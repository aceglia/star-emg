import numpy as np
import scipy
from scipy.fft import rfft, rfftfreq

try:
    from fbpca import pca
except ImportError:
    pca = None

from numpy.lib.stride_tricks import as_strided


def get_signal_from_hankel(hankel: np.ndarray, tau: int = 1) -> np.ndarray:
    """
    Reconstruct a 1D signal from a Hankel matrix using anti-diagonal averaging.

    Parameters
    ------------
    hankel : np.ndarray
        Hankel matrix representation of the signal.
    tau : int
        Delay used when constructing the Hankel matrix.

    Returns
    --------
    np.ndarray
        Reconstructed signal.
    """
    rows, cols = hankel.shape
    i = np.arange(rows)[:, np.newaxis]
    j = np.arange(cols)
    idx = i * tau + j

    vals = hankel.ravel()
    idx_flat = idx.ravel()

    total_length = (rows - 1) * tau + cols
    sums = np.bincount(idx_flat, weights=vals, minlength=total_length)
    counts = np.bincount(idx_flat, minlength=total_length)

    reconstructed_signal = sums / counts
    return reconstructed_signal


def hankel_delay_fast(x: np.ndarray, L: int, tau: int) -> np.ndarray:
    """
    Construct a Hankel matrix with delay using stride tricks.

    Parameters
    ------------
    x : np.ndarray
        Input signal.
    L : int
        Number of rows of the Hankel matrix.
    tau : int
        Delay between rows.

    Returns
    --------
    np.ndarray
        Hankel matrix view of the signal.
    """
    N = len(x)
    K = N - (L - 1) * tau
    if K <= 0:
        raise ValueError("L and tau too large")
    stride = x.strides[0]
    return as_strided(x, shape=(L, K), strides=(tau * stride, stride))


def compute_svd(
    emg_signal: np.ndarray,
    n_rows: int = 800,
    hankel: np.ndarray = None,
    randomized: bool = True,
    nb_principal_components: int = None,
    epsilon: float = None,
    hankel_delay: int = 1,
) -> tuple:
    """
    Compute SVD of a Hankel matrix derived from the signal.

    Parameters
    ------------
    emg_signal : np.ndarray
        Input EMG signal.
    n_rows : int
        Number of rows in the Hankel matrix.
    hankel : np.ndarray, optional
        Precomputed Hankel matrix.
    randomized : bool
        Use randomized SVD.
    nb_principal_components : int, optional
        Number of principal components to retain.
    epsilon : float, optional
        Threshold for singular value truncation.
    hankel_delay : int
        Delay used for Hankel construction.

    Returns
    --------
    tuple
        U, S, Vh matrices and the Hankel matrix.
    """
    if hankel is None or n_rows != hankel.shape[0]:
        hankel = hankel_delay_fast(emg_signal, n_rows, hankel_delay)

    if randomized:
        nb_principal_components = hankel.shape[0] if nb_principal_components is None else nb_principal_components
        if pca is None:
            print(
                "ImportError: fbpca is not installed. Falling back to classic SVD. Please install fbpca to use this feature."
            )
            return compute_svd(
                emg_signal,
                n_rows=n_rows,
                hankel=hankel,
                randomized=False,
                nb_principal_components=nb_principal_components,
                epsilon=epsilon,
                hankel_delay=hankel_delay,
            )
        else:
            U, S, Vh = pca(hankel, k=nb_principal_components, raw=True, n_iter=2)
    else:
        U, S, Vh = scipy.linalg.svd(
            hankel,
            full_matrices=False,
            check_finite=False,
            overwrite_a=True,
        )
        if nb_principal_components is not None:
            U, S, Vh = U[:, :nb_principal_components], S[:nb_principal_components], Vh[:nb_principal_components]
        if epsilon is not None:
            idx = np.argwhere(S > epsilon).flatten()
            U, S, Vh = U[:, idx], S[idx], Vh[idx]

    return U, S, Vh, hankel


def mean_around_row_max(X: np.ndarray, w: int) -> np.ndarray:
    """
    Compute the mean value around the maximum of each row.

    Parameters
    ------------
    X : np.ndarray
        Input 2D array.
    w : int
        Window size around the maximum.

    Returns
    --------
    np.ndarray
        Mean values for each row.
    """
    N, M = X.shape
    idx = np.argmax(X, axis=1)
    offsets = np.arange(-w, w + 1)
    cols = idx[:, None] + offsets[None, :]
    cols = np.clip(cols, 0, M - 1)
    values = X[np.arange(N)[:, None], cols]
    # out = np.empty(N, dtype=X.dtype)
    # for i in range(N):
    #     start = max(0, idx[i] - w)
    #     end   = min(M, idx[i] + w + 1)
    #     out[i] = X[i, start:end].mean()
    return values.mean(axis=1)


def peak_energy_ratio(X: np.ndarray) -> np.ndarray:
    """
    Compute peak energy ratio for each row.

    Parameters
    ------------
    X : np.ndarray
        Input array (e.g., FFT magnitudes).

    Returns
    --------
    np.ndarray
        Peak energy ratios.
    """
    P = np.abs(X) ** 2
    w = int(X.shape[-1] * 5 / 100)
    return np.max(P, axis=-1) / mean_around_row_max(P, w)


def remove_singular_values(
    v: np.ndarray,
    s: np.ndarray,
    u: np.ndarray,
    data_rate: float = None,
    freq_bounds: list = [10, 450],
    factor: float = 0.5,
    fft_freqs: rfftfreq = None,
    rejected_idx: list = None,
) -> tuple:
    """
    Remove singular values based on spectral characteristics.

    Parameters
    ------------
    v : np.ndarray
        Right singular vectors.
    s : np.ndarray
        Singular values.
    u : np.ndarray
        Left singular vectors.
    data_rate : float
        Sampling frequency.
    freq_bounds : list
        Frequency bounds for valid components.
    factor : float
        Threshold factor for peak detection.
    fft_freqs : np.ndarray, optional
        Precomputed FFT frequencies.

    Returns
    --------
    tuple
        Modified singular values, v and u.
    """
    if rejected_idx is None:
        fft_freqs = rfftfreq(v.shape[1], 1 / data_rate) if fft_freqs is None else fft_freqs
        all_fft_max = np.abs(rfft(v, axis=-1))
        peak_ratio = peak_energy_ratio(all_fft_max)
        ratio = peak_ratio / np.max(peak_ratio)

        freqs = fft_freqs[np.argmax(all_fft_max, axis=1)]
        # print(  "max freqs:", freqs)

        to_reject = [
            np.argwhere((freqs <= freq_bounds[0]) | (freqs >= freq_bounds[1]))[:, 0],
            np.argwhere((ratio > np.median(ratio) + factor * np.std(ratio)))[:, 0],
        ]
        rejected_idx = np.unique(np.hstack(to_reject))
    s[rejected_idx] = 0
    return s, v, u, rejected_idx

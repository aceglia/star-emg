import numpy as np
import scipy
import scipy.signal as signal
from scipy.fft import rfft, rfftfreq
from scipy.stats import kurtosis
from typing import Optional, Tuple, List, Union

from star_emg.app.gui_utils import ensure_list


def _butter_bandpass(lowcut: float, highcut: float, fs: float, order: int = 4) -> Tuple[np.ndarray, np.ndarray]:
    """
    Design a Butterworth bandpass filter.

    Parameters
    ----------
    lowcut : float
        Low cutoff frequency (Hz).
    highcut : float
        High cutoff frequency (Hz).
    fs : float
        Sampling frequency (Hz).
    order : int, optional
        Filter order, by default 4.

    Returns
    -------
    tuple[np.ndarray, np.ndarray]
        Numerator (b) and denominator (a) filter coefficients.
    """
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = signal.butter(order, [low, high], btype="band")
    return b, a


def _bandpass_filter(
    data: np.ndarray, cutoff: List[float], fs: float, order: int = 4, offline=True, a=None, b=None
) -> np.ndarray:
    """
    Apply zero-phase Butterworth bandpass filtering.

    Parameters
    ----------
    data : np.ndarray
        1D signal data.
    cutoff : list[float]
        [lowcut, highcut] in Hz.
    fs : float
        Sampling frequency (Hz).
    order : int, optional
        Filter order, by default 4.

    Returns
    -------
    np.ndarray
        Filtered signal with same shape as input.
    """
    if a is None or b is None:
        b, a = _butter_bandpass(cutoff[0], cutoff[1], fs, order)
    if offline:
        return signal.filtfilt(b, a, data), a, b
    else:
        return signal.lfilter(b, a, data), a, b


def _butter_lowpass(cutoff: float, fs: float, order: int = 5) -> Tuple[np.ndarray, np.ndarray]:
    """
    Design a Butterworth lowpass filter.

    Parameters
    ----------
    cutoff : float
        Cutoff frequency (Hz).
    fs : float
        Sampling frequency (Hz).
    order : int, optional
        Filter order, by default 5.

    Returns
    -------
    tuple[np.ndarray, np.ndarray]
        Numerator (b) and denominator (a) filter coefficients.
    """
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    return signal.butter(order, normal_cutoff, btype="low", analog=False)


def _butter_lowpass_filter(
    data: np.ndarray, cutoff: float, fs: float, order: int = 5, offline=True, a=None, b=None
) -> np.ndarray:
    """
    Apply zero-phase Butterworth lowpass filtering.

    Parameters
    ----------
    data : np.ndarray
        1D signal array.
    cutoff : float
        Cutoff frequency (Hz).
    fs : float
        Sampling frequency (Hz).
    order : int, optional
        Filter order, by default 5.

    Returns
    -------
    np.ndarray
        Filtered signal.
    """
    b, a = _butter_lowpass(cutoff, fs, order)
    if offline:
        return signal.filtfilt(b, a, data), a, b
    else:
        return signal.lfilter(b, a, data), a, b


def _butter_highpass(cutoff: float, fs: float, order: int = 5) -> Tuple[np.ndarray, np.ndarray]:
    """
    Design a Butterworth highpass filter.

    Parameters
    ----------
    cutoff : float
        Cutoff frequency (Hz).
    fs : float
        Sampling frequency (Hz).
    order : int, optional
        Filter order, by default 5.

    Returns
    -------
    tuple[np.ndarray, np.ndarray]
        Numerator (b) and denominator (a) filter coefficients.
    """
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    return signal.butter(order, normal_cutoff, btype="high", analog=False)


def _butter_highpass_filter(
    data: np.ndarray, cutoff: float, fs: float, order: int = 5, offline=True, a=None, b=None
) -> np.ndarray:
    """
    Apply zero-phase Butterworth highpass filtering.

    Parameters
    ----------
    data : np.ndarray
        1D signal array.
    cutoff : float
        Cutoff frequency (Hz).
    fs : float
        Sampling frequency (Hz).
    order : int, optional
        Filter order, by default 5.

    Returns
    -------
    np.ndarray
        Filtered signal.
    """
    b, a = _butter_highpass(cutoff, fs, order)
    if offline:
        return signal.filtfilt(b, a, data), a, b
    else:
        return signal.lfilter(b, a, data), a, b


def filter_data(
    data: np.ndarray,
    cutoff: Union[float, List[float]] = 450.0,
    order: int = 2,
    fs: float = 2000.0,
    filter_type: str = "low",
    offline=True,
    a=None,
    b=None,
) -> np.ndarray:
    """
    Apply Butterworth filtering to 3D data array.

    Parameters
    ----------
    data : np.ndarray
        Array of shape [epochs, channels, samples].
    cutoff : float or list[float], optional
        Cutoff frequency or [lowcut, highcut], by default 450.0.
    order : int, optional
        Filter order, by default 2.
    fs : float, optional
        Sampling frequency (Hz), by default 2000.0.
    filter_type : str, optional
        "low", "high", or "band".

    Returns
    -------
    np.ndarray
        Filtered array, same shape as input.
    """
    if filter_type == "low":
        filter_function = _butter_lowpass_filter
    elif filter_type == "band":
        filter_function = _bandpass_filter
    elif filter_type == "high":
        filter_function = _butter_highpass_filter
    else:
        raise ValueError("Invalid filter type")

    epochs_added = False
    if len(data.shape) != 3:
        epochs_added = True
        data = data[None]
    filtered_data = np.zeros_like(data)
    for i in range(data.shape[0]):
        for k in range(data.shape[1]):
            filtered_data[i, k, :], a, b = filter_function(
                data[i, k, :], cutoff, fs, order=order, offline=offline, a=a, b=b
            )
    if epochs_added:
        filtered_data = filtered_data[0]
    return filtered_data, a, b


def robust_max_percentile(x: np.ndarray, percent: float = 99.9) -> np.ndarray:
    """
    Get percentile-based robust maximum.

    Parameters
    ----------
    x : np.ndarray
        Input array, typically FFT amplitude.
    q : float, optional
        Percentile value, by default 99.5.

    Returns
    -------
    np.ndarray
        Percentile value along last axis after cleaning the signals from possible artifacts.
    """
    # return np.percentile(x, q, axis=-1)
    x = np.asarray(x)
    med = np.median(x, axis=-1, keepdims=True)
    mad = np.median(np.abs(x - med), axis=-1, keepdims=True) + 1e-12
    mask = x < med + 3 * mad
    if not np.any(mask):
        return np.percentile(x, percent, axis=-1)
    x_clean = np.delete(x, np.argwhere(~mask), axis=-1)
    return np.percentile(x_clean, percent, axis=-1)


def line_length(data: np.ndarray, w: Optional[int] = None) -> np.ndarray:
    """
    Compute normalized line length quality metric.

    Parameters
    ----------
    data : np.ndarray
        1D or multidimensional signals.
    w : int or None
        Window length (unused for current formula)

    Returns
    -------
    np.ndarray
        Normalized line length.
    """
    # use central diff
    diff = data[..., 2:] - data[..., :-2]
    ll = np.sum(np.abs(diff), axis=-1)
    return ll / (np.std(data) * data.shape[-1])


def kurtosis_value(data: np.ndarray, w: int = 15) -> np.ndarray:
    """
    Compute moving-window kurtosis metric.

    Parameters
    ----------
    data : np.ndarray
        Signal array.
    w : int, optional
        Window length in samples, by default 15.

    Returns
    -------
    np.ndarray
        Average kurtosis over windows.
    """
    non_zero_idx = np.argwhere(data == 0)
    if len(non_zero_idx) > 0:
        data = np.delete(data, non_zero_idx, axis=-1)
    stds = np.stack([kurtosis(data[..., i : i + w], axis=-1) for i in range(0, data.shape[-1] - w, w)])
    return np.mean(stds, axis=0)


def median_frequency(
    data: np.ndarray,
    fs: float = 2000,
    fft: Optional[np.ndarray] = None,
    fft_freq: Optional[np.ndarray] = None,
    return_fft: bool = False,
) -> Union[np.ndarray, Tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """
    Compute median frequency of power spectrum.

    Parameters
    ----------
    data : np.ndarray
        Input signal.
    fs : float, optional
        Sampling frequency (Hz), by default 2000.
    fft : np.ndarray or None, optional
        Precomputed FFT data, by default None.
    fft_freq : np.ndarray or None, optional
        Frequencies array, by default None.
    return_fft : bool, optional
        Set True to return (median_freq, fft, freqs).

    Returns
    -------
    np.ndarray or tuple
        Median frequency, optionally FFT and frequency vector.
    """
    fft_data = abs(rfft(data, axis=-1)) if fft is None else fft
    cumsum = np.cumsum(fft_data**2, axis=-1)
    half_energy = cumsum[..., -1:] / 2
    idx = np.argmax(cumsum >= half_energy, axis=-1)
    freqs = rfftfreq(data.shape[-1], d=1 / fs) if fft_freq is None else fft_freq

    if return_fft:
        return freqs[idx], fft_data, freqs

    return freqs[idx]


def compute_signal_comparison(
    data: np.ndarray,
    ref_data: np.ndarray,
    n_frame_stim: int = 6000,
) -> Tuple[float, int, float]:
    """
    Compare two signals using correlation, Pearson, and peak amplitude error.

    Parameters
    ----------
    data : np.ndarray
        Processed signal.
    ref_data : np.ndarray
        Reference signal.
    n_frame_stim : int, optional
        Starting frame for peak analysis, by default 6000.

    Returns
    -------
    tuple[float, int, float]
        (pearson corr, lag, peaks amplitude error).
    """
    correlation = signal.correlate(data[:], ref_data[: data.shape[0]])
    lag = signal.correlation_lags(data.shape[0], ref_data[: data.shape[0]].shape[0])
    correlation /= np.max(correlation)

    final_lag = lag[np.argmax(correlation)]
    pearson = scipy.stats.pearsonr(data[100:], ref_data[100 : data.shape[0]])[0]

    peak_ref = scipy.signal.find_peaks(
        np.abs(ref_data[int(n_frame_stim + 0.1 * 2000) : int(n_frame_stim + 0.4 * 2000)]), height=0.08
    )
    amplitude_ref = np.sum(peak_ref[1]["peak_heights"])

    peak_proc = scipy.signal.find_peaks(
        np.abs(data[int(n_frame_stim + 0.1 * 2000) : int(n_frame_stim + 0.4 * 2000)]), height=0.08
    )
    amplitude_proc = np.sum(peak_proc[1]["peak_heights"])

    peaks_error = amplitude_ref - amplitude_proc

    return pearson, final_lag, peaks_error


def merge_dict(old: Optional[dict], new: dict) -> dict:
    """
    Merge result dictionaries with array concat.

    Parameters
    ----------
    old : dict or None
        Existing dictionary (may contain results arrays).
    new : dict
        New dictionary to merge in.

    Returns
    -------
    dict
        Merged dictionary.
    """
    out_dict = {}

    if "data" in new:
        new.pop("data")

    if old is None:
        for k, v in new.items():
            if v is None:
                new[k] = [None]
            elif v.ndim > 1:
                new[k] = v[None]
        return new

    for k, v in new.items():
        if v is None:
            out_dict[k] = np.hstack([old.get(k, [None]), [None]])
        elif v.ndim > 1:
            out_dict[k] = np.concatenate((old.get(k, []), v[None]))
        else:
            out_dict[k] = np.concatenate((old.get(k, []), v))

    return out_dict


class Quality:
    def __init__(self, shape=None):
        self.raw_data_quality = None
        self.clean_data_quality = None
        self.ground_truth_quality = None
        self.quality_mapping = {"kurtosis": 0, "line_length": 1, "mdf": 2, "fft_amplitude": 3}
        self.n_metrics = 4
        self.initialized = False
        if shape is not None:
            self.init_shape(shape)

    def init_shape(self, shape):
        """
        Initialize quality array shapes [metric, ...shape_without_last_dim].
        """
        total_shape = [self.n_metrics]
        total_shape.extend(shape[:-1])
        self.raw_data_quality = np.empty(total_shape) * np.nan
        self.clean_data_quality = np.empty(total_shape) * np.nan
        self.ground_truth_quality = np.empty(total_shape) * np.nan
        self.initialized = True

    def _get_quality_per_idx(self, idx=None, channel=None, quality_idx=0):
        raw, clean, truth = self._get_all_quality(idx, channel)
        return raw[quality_idx], clean[quality_idx], truth[quality_idx]

    def _get_all_quality(self, idx=None, channel=None):
        raw = self._return_shaped_matrix(self.raw_data_quality, idx, channel)
        clean = self._return_shaped_matrix(self.clean_data_quality, idx, channel)
        truth = self._return_shaped_matrix(self.ground_truth_quality, idx, channel)
        return raw, clean, truth

    def get_kurtosis(self, idx=None, channel=None):
        return self._get_quality_per_idx(idx, channel, 0)

    def get_mdf(self, idx=None, channel=None):
        return self._get_quality_per_idx(idx, channel, 2)

    def get_line_length(self, idx=None, channel=None):
        return self._get_quality_per_idx(idx, channel, 1)

    def get_fft_amplitude(self, idx=None, channel=None):
        return self._get_quality_per_idx(idx, channel, 3)

    def get_quality(self, idx=None, channel=None):
        return self._get_all_quality(idx, channel)

    def _return_shaped_matrix(self, generic, idx=None, channel=None):
        if idx is not None:
            generic = generic[:, ensure_list(idx)]
        if channel is not None:
            generic = generic[:, :, ensure_list(channel)]
        return generic

    def _get_indices(self, idx=None, channel=None):
        i = slice(None)
        j = ensure_list(idx) if idx is not None else slice(None)
        k = ensure_list(channel) if channel is not None else slice(None)
        return (j, k, i)

    def compute_quality(
        self,
        raw,
        processed,
        ground_truth=None,
        channel=None,
        idx=None,
        kw=100,
        maxw=150,
        fs=2000,
        percentile=[99.5, 99.9, 99.9],
        fft_freqs=None,
        analysis=list(range(4)),
    ):
        """
        Compute multi-metric quality scores for raw/processed/[ground_truth] signals.
        """
        if raw.ndim != 3:
            raw = raw[None]
        if processed.ndim != 3:
            processed = processed[None]
        if ground_truth is not None and ground_truth.ndim != 3:
            ground_truth = ground_truth[None]
        if not self.initialized:
            self.init_shape(raw.shape)
        if ground_truth is not None:
            self.ground_truth = True
        data_list = [raw, processed, ground_truth]
        data_quality = ["raw_data_quality", "clean_data_quality", "ground_truth_quality"]
        indices = self._get_indices(idx, channel)
        for qual, data, per in zip(data_quality, data_list, percentile):
            if data is None:
                continue
            quality = getattr(self, qual)
            quality[(0, *indices[:-1])] = kurtosis_value(data, kw) if 0 in analysis else np.nan
            quality[(1, *indices[:-1])] = line_length(data) if 1 in analysis else np.nan
            quality[(2, *indices[:-1])], fft, fft_freqs = (
                median_frequency(data, fs, return_fft=True, fft_freq=fft_freqs)
                if (2 in analysis or 3 in analysis)
                else np.nan
            )
            quality[(3, *indices[:-1])] = (
                robust_max_percentile(fft[..., : int(np.argwhere(fft_freqs > maxw)[0].item())], per)
                if 3 in analysis
                else np.nan
            )
        return self.get_quality(idx, channel)

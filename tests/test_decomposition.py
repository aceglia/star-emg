import numpy as np
import pytest

from star_emg.decomposition_utils import (
    get_signal_from_hankel,
    hankel_delay_fast,
    compute_svd,
    remove_singular_values,
)


def test_hankel_delay_fast():
    x = np.arange(10)

    H = hankel_delay_fast(x, L=3, tau=2)

    expected = np.array(
        [
            [0, 1, 2, 3, 4, 5],
            [2, 3, 4, 5, 6, 7],
            [4, 5, 6, 7, 8, 9],
        ]
    )

    np.testing.assert_array_equal(H, expected)


def test_hankel_delay_fast_invalid():
    x = np.arange(10)
    with pytest.raises(ValueError):
        hankel_delay_fast(x, L=20, tau=2)


@pytest.mark.parametrize("tau", [1, 2, 3])
def test_hankel_reconstruction_tau(tau):
    signal = np.random.randn(100)

    H = hankel_delay_fast(signal, L=20, tau=tau)

    reconstructed = get_signal_from_hankel(H, tau=tau)

    np.testing.assert_allclose(reconstructed, signal, atol=1e-6)


@pytest.mark.parametrize("randomized", [False, True])
def test_compute_svd_shapes(randomized):
    signal = np.random.randn(1000)
    U, S, Vh, H = compute_svd(
        signal,
        n_rows=50,
        randomized=randomized,
    )
    assert U.shape[0] == 50
    assert len(S) == min(H.shape)
    assert Vh.shape[0] == len(S)


def test_compute_svd_values():
    np.random.seed(0)
    signal = np.random.randn(1000)
    U, S, Vh, H = compute_svd(
        signal,
        n_rows=50,
        randomized=False,
    )
    np.testing.assert_allclose(
        U[:5, 5], np.array([0.18243271, -0.22133605, 0.27563074, -0.11742851, 0.07237985]), atol=1e-6
    )
    np.testing.assert_allclose(
        S[:5], np.array([37.56436258, 36.03179483, 35.72729699, 35.28566582, 35.10321724]), atol=1e-6
    )
    np.testing.assert_allclose(
        Vh[:5, 5], np.array([0.00926913, -0.01469747, 0.05148258, -0.04651756, 0.04863341]), atol=1e-6
    )


def test_compute_svd_nb_components():
    signal = np.random.randn(1000)

    U, S, Vh, H = compute_svd(
        signal,
        n_rows=50,
        randomized=False,
        nb_principal_components=5,
    )

    assert U.shape[1] == 5
    assert len(S) == 5
    assert Vh.shape[0] == 5


def test_remove_singular_values():
    fs = 2000

    t = np.arange(1000) / fs

    v = np.vstack(
        [
            np.sin(2 * np.pi * 30 * t),
            np.random.randn(len(t)),
        ]
    )

    s = np.array([10.0, 5.0])

    u = np.eye(2)

    s_reduced, _, _, rejected = remove_singular_values(
        v=v,
        s=s.copy(),
        u=u,
        data_rate=fs,
        factor=0.1,
    )

    assert len(rejected) > 0

    for idx in rejected:
        assert s_reduced[idx] == 0

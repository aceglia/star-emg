# tests/test_signal_processing.py

import numpy as np
import pytest

from star_emg.processing_utils import (
    _butter_bandpass,
    _bandpass_filter,
    _butter_lowpass,
    _butter_lowpass_filter,
    _butter_highpass,
    _butter_highpass_filter,
    filter_data,
    robust_max_percentile,
    line_length,
    kurtosis_value,
    median_frequency,
    compute_signal_comparison,
    merge_dict,
    Quality,
)

# =============================================================================
# FILTER DESIGN
# =============================================================================


def test_butter_bandpass():
    b, a = _butter_bandpass(20, 450, fs=2000)

    assert len(a) > 0
    assert len(b) > 0
    assert len(a) == len(b)


def test_butter_lowpass():
    b, a = _butter_lowpass(450, fs=2000)

    assert len(a) > 0
    assert len(b) > 0


def test_butter_highpass():
    b, a = _butter_highpass(20, fs=2000)

    assert len(a) > 0
    assert len(b) > 0


# =============================================================================
# FILTER APPLICATION
# =============================================================================


@pytest.mark.parametrize(
    "filter_function,args",
    [
        (_butter_lowpass_filter, (100,)),
        (_butter_highpass_filter, (20,)),
        (_bandpass_filter, ([20, 450],)),
    ],
)
def test_filter_shape(filter_function, args):
    fs = 2000
    t = np.arange(0, 2, 1 / fs)

    signal = np.sin(2 * np.pi * 10 * t) + np.sin(2 * np.pi * 100 * t) + np.sin(2 * np.pi * 600 * t)

    filtered, _, _ = filter_function(signal, *args, fs=fs)

    assert filtered.shape == signal.shape


def test_filter_data_lowpass():
    data = np.random.randn(2, 4, 1000)

    filtered, _, _ = filter_data(
        data,
        cutoff=100,
        fs=2000,
        filter_type="low",
    )

    assert filtered.shape == data.shape


def test_filter_data_highpass():
    data = np.random.randn(2, 4, 1000)

    filtered, _, _ = filter_data(
        data,
        cutoff=20,
        fs=2000,
        filter_type="high",
    )

    assert filtered.shape == data.shape


def test_filter_data_bandpass():
    data = np.random.randn(2, 4, 1000)

    filtered, _, _ = filter_data(
        data,
        cutoff=[20, 450],
        fs=2000,
        filter_type="band",
    )

    assert filtered.shape == data.shape


def test_filter_data_invalid_type():
    data = np.random.randn(1, 1, 100)

    with pytest.raises(ValueError):
        filter_data(data, filter_type="wrong")


# =============================================================================
# ROBUST MAX PERCENTILE
# =============================================================================


def test_robust_max_percentile():
    x = np.ones(100)
    x[-1] = 1000

    value = robust_max_percentile(x)

    assert value < 1000
    assert value > 0


# =============================================================================
# LINE LENGTH
# =============================================================================


def test_line_length():
    np.random.seed(0)
    signal = np.random.randn(100)

    ll = line_length(signal)

    assert np.isfinite(ll)
    np.testing.assert_allclose(ll, 1.044859753742975, atol=1e-6)


# =============================================================================
# KURTOSIS
# =============================================================================
@pytest.mark.parametrize("w", [15, 50])
def test_kurtosis_value(w):
    np.random.seed(0)
    data = np.random.randn(500)

    value = kurtosis_value(data, w)
    target = [-0.43925071463489385, -0.23839052478927808]
    assert np.isfinite(value)
    if w == 15:
        np.testing.assert_allclose(value, target[0], atol=1e-6)
    else:
        np.testing.assert_allclose(value, target[1], atol=1e-6)


# =============================================================================
# MEDIAN FREQUENCY
# =============================================================================


def test_median_frequency_single_tone():
    fs = 2000
    f = 100

    t = np.arange(0, 2, 1 / fs)
    signal = np.sin(2 * np.pi * f * t)

    mdf = median_frequency(signal, fs=fs)

    assert abs(mdf - f) < 10


def test_median_frequency_return_fft():
    fs = 2000
    signal = np.random.randn(1000)

    mdf, fft, freqs = median_frequency(
        signal,
        fs=fs,
        return_fft=True,
    )

    assert fft.shape[-1] == len(freqs)
    assert np.isscalar(mdf)


# =============================================================================
# SIGNAL COMPARISON
# =============================================================================


def test_compute_signal_comparison_identical_signals():
    fs = 2000
    n = 8000

    signal = np.random.randn(n)

    pearson, lag, error = compute_signal_comparison(
        signal,
        signal.copy(),
        n_frame_stim=6000,
    )

    assert pearson > 0.99
    assert lag == 0
    assert abs(error) < 1e-12


# =============================================================================
# MERGE DICT
# =============================================================================


def test_merge_dict_first_entry():
    new = {
        "a": np.array([1, 2, 3]),
        "b": np.array([[1, 2], [3, 4]]),
    }

    out = merge_dict(None, new)

    assert "a" in out
    assert "b" in out


def test_merge_dict_existing():
    old = {
        "a": np.array([1, 2]),
        "b": np.array([[[1, 2], [3, 4]]]),
    }

    new = {
        "a": np.array([3, 4]),
        "b": np.array([[5, 6], [7, 8]]),
    }

    out = merge_dict(old, new)

    assert out["a"].shape[0] == 4
    assert out["b"].shape[0] == 2


# =============================================================================
# QUALITY CLASS
# =============================================================================


def test_quality_initialization():
    q = Quality(shape=(2, 4, 1000))

    assert q.initialized
    assert q.raw_data_quality.shape == (4, 2, 4)


def test_quality_compute():
    raw = np.random.randn(2, 3, 1000)
    clean = raw * 0.8

    q = Quality()

    raw_q, clean_q, truth_q = q.compute_quality(
        raw,
        clean,
        fs=2000,
    )

    assert raw_q.shape == (4, 2, 3)
    assert clean_q.shape == (4, 2, 3)
    assert truth_q.shape == (4, 2, 3)


def test_quality_getters():
    raw = np.random.randn(2, 3, 1000)
    clean = raw * 0.8

    q = Quality()
    q.compute_quality(raw, clean)

    kurtosis_raw, _, _ = q.get_kurtosis()
    ll_raw, _, _ = q.get_line_length()
    mdf_raw, _, _ = q.get_mdf()
    fft_raw, _, _ = q.get_fft_amplitude()

    assert kurtosis_raw.shape == (2, 3)
    assert ll_raw.shape == (2, 3)
    assert mdf_raw.shape == (2, 3)
    assert fft_raw.shape == (2, 3)


def test_quality_channel_selection():
    raw = np.random.randn(2, 4, 1000)
    clean = raw.copy()

    q = Quality()
    q.compute_quality(raw, clean)

    selected = q.get_quality(channel=1)

    assert selected[0].shape == (4, 2, 1)

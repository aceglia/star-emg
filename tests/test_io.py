# tests/test_data_loader.py

import numpy as np
import pytest
from unittest.mock import patch

from star_emg.io_utils import (
    ensure_array_dim,
    load_from_dict,
    DataLoader,
)

# =============================================================================
# ensure_array_dim
# =============================================================================


def test_ensure_array_dim_1d():
    data = np.arange(100)

    out = ensure_array_dim(data)

    assert out.shape == (1, 1, 100)


def test_ensure_array_dim_2d():
    data = np.random.randn(4, 100)

    out = ensure_array_dim(data)

    assert out.shape == (1, 4, 100)


def test_ensure_array_dim_3d():
    data = np.random.randn(2, 4, 100)

    out = ensure_array_dim(data)

    assert out.shape == data.shape


def test_ensure_array_dim_invalid():
    data = np.random.randn(2, 3, 4, 5)

    with pytest.raises(RuntimeError):
        ensure_array_dim(data)


# =============================================================================
# load_from_dict
# =============================================================================


def test_load_from_dict():
    data = {
        "values": np.random.randn(2, 4, 100),
        "channel_names": ["a", "b", "c", "d"],
        "data_rate": 2000,
    }

    array, channels, frames, rate = load_from_dict(data)

    assert array.shape == (2, 4, 100)
    assert channels == ["a", "b", "c", "d"]
    assert len(frames) == 2
    assert rate == 2000


def test_load_from_dict_default_channel_names():
    data = {
        "values": np.random.randn(2, 3, 100),
    }

    array, channels, frames, rate = load_from_dict(data)

    assert len(channels) == 3
    assert channels[0] == "channel_0"
    assert rate is None


# =============================================================================
# DataLoader initialization from ndarray
# =============================================================================


def test_dataloader_from_array():
    data = np.random.randn(1, 4, 1000)

    loader = DataLoader(
        data,
        ignore_filtering=True,
        data_rate=2000,
    )

    assert loader.is_data_loaded
    assert loader.init_data.shape == data.shape
    assert loader.data_rate == 2000


def test_dataloader_without_data_rate():
    data = np.random.randn(1, 4, 1000)

    with pytest.raises(ValueError):
        DataLoader(
            data,
            ignore_filtering=True,
        )


def test_flatten_unflatten():
    data = np.random.randn(2, 4, 100)

    loader = DataLoader(
        data,
        ignore_filtering=True,
        data_rate=2000,
    )

    flattened = loader.flatten_data(data)

    assert flattened.shape == (8, 100)

    restored = loader.unflatten_data(flattened)

    np.testing.assert_array_equal(restored, data)


# =============================================================================
# stack epochs
# =============================================================================


def test_apply_stack_epochs():
    data = np.random.randn(3, 4, 100)

    loader = DataLoader(
        data,
        ignore_filtering=True,
        data_rate=2000,
    )

    original_shape = data.shape

    loader._apply_stack_epochs()

    assert loader.stack_epochs_applied

    restored = loader.get_unstacked_data()

    assert restored.shape == original_shape

    np.testing.assert_allclose(restored, data)


# =============================================================================
# center_and_filter
# =============================================================================


def test_center_only():
    data = np.random.randn(1, 4, 1000) + 10

    loader = DataLoader(
        data.copy(),
        ignore_filtering=True,
        data_rate=2000,
    )

    centered = loader.center_and_filter(
        data.copy(),
        center=True,
        signal_filter=False,
    )

    np.testing.assert_allclose(
        np.mean(centered, axis=-1),
        0,
        atol=1e-10,
    )


def test_no_center_no_filter():
    data = np.random.randn(1, 4, 1000)

    loader = DataLoader(
        data.copy(),
        ignore_filtering=True,
        data_rate=2000,
    )

    out = loader.center_and_filter(
        data.copy(),
        center=False,
        signal_filter=False,
    )

    np.testing.assert_array_equal(out, data)


def test_invalid_lowpass_cutoff():
    data = np.random.randn(1, 2, 1000)

    loader = DataLoader(
        data,
        ignore_filtering=True,
        data_rate=1000,
    )

    with pytest.raises(RuntimeError):
        loader.center_and_filter(
            data.copy(),
            signal_filter=True,
            cutoff=600,
            fs=1000,
        )


def test_invalid_bandpass_cutoff():
    data = np.random.randn(1, 2, 1000)

    loader = DataLoader(
        data,
        ignore_filtering=True,
        data_rate=1000,
    )

    with pytest.raises(RuntimeError):
        loader.center_and_filter(
            data.copy(),
            signal_filter=True,
            cutoff=[20, 600],
            fs=1000,
        )


# =============================================================================
# filtering
# =============================================================================


def test_apply_filtering():
    data = np.random.randn(1, 4, 2000)

    loader = DataLoader(
        data.copy(),
        ignore_filtering=True,
        data_rate=2000,
    )

    filtered = loader.apply_filtering()

    assert filtered.shape == data.shape


def test_apply_filtering_external_data():
    data = np.random.randn(1, 4, 2000)

    loader = DataLoader(
        data.copy(),
        ignore_filtering=True,
        data_rate=2000,
    )

    other = np.random.randn(1, 4, 2000)

    filtered = loader.apply_filtering(other)

    assert filtered.shape == other.shape


import os
from star_emg.io_utils import load_txt_file
from star_emg.io_utils import load_mat_file
from star_emg.io_utils import load_bio_file
from star_emg.io_utils import load_npz_file

base_example_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "examples", "data", "example")


@pytest.mark.parametrize(
    "extension, fct",
    [(".txt", load_txt_file), (".mat", load_mat_file), (".bio", load_bio_file), (".npz", load_npz_file)],
)
def test_load_file(extension, fct):
    example_txt_file = base_example_file + extension
    if extension in [".txt"]:
        data, channels, frames, rate, time = fct(example_txt_file)
    elif extension in [".mat"]:
        data, channels, frames, rate = fct(example_txt_file)
    else:
        data, channels, frames, rate, time, loaded_raw = fct(example_txt_file)

    assert data.ndim == 3
    assert len(channels) == 2
    assert len(frames) == 9
    assert int(rate) == 1925


def test_read_zarr_ds():
    from star_emg.app.save_utils import ZarrRecording

    zarr_ds = ZarrRecording.load_dataset(base_example_file + ".stream")
    data_dict, configs = zarr_ds.to_dict()
    assert data_dict["values"].ndim == 3
    assert len(data_dict["channel_names"]) == 2
    assert len(data_dict["time"]) == 9
    assert int(data_dict["data_rate"]) == 1925
    return data_dict

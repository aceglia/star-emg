import numpy as np
import pytest
from star_emg.rt_automatic_remover import RtArtifactRemover


def test_init_without_data():
    remover = RtArtifactRemover(window_size=1000)
    assert remover.window_size == 1000
    assert remover.offline is False
    assert remover.output is None
    assert remover.idx == 0
    assert remover.get_init_signal() is None


def test_init_with_data():
    data = np.random.randn(1, 1000)
    remover = RtArtifactRemover(
        window_size=1000,
        data=data,
        data_rate=2000,
    )

    assert remover.offline is True
    assert remover.streamer.init_data.shape == (1, 1000)
    assert remover.streamer.data_rate == 2000
    assert np.allclose(data, remover.streamer.init_data, atol=1e-6)
    assert np.allclose(data, remover.get_init_signal(), atol=1e-6)


def test_stream_evaluation_not_implemented():
    remover = RtArtifactRemover(window_size=1000)

    with pytest.raises(NotImplementedError):
        remover._stream_evaluation(np.random.randn(100))


def test_process_chunk_requires():
    remover = RtArtifactRemover(window_size=1000)

    with pytest.raises(ValueError):
        remover.process_chunk(
            np.random.randn(2, 100),
            notch_filter=True,
        )
    with pytest.raises(AssertionError):
        remover.process_chunk(
            np.random.randn(100),
            notch_filter=True,
        )


@pytest.mark.parametrize("chunk_size", [500, 1000])
def test_process_chunk_buffer_not_full(chunk_size):
    np.random.seed(0)
    remover = RtArtifactRemover(window_size=1000, center=True, data_rate=2000)
    chunk = np.random.randn(1, chunk_size)

    result = remover.process_chunk(
        chunk,
        notch_filter=True,
    )
    if chunk_size == 500:
        assert result is None
        result = remover.process_chunk(
            chunk,
            notch_filter=True,
        )
        target = np.array(
            [
                -0.22238667,
                0.37627601,
                0.88600431,
                0.97673021,
                1.18691829,
                1.18447265,
                0.6083216,
                0.26692179,
                0.38309683,
                0.43958959,
                0.31412536,
                0.26004596,
                0.46831419,
                0.60709498,
                0.56431815,
                0.6611858,
                0.91477584,
                1.12054425,
                0.93760682,
                0.37931239,
            ]
        )

    else:
        target = np.array(
            [
                0.18889735,
                0.58929931,
                0.80590412,
                0.94609927,
                1.32930237,
                1.37830741,
                0.82241383,
                0.39520784,
                0.27406116,
                0.20612857,
                0.23057159,
                0.4081987,
                0.70639941,
                0.80982327,
                0.6132,
                0.4399927,
                0.53007848,
                0.70209814,
                0.60010648,
                0.26128982,
            ]
        )

    assert result.shape == (1, chunk_size)
    np.testing.assert_allclose(result[0, :20], target, atol=1e-5)

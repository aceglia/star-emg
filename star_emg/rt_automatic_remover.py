import numpy as np
import time

from star_emg.streaming_utils import DataStreamer
from biosiglive.streaming.utils import CircularBuffer
from star_emg.automatic_remover import ArtifactRemover
from star_emg.solution import Solution


class RtArtifactRemover(ArtifactRemover):
    """
    Class for real-time artifact removal.
    It is based on the ArtifactRemover class and it is designed to work in real-time.
    Convenient offline mode can be used to stream from a file.
    """

    def __init__(self, window_size=None, data=None, update_svd_every=1, **data_loader_kwargs):
        """
        Initialize the artifact remover.
        If data is provided, it will be used to initialize the data loader and the streamer. Otherwise, it will initialize the window size.

        Parameters
        ----------
        data: str or np.ndarray, optional
            Path to the data file or data array. If None, the class will be initialized without parameters.
        window_size: int, optional
            Size of the processing window. Default is 2000 samples.
        data_loader_kwargs: dict, optional
            The expected dict can contain the following keys:
            - delimiter: The delimiter used in the file format (e.g., "\t" for .txt files).
            - channel_names: A list of strings representing the names of the channels in the signal data.
            - data_rate: A float representing the data rate (sampling frequency) of the signal data.
            - data_window: A tuple representing the start and end indices of the data window to be loaded.
            - cutoff: The cutoff frequency for filtering the data.
            - order: The order of the filter to be applied to the data.
            - center: Wether to center the data before filtering.
            - signal_filter: Wether to apply filtering to the data after artifact removal.

        Returns
        -------
        None
        """
        super().__init__(None, **data_loader_kwargs)
        self.offline = False if data is None else True
        self.window_size = window_size
        self.output = None
        self.update_svd_every = update_svd_every

        if window_size is not None:
            self.buffer = CircularBuffer(1, window_size)
        self.solution = None
        self.last_rejected = None
        self.streamer = DataStreamer(data=data, offline=self.offline, **data_loader_kwargs)
        if self.streamer.init_data is not None:
            self.output = np.zeros_like(self.streamer.init_data)
            self.solution = Solution(data_rate=self.streamer.data_rate)
        self.idx = 0

    def get_init_signal(self) -> np.ndarray | None:
        """
        Return the signal loaded from a file if any.
        """
        if not self.offline:
            return None
        return self.streamer.init_data

    # TODO: Implement multiprocessing to process multiple channels like in the APP.
    def process_chunk(self, data: np.ndarray, **process_kwargs) -> np.ndarray | None:
        """
        This process a chunk of data. The internal buffer handle the processing window size so the user can provide only the chunck.
        It is meant to be called in stream settings. Only one channel can be process at the same time.
        If several channels needs to be processed, the user should use multiprocessing.
        Parameters
        ----------
        data: np.ndarray
            The data to process. Of the shape (n_samples).
        **process_kwargs: dict
            Additional parameters to pass to the processing function.

        Returns
        -------
        np.ndarray | None
            The processed data or None if the buffer is not full.
        """
        assert (
            data.ndim == 2
        ), "Only one channel can be processed at the same time. Please provide a 2D array of shape (1, n_channels)."
        if data.shape[0] != 1:
            raise ValueError(
                "Only one channel can be processed at the same time. Please provide a 2D array of shape (1, n_channels)."
            )
        if self.buffer is None and "window_size" not in process_kwargs:
            raise ValueError(
                "The buffer is not initialized. Please provide a window_size parameter to initialize the buffer."
            )
        elif self.buffer is not None:
            tmp_data, tmp_time = self.buffer.get()
            if "window_size" in process_kwargs and process_kwargs["window_size"] != self.buffer.size:
                self.buffer = CircularBuffer(1, process_kwargs["window_size"])
                if tmp_data is not None:
                    self.buffer.append(
                        x=tmp_data[-process_kwargs["window_size"] :], t=tmp_time[-process_kwargs["window_size"] :]
                    )

        self.buffer.append(data)
        if not self.buffer.full:
            return None
        else:
            self.buffer.append(data)
            data_tmp, _ = self.buffer.get()
            data_tmp = self.streamer.data_loader.apply_filtering(data_tmp, offline=False)
            if "notch_filter" in process_kwargs and process_kwargs["notch_filter"]:
                process_kwargs["offline"] = False
            process_kwargs["rejected_idx"] = None if self.idx % self.update_svd_every == 0 else self.last_rejected
            output = self._remove_artifact_from_windows(data_tmp, **process_kwargs)
            output = output[0]
            if self.offline:
                self.output[:, self.idx : self.idx + self.streamer.chunk_size] = output[-self.streamer.chunk_size :][
                    None
                ]
            return output[None, -data.shape[-1] :]

    def _stream_evaluation(self, data):
        raise NotImplementedError("Evaluation of the quality during stream is not implemented yet.")

        # data_weighted = np.concatenate([data[:, :, :-100], data[:, :, -100:] * 10], axis=-1)
        # self.quality_fct(raw=None, processed=data[0, 1], analysis=[0, 1, 2, 3])
        # quality = self.quality_fct(raw=data[0, 0], processed=None, analysis=[0, 1, 2, 3])
        # data_fft = np.abs(rfft(data_weighted[0, 1]))
        # self.quality_fct(raw=data_fft, processed=None, analysis=[1])
        # from star_emg.processing_utils import line_length, kurtosis_value, robust_max_percentile, median_frequency

        # np.cumsum(np.abs(rfft(data[0, 0])))[-1]
        # np.cumsum(np.abs(rfft(data[0, 1])))[-1]
        # np.sum(np.abs(np.diff(data[0, 1])), axis=-1)
        # line_length(data[0, 0])
        # line_length(data[0, 1])
        # spike_score(data[0, 0], 10)
        # spike_score(data[0, 1], 10)

        # def spike_score(x, k=20):
        #     threshold = np.percentile(np.abs(x), 95)
        #     score = np.mean(np.abs(x)[np.abs(x) > threshold])
        #     # topk = np.mean(ax[np.argpartition(ax, -k)[-k:]]) * k
        #     return score

        # kurtosis_value(data[0, 0], 50)
        # kurtosis_value(data[0, 1], 50)
        # robust_max_percentile(
        #     np.abs(rfft(data[0, 0]))[rfftfreq(600, 1 / self.streamer.data_loader.data_rate) < 150], 99.2
        # )
        # robust_max_percentile(
        #     np.abs(rfft(data[0, 1]))[rfftfreq(600, 1 / self.streamer.data_loader.data_rate) < 150], 99.9
        # )
        # median_frequency(data[0, 0], self.streamer.data_loader.data_rate)
        # median_frequency(data[0, 1], self.streamer.data_loader.data_rate)

        # line_length_fft = line_length(np.abs(rfft(data_weighted[0, 0])))

    def process_all_data(
        self, chunk_size=None, data_window=None, channel_idxs=None, update_svd_every=1, **process_kwargs
    ) -> Solution:
        """
        This function aim to process all data from a prerecccorded file.
        It is useful to evaluate the performance of the algorithm in a real time scenario, without the need of actually streaming real data.

        Parameters
        ----------
        chunk_size: int, optional
            Size of the chunk to process. Default is the chunk size of the data loader.
        data_window: tuple, optional
            Window of the data to process. Default is the whole data.
        channel_idxs: list, optional
            Indices of the channels to process. Default is all channels.
        update_svd_every: int, optional
            If one the SVD rows that will be removed will be updated at each chunk.
              If higher than one, the same rows will be removed for several chunks. Default is 1.
        **process_kwargs: dict, optional
            Additional parameters to pass to the processing function either notch filter or SVD based filter.

        Returns
        -------
        np.ndarray
            The processed data of the same shape than the input data.
        """
        if data_window is not None or channel_idxs is not None:
            data = self.get_init_signal()
            if not isinstance(channel_idxs, list):
                channel_idxs = [channel_idxs]
            data = data[channel_idxs, :] if channel_idxs is not None else data
            data = data[:, data_window[0] : data_window[1]] if data_window is not None else data
            self.streamer.data_loader.init_data = data
        self.output = np.zeros_like(self.streamer.init_data)
        self.streamer.chunk_size = chunk_size if chunk_size else self.streamer.chunk_size
        self.solution.data_rate = self.streamer.data_loader.data_rate
        self.update_svd_every = update_svd_every

        if not process_kwargs["notch_filter"]:
            fft_freqs = np.fft.rfftfreq(
                self.window_size - (process_kwargs["hankel_size"] - 1) * process_kwargs.get("hankel_delay", 1),
                1 / self.streamer.data_loader.data_rate,
            )
        else:
            fft_freqs = None
        process_kwargs["fft_freqs"] = fft_freqs
        process_kwargs["offline"] = False
        # self.quality = Quality(shape=data.shape)
        # self.quality_fct = partial(
        #     self.quality.compute_quality,
        #     ground_truth=None,
        #     channel=0,
        #     idx=0,
        #     fs=self.streamer.data_loader.data_rate,
        #     kw=20,
        #     fft_freqs=fft_freqs,
        # )
        tic = time.time()
        count = 0
        for i in range(self.streamer.num_chunks):
            _, data_chunk = self.streamer.get_next_chunk(self.streamer.chunk_size)
            if data_chunk is None:
                break
            self.process_chunk(data_chunk, **process_kwargs)
            self.idx += self.streamer.chunk_size
            count += 1

        if "notch_filter" in process_kwargs and process_kwargs["notch_filter"]:
            fct = self.solution.from_notch_filter
        else:
            fct = self.solution.from_signal_decomposition
        fct(
            [
                {
                    "data": self.streamer.data_loader.apply_filtering(self.streamer.init_data, offline=False)[None],
                    "output": self.output[None],
                    "u": None,
                    "v": None,
                    "s": None,
                    "unfiltered_signal": self.output[None],
                }
            ],
            (1, *self.streamer.init_data.shape),
        )

        print(
            "Total time to process data:",
            time.time() - tic,
            "its around: ",
            np.round(((time.time() - tic) / count) * 1000, 2),
            "ms",
            np.round(1 / ((time.time() - tic) / count), 2),
            "FPS",
        )
        return self.solution

    def _remove_artifact_from_windows(
        self,
        data,
        hankel_size=None,
        randomized=False,
        nb_principal_components=None,
        epsilon=None,
        notch_filter=False,
        quality_factor=30,
        frequency_peaks=30,
        first_peak=30,
        hankel_delay=1,
        freq_bounds=[10, 450],
        factor=0.5,
        fft_freqs=None,
        rejected_idx=None,
        data_rate=None,
        **kwargs,
    ):
        data_rate = data_rate if data_rate is not None else self.streamer.data_loader.data_rate
        data = data.flatten()
        if notch_filter:
            output = self._perform_notch_filter(
                frequency_peaks,
                data,
                data_rate,
                quality_factor,
                return_dict=False,
                first_peak=first_peak,
                offline=False,
            )
        else:
            output = self._perform_decomposition(
                data=data,
                hankel_size=hankel_size,
                randomized=randomized,
                filter=False,
                nb_principal_components=nb_principal_components,
                epsilon=epsilon,
                hankel_delay=hankel_delay,
                return_dict=False,
                data_rate=data_rate,
                freq_bounds=freq_bounds,
                factor=factor,
                fft_freqs=fft_freqs,
                rejected_idx=rejected_idx,
            )
            self.last_rejected = rejected_idx
        return output
        # if self.offline:
        #     self.output[:, 0, self.idx : self.idx + self.streamer.chunk_size] = output[-self.streamer.chunk_size :][
        #         None, :
        #     ]
        #     return self.output[:, 0, self.idx : self.idx + self.streamer.chunk_size]

    def get_solution(self):
        return self.solution

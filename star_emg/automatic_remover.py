import multiprocessing as mp
from typing import Union

import numpy as np
import scipy

from star_emg.io_utils import DataLoader
from star_emg.decomposition_utils import (
    compute_svd,
    remove_singular_values,
    get_signal_from_hankel,
)
from star_emg.solution import Solution
from star_emg.processing_utils import filter_data, merge_dict


class ArtifactRemover:
    def __init__(self, data: str = None, **data_loader_kwargs):
        """
        Initialize the ArtifactRemover object.

        Parameters
        ------------
        data : str, optional
            Path to the data file to load.
        data_loader_kwargs : dict
            Additional keyword arguments for the DataLoader.

        Returns
        --------
        None
        """
        self.ratio = None
        self.transformer = None
        self.is_txt_file = False
        self.is_data_loaded = False
        self.solution = None

        if data is not None:
            self.load_data(data, data_loader_kwargs)

    def load_data(self, data: str, data_loader_kwargs: dict):
        """
        Load data using the DataLoader.

        Parameters
        ------------
        data : str
            Path to the data file.
        data_loader_kwargs : dict
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
        --------
        None
        """
        self.data_loader = DataLoader(data, **data_loader_kwargs)
        self.is_data_loaded = True

    def process(
        self,
        hankel_size: int = 300,
        randomized: bool = False,
        post_filter: bool = False,
        threads: int = 1,
        epochs_idxs: Union[list, int] = None,
        channel_idxs: Union[list, int] = None,
        data_window: list = None,
        nb_principal_components: int = None,
        epsilon: float = None,
        notch_filter: bool = False,
        quality_factor: int = 150,
        frequency_peaks: float = 30,
        first_peak: float = None,
        hankel_delay: int = 1,
        process_window: int = None,
        freq_bounds: list = [10, 450],
        factor: float = 0.5,
    ) -> Solution:
        """
        Main processing function to remove artifacts from signals.

        Parameters
        ------------
        hankel_size : int
            The number of lines of the Hankel matrix.
        randomized : bool
            Whether to use randomized SVD.
        post_filter : bool
            Apply filtering after processing.
        threads : int
            Number of parallel processes.
        epochs_idxs : int or list, optional
            Batch indices to process.
        channel_idxs : int or list, optional
            Channel indices to process.
        data_window : list, optional
            Time window [start, end] for data selection.
        nb_principal_components : int, optional
            Number of principal components to retain.
        epsilon : float, optional
            Threshold for SVD truncation.
        notch_filter : bool
            Use notch filtering instead of decomposition.
        quality_factor : float
            Quality factor for notch filter.
        frequency_peaks : float
            Frequency of stimulation artifacts.
        first_peak : float, optional
            First peak frequency.
        hankel_delay : int
            Delay used in Hankel construction.
        process_window : int, optional
            Window size for processing.
        freq_bounds : list
            Frequency bounds for filtering.
        factor : float
            Scaling factor for singular values.

        Returns
        --------
        Solution
            Processed solution object.
        """
        self.solution = Solution(self.data_loader.data_rate)
        print("Processing signals, this might take a while...")
        data = self.data_loader.init_data
        if epochs_idxs and not self.data_loader.stack_epochs:
            if not isinstance(epochs_idxs, list):
                epochs_idxs = [epochs_idxs]
            data = data[epochs_idxs, ...]

        if channel_idxs:
            if not isinstance(channel_idxs, list):
                channel_idxs = [channel_idxs]
            data = data[:, channel_idxs, :]

        if data_window:
            data = data[..., data_window[0] : min(data.shape[-1], data_window[1])]
        process_window = process_window if process_window is not None else data.shape[-1]
        process_window = min(process_window, 10000)

        data = self.data_loader.flatten_data(data)
        data_rate = self.data_loader.data_rate
        list_results = []
        fft_freqs = np.fft.rfftfreq(process_window - (hankel_size - 1) * hankel_delay, 1 / data_rate)

        if threads == 1:
            for d in range(data.shape[0]):
                list_results.append(
                    self.perform_window_process(
                        frequency_peaks=frequency_peaks,
                        data=data[d],
                        fs=data_rate,
                        quality_factor=quality_factor,
                        first_peak=first_peak,
                        hankel_size=hankel_size,
                        randomized=randomized,
                        filter=post_filter,
                        nb_principal_components=nb_principal_components,
                        epsilon=epsilon,
                        hankel_delay=hankel_delay,
                        window=process_window,
                        data_rate=data_rate,
                        freq_bounds=freq_bounds,
                        factor=factor,
                        fft_freqs=fft_freqs,
                        notch_filter=notch_filter,
                    )
                )
        else:
            args = [
                (
                    data[b],
                    hankel_size,
                    randomized,
                    post_filter,
                    nb_principal_components,
                    epsilon,
                    notch_filter,
                    quality_factor,
                    frequency_peaks,
                    first_peak,
                    hankel_delay,
                    process_window,
                    data_rate,
                    freq_bounds,
                    factor,
                    fft_freqs,
                )
                for b in range(data.shape[0])
            ]
            ctx = mp.get_context("spawn")
            with ctx.Pool(processes=threads) as pool:
                list_results = pool.map(self.worker, args)

        fct = self.solution.from_notch_filter if notch_filter else self.solution.from_signal_decomposition
        fct(list_results, initial_data_shape=self.data_loader._data_shape)
        return self.solution

    @staticmethod
    def worker(args: tuple) -> dict | np.ndarray:
        """
        Worker function for multiprocessing.

        Parameters
        ------------
        args : tuple
            Arguments required for processing.

        Returns
        --------
        dict
            Result dictionary from processing.
        """
        (
            data,
            hankel_size,
            randomized,
            post_filter,
            nb_principal_components,
            epsilon,
            notch_filter,
            quality_factor,
            frequency_peaks,
            first_peak,
            hankel_delay,
            window,
            data_rate,
            freq_bounds,
            factor,
            fft_freqs,
        ) = args

        return ArtifactRemover().perform_window_process(
            frequency_peaks=frequency_peaks,
            data=data,
            fs=data_rate,
            quality_factor=quality_factor,
            first_peak=first_peak,
            hankel_size=hankel_size,
            randomized=randomized,
            filter=post_filter,
            nb_principal_components=nb_principal_components,
            n_reconstruct=None,
            epsilon=epsilon,
            offline=True,
            hankel_delay=hankel_delay,
            return_dict=True,
            window=window,
            data_rate=data_rate,
            freq_bounds=freq_bounds,
            factor=factor,
            fft_freqs=fft_freqs,
            notch_filter=notch_filter,
        )

    @staticmethod
    def perform_window_process(
        data, return_dict: bool = True, window: int = 10000, notch_filter: bool = False, **kwargs
    ) -> dict | np.ndarray:
        """
        Process data in a moving windows approach.

        Parameters
        ------------
        data : ndarray
            Input signal.
        return_dict : bool
            Return results as dictionary.
        window : int
            Window size.
        notch_filter : bool
            Use notch filtering.
        **kwargs: kwargs
            Additional arguments for processing

        Returns
        --------
        dict or ndarray
            Processed result.
        """
        fct = ArtifactRemover()._perform_notch_filter if notch_filter else ArtifactRemover()._perform_decomposition
        if return_dict:
            init_data = data.copy()

        count = 0
        len_d = len(data)
        break_at_end = False
        res = None

        while True:
            overlap = 0
            if count != 0:
                available_wind = min(len_d - count, window)
                if available_wind < window:
                    overlap = window - available_wind
                    data_tmp = np.concatenate((data[count - overlap : count], data[count : count + available_wind]))
                    break_at_end = True
                else:
                    data_tmp = data[count : count + window]
            else:
                data_tmp = data[count : count + window]

            res_tmp = fct(data=data_tmp, return_dict=return_dict, **kwargs)
            if notch_filter:
                res_tmp, a_list, b_list = res_tmp
                # kwargs.update({'b_list': b_list, 'a_list': a_list})
            else:
                res_tmp, rejected_idx = res_tmp
                # kwargs.update({'rejected_idx': rejected_idx})
            if return_dict:
                if overlap != 0:
                    res_tmp["output"] = res_tmp["output"][overlap:]
                res = merge_dict(res, res_tmp)
            else:
                res = np.concatenate((res, res_tmp[overlap:])) if res is not None else res_tmp

            count += window
            if break_at_end or count >= len_d:
                break

        if return_dict:
            res["data"] = init_data
        return res

    @staticmethod
    def _perform_decomposition(
        data: np.ndarray,
        hankel_size: int = None,
        randomized: bool = False,
        filter: bool = False,
        nb_principal_components: int = None,
        epsilon: float = None,
        hankel_delay: int = 1,
        return_dict: bool = True,
        data_rate: float = None,
        freq_bounds: list = [10, 450],
        factor: float = 0.5,
        fft_freqs: scipy.fft.rfftfreq = None,
        rejected_idx=None,
        **kwargs,
    ):
        """
        Perform SVD-based signal decomposition and artifact removal.

        Parameters
        ------------
        data : ndarray
            Input signal.
        hankel_size : int
            Number of rows in Hankel matrix.
        randomized : bool
            Use randomized SVD.
        filter : bool
            Apply post-filtering.
        nb_principal_components : int
            Number of principal components.
        epsilon : float
            Threshold for singular values.

        Returns
        --------
        dict or ndarray
            Processed signal or detailed results.
        """
        if return_dict:
            out_dict = {"data": data}

        # TODO: reuse hankel matrix if the signal didn't change and if the hankel size is the same
        u, s, v, hankel_matrix = compute_svd(
            data,
            n_rows=hankel_size,
            hankel=None,
            randomized=randomized,
            nb_principal_components=nb_principal_components,
            epsilon=epsilon,
            hankel_delay=hankel_delay,
        )

        if return_dict:
            out_dict.update({"s": s.copy()})

        s_reduced, v, u, rejected_idx = remove_singular_values(
            v,
            s,
            u,
            data_rate=data_rate,
            freq_bounds=freq_bounds,
            factor=factor,
            fft_freqs=fft_freqs,
            rejected_idx=rejected_idx,
        )
        # if n_reconstruct is not None:
        #     signal_reduced = get_signal_from_hankel(u @ (v[:, -n_reconstruct:] * s_reduced[:, None]), hankel_delay)
        # else:
        signal_reduced = get_signal_from_hankel((u * s_reduced) @ v, hankel_delay)

        if return_dict:
            out_dict["unfiltered_signal"] = signal_reduced.copy()

        if filter:
            signal_reduced = filter_data(signal_reduced[None, None, :])[0, 0, :]

        if return_dict:
            out_dict["output"] = signal_reduced
            out_dict["u"] = u
            out_dict["v"] = v
            out_dict["s_reduced"] = s_reduced
            out_dict["rejected_idx"] = rejected_idx
            return (out_dict, rejected_idx)
        else:
            return (signal_reduced, rejected_idx)

    @staticmethod
    def _perform_notch_filter(
        frequency_peaks: float,
        data: np.ndarray,
        fs: float = 2000,
        quality_factor: int = 150,
        return_dict: bool = True,
        first_peak: float = None,
        offline=True,
        b_list=None,
        a_list=None,
        **kwargs,
    ):
        """
        Apply notch filters at harmonic frequencies.

        Parameters
        ------------
        frequency_peaks : float
            Base frequency of artifacts.
        data : ndarray
            Input signal.
        fs : float
            Sampling frequency.
        quality_factor : float
            Quality factor of notch filters.
        first_peak: float
            The first frequency peak corresponding to the artifacts, needed if not the same than frequency peaks.

        Returns
        --------
        dict or ndarray
            Filtered signal.
        """
        if return_dict:
            out_dict = {"data": data.copy()}

        first_peak = frequency_peaks if first_peak is None else first_peak
        harmonics = [i * frequency_peaks + first_peak for i in range(0, int((fs / 2) / frequency_peaks) + 1)]
        if b_list is None or a_list is None:
            b_list, a_list = [], []
            recompute_filters = True
        for p, ha in enumerate(harmonics):
            try:
                if recompute_filters:
                    if not isinstance(fs, int):
                        fs = int(fs)
                    b, a = scipy.signal.iirnotch(ha, quality_factor, fs=fs)
                    b_list.append(b)
                    a_list.append(a)
                else:
                    b, a = b_list[p], a_list[p]

                if offline:
                    filtered_signal = (
                        scipy.signal.filtfilt(b, a, data) if p == 0 else scipy.signal.filtfilt(b, a, filtered_signal)
                    )
                else:
                    filtered_signal = (
                        scipy.signal.lfilter(b, a, data) if p == 0 else scipy.signal.lfilter(b, a, filtered_signal)
                    )
            except:
                continue

        if return_dict:
            out_dict.update(
                {
                    "unfiltered_signal": filtered_signal,
                    "output": filtered_signal,
                    "u": None,
                    "s": None,
                    "v": None,
                    "s_reduced": None,
                }
            )
            return (out_dict, b_list, a_list)
        else:
            return (filtered_signal, b_list, a_list)

    def get_process_signal(self, filtered=True):
        """
        Retrieve processed signal.

        Parameters
        ------------
        filtered : bool
            Return filtered or unfiltered signal.

        Returns
        --------
        ndarray
            Requested signal.
        """
        return self.solution.get("signal_reduced") if filtered else self.solution.get("unfiltered_signal")

    def get_init_signal(self):
        """
        Retrieve initial raw signal.

        Parameters
        ------------
        None

        Returns
        --------
        ndarray
            Initial data.
        """
        return self.data_loader.init_data

    def get_singular_values(self, processed=False):
        """
        Retrieve singular values.

        Parameters
        ------------
        processed : bool
            Return processed or original singular values.

        Returns
        --------
        ndarray
            Singular values.
        """
        return self.solution.get(["s"]) if not processed else self.solution.get(["s_reduced"])

    def get_data_rate(self):
        """
        Retrieve data sampling rate.

        Parameters
        ------------
        None

        Returns
        --------
        float
            Sampling frequency.
        """
        return self.data_loader.data_rate

    def get_channel_names(self):
        """
        Retrieve channel names.

        Parameters
        ------------
        None

        Returns
        --------
        list
            Channel names.
        """
        return self.data_loader.channel_names

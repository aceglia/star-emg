from functools import partial
import json
import os
import time
import zarr

from PyQt5.QtWidgets import QWidget, QSplitter, QVBoxLayout, QFileDialog
from PyQt5.QtCore import Qt, QThreadPool, QTimer

import numpy as np
import multiprocessing as mp
from scipy.fft import rfftfreq
import scipy.io as sio

from biosiglive.streaming.utils import CircularBuffer
from biosiglive import save
from .stream_utils import CustomQueue
from .remover_widget import StreamRemover, OfflineRemover
from ..rt_automatic_remover import RtArtifactRemover
from .display_options import StreamDisplayWidget, OfflineDisplayWidget
from .plot_widget import OfflinePlotter, StreamPlotter
from .gui_utils import ensure_list, Worker
from ..io_utils import export_csv, write_txt_file
from ..processing_utils import Quality
from ..solution import Solution
from .stream_widget import StreamWidget
from .save_utils import StreamSave
from .popup_utils import FilterDialog


class ProcessingWidget(QWidget):
    """
    Parent class for the processing widget, which will be used for both offline and online processing.
    It contains the common methods for both types of processing.
    """

    def __init__(self, parent=None):
        """
        Initialize the class with the parent widget.
        The parent widget is the main window of the application, it will be used to access the log box and the toolbar.
        """
        super().__init__()
        self.parent = parent
        self.stream_widget = None

    def _init_layout(self):
        """
        Initialize the layout of the widget.
        """
        right_panel = QWidget()
        right_layout = QVBoxLayout()

        right_layout.addWidget(self.remover_options.process_widgets)
        right_layout.addWidget(self.display_options)
        right_panel.setLayout(right_layout)
        right_panel.setMaximumWidth(500)

        splitter = QSplitter(Qt.Horizontal)

        splitter.addWidget(self.plot)
        splitter.addWidget(right_panel)
        self.setLayout(QVBoxLayout())
        if self.stream_widget is not None:
            self.layout().addWidget(self.stream_widget)
        self.layout().addWidget(splitter)

    def update_filter(self, name="notch"):
        """
        Update the filter and update the plot and display options. The filter name is passed as a parameter.
        Parameters:
        -----------
        name: str
            The name of the filter to update.
        Returns:
        --------
        None
        """
        self.remover_options.update_filter(name)
        self.plot.update_filter(name)
        self.plot.update_config_button(self.remover_options.get_current_config())
        processed = self.get_processed_channels()
        if processed is not None:
            self.display_options.display_processed_btn.setEnabled(True)
        else:
            self.display_options.display_processed_btn.setEnabled(False)
        self.remover_options.show_config("")

    def update_mouse_pos(self, pos):
        """
        Update the mouse position. It is used to display the value within a plot.

        Parameters:
        -----------
        pos: tuple
            The mouse position. It is used to display the value within a plot.
        Returns:
        --------
        None
        """
        self.display_options.update_mouse_pos(pos)

    def get_processed_channels(self):
        return self.remover_options.get_processed_channels()


class OfflineProcessingWidget(ProcessingWidget):
    def __init__(self, parent=None):
        """
        Initialize the offline processing widget based on the parent widget.
        Parameters:
        -----------
        parent: QMainWindow
            The main window of the application.
        Returns:
        --------
        None
        """
        super().__init__(parent)
        self.remover_options = OfflineRemover(self)
        self.display_options = OfflineDisplayWidget(self)
        self.display_options.disable()
        self.remover_options.disable()
        self.plot = OfflinePlotter(self)
        self._init_layout()
        self.clean_notch = None
        self.clean_svd = None
        self.process_file_path = None
        self.worker = None
        self.threadpool = QThreadPool()
        self.filter_dialog = None
        self.canceled = False
        self.quality_notch = Quality()
        self.quality_svd = Quality()
        self.file_path = None

    def update_frame(self, frame_number):
        """
        Update the epochs number and update the plot.
        """
        self.plot.update_frame(frame_number, update_time=True)
        self.plot.update_config_button(self.remover_options.get_current_config())
        self.remover_options.update_frame(frame_number)
        self.remover_options.show_config("")

    def process(self, **kwargs):
        """
        Process the data with the specified parameters.
        Parameters:
        -----------
        kwargs: dict
            The parameters for the processing.
        Returns:
        --------
        None
        """
        kwargs["epochs_idxs"] = ensure_list(self.display_options.frame_number)
        # self.remover_options.disable()
        self.parent.log_box.log("Processing data...")
        if kwargs["notch_filter"]:
            results, init_shape = self._thread_safe_process(
                self.remover_options.remover.perform_window_process,
                self.remover_options.remover.data_loader.init_data,
                self.remover_options.remover.data_loader.data_rate,
                **kwargs,
            )
            self._on_processing_done((results, init_shape), kwargs)
        else:
            worker = Worker(
                self._thread_safe_process,
                self.remover_options.remover.perform_window_process,
                self.remover_options.remover.data_loader.init_data,
                self.remover_options.remover.data_loader.data_rate,
                **kwargs,
            )
            worker.signals.finished.connect(lambda result: self._on_processing_done(result, kwargs))
            worker.signals.error.connect(lambda e: self.parent.log_box.log(f"Error while processing data: {e}"))
            self.threadpool.start(worker)

    def _on_processing_done(self, result, kwargs):
        """
        To do when the processing is done, mostly for the multiprocessing case.
        Parameters:
        -----------
        result: tuple
            The results of the processing.
        kwargs: dict
            The parameters for the processing.
        Returns:
        --------
        None
        """
        list_results, init_shape = result
        solution = Solution(self.remover_options.remover.data_loader.data_rate)
        fct = solution.from_notch_filter if kwargs["notch_filter"] else solution.from_signal_decomposition
        fct(list_results, initial_data_shape=init_shape)

        self.remover_options.remover.solution = solution
        self.update_processed_plot(kwargs["epochs_idxs"], kwargs["channel_idxs"])
        self.parent.log_box.log("Data processing done!")
        qual_fct = self.quality_notch.compute_quality if kwargs["notch_filter"] else self.quality_svd.compute_quality
        qual_fct(
            self.remover_options.get_data(kwargs["epochs_idxs"], kwargs["channel_idxs"]).astype(float),
            self.remover_options.get_cleaned_data().astype(float),
            ground_truth=None,
            fs=self.remover_options.get_rate(),
            idx=kwargs["epochs_idxs"],
            channel=kwargs["channel_idxs"],
        )
        self.remover_options.enable(all=True)
        self.display_options.display_processed_btn.setEnabled(True)
        self.parent.set_saved_ok(False)

    @staticmethod
    def _thread_safe_process(fct, data, data_rate, epochs_idxs, channel_idxs, process_window, **kwargs):
        """
        A thread-safe version of the processing function. It uses a queue to pass data between threads.
        Parameters:
        -
        fct: function
            The function to process the data.
        data: numpy.ndarray
            The data to process.
        data_rate: float
            The data rate.
        epochs_idxs: list
            The epochs indices to process.
        channel_idxs: list
            The channel indices to process.
        process_window: int
            The size of the processing window.
        **kwargs: dict
            The parameters for the processing.
        Returns:
        --------
        tuple
            The results of the processing.
        """
        if epochs_idxs:
            if not isinstance(epochs_idxs, list):
                epochs_idxs = [epochs_idxs]
            data = data[epochs_idxs, ...]

        if channel_idxs:
            if not isinstance(channel_idxs, list):
                channel_idxs = [channel_idxs]
            data = data[:, channel_idxs, :]

        # if kwargs['data_window']:
        #     data = data[..., kwargs['data_window'][0] : min(data.shape[-1], kwargs['data_window'][1])]
        process_window = process_window if process_window is not None else data.shape[-1]
        _init_data_shape = data.shape
        data = data.reshape(-1, data.shape[-1])
        list_results = []
        fft_freqs = np.fft.rfftfreq(
            process_window - (kwargs["hankel_size"] - 1) * kwargs["hankel_delay"], 1 / data_rate
        )
        for d in range(data.shape[0]):
            list_results.append(fct(data=data[d], fs=data_rate, fft_freqs=fft_freqs, window=process_window, **kwargs))
        return list_results, _init_data_shape

    def set_file(self, file_list, process_data_file=None, filtering_params=None):
        """
        Load the file and set the parameters.
        Parameters:
        -----------
        file_list: list or str
            The path to the file.
        process_data_file: str, optional
            The path to the file containing the processed data if loaded from a configuration file.
        filtering_params: dict, optional
            The parameters for the filtering if loaded from a configuration file.

        Returns:
        --------
        None

        """
        if filtering_params is None:
            self.filter_dialog = FilterDialog(self)
            if self.filter_dialog.exec_() == 0:
                self.canceled = True
                return
            else:
                self.canceled = False
                filtering_params = self.filter_dialog.get_filter_params()
        self.file_path = file_list
        self.remover_options.set_file(file_list, **filtering_params)
        if self.remover_options.remover is None:
            self.file_path = None
            return
        clean_svd, clean_notch = None, None
        for qual in [self.quality_notch, self.quality_svd]:
            qual.init_shape(self.remover_options.get_data().shape)
        if process_data_file is not None:
            clean_svd, clean_notch = self.get_process_data(process_data_file)
            clean = [clean_notch, clean_svd]
            init_data = self.remover_options.get_data()
            for q, qual_fct in enumerate([self.quality_notch.compute_quality, self.quality_svd.compute_quality]):
                qual_fct(init_data, clean[q], ground_truth=None, fs=self.remover_options.get_rate())

        self.display_options.set_file_params(
            self.remover_options.get_channels(), self.remover_options.get_all_data().shape[0]
        )
        self.plot.initialize_data(
            self.remover_options.get_all_data(),
            self.remover_options.get_channels(),
            self.remover_options.remover.data_loader.time,
            cleaned_notch=clean_notch,
            cleaned_svd=clean_svd,
        )
        self.parent.toolbar.enable_filter_menu()
        self.parent.toolbar.radio_svd_filter_button.setEnabled(False)
        self.parent.toolbar.radio_notch_filter_button.setEnabled(True)
        self.update_frame(0)
        self.update_filter("svd")

    def update_processed_plot(self, epochs_idxs, channel_idxs):
        """
        Update the plot with the processed data.
        Parameters:
        -----------
        epochs_idxs: list
            The epochs indices to process.
        channel_idxs: list
            The channel indices to process.
        Returns:
        --------
        None
        """
        cleaned_data = self.remover_options.get_cleaned_data()
        self.plot.update_data(
            cleaned_data, ensure_list(channel_idxs), ensure_list(epochs_idxs), data_type="clean", auto_range=False
        )
        self.plot.enable_config_button(channel_idxs)

    def save_file(self, path, ext=".bio"):
        """
        Save the processed and raw data to a file.
        Parameters:
        -----------
        path: str
            The path to the file.
        Returns:
        --------
        None
        """
        self.process_file_path = path
        dic_to_save = {
            "raw_data": self.plot.raw_data,
            "processed_data_svd": self.plot.clean_svd,
            "processed_data_notch": self.plot.clean_notch,
            "channels": self.remover_options.get_channels(),
            "rate": self.remover_options.get_rate(),
        }
        if ext == ".mat":
            sio.savemat(path, dic_to_save)
        elif ext == ".bio":
            save(dic_to_save, path)
        elif ext == ".txt":
            channels = self.remover_options.get_channels()
            suffix = ["", "_clean_svd", "_clean_notch"]
            channels_str = sum([[chan + s for chan in channels] for s in suffix], [])
            channels_str = ["time"] + channels_str
            time_vector = self.remover_options.remover.data_loader.time_vector
            write_txt_file(
                np.hstack((time_vector, self.plot.raw_data, self.plot.clean_svd, self.plot.clean_notch)),
                path=path,
                headers=channels_str,
            )
        # export_csv(path, **dic_to_save)
        # self.parent.log_box.log(
        #     "To use the processed file in signal you can import the txt file saved at " + path.replace(".mat", ".txt")
        # )
        self.parent.set_saved_ok(True)

    def load_config(self, path):
        """
        Load a configuration file generated from this app and set the files and parameters accordingly.

        Parameters:
        -----------
        path: str
            The path to the configuration file. Returns:
        --------
        None
        """
        if path == "":
            self.canceled = True
            return
        else:
            self.canceled = False
        with open(path, "r") as f:
            config_data = json.load(f)
        self.set_file(config_data["file_path"], config_data["process_file_path"], config_data["preprocessing_params"])
        self.remover_options.svd_options.load_config(config_data["filters_params_svd"])
        self.remover_options.notch_options.load_config(config_data["filters_params_notch"])

    def get_process_data(self, file_path):
        """
        Get the processed data from a file.
        Parameters:
        -----------
        file_path: str
            The path to the file.
        Returns:
        --------
        tuple
            The processed data. Returns:
        --------
        tuple
            The processed data. Returns:
        """
        if file_path is None:
            return
        data = sio.loadmat(file_path)
        return data["processed_data_svd"], data["processed_data_notch"]

    def save_config(self, path):
        """
        Save the configuration file in JSON format.

        Parameters:
        -----------
        path: str
            The path to the configuration file.

        Returns:
        --------
        None
        """
        config = {
            "mode": "offline",
            "file_path": self.file_path,
            "process_file_path": self.process_file_path,
            "preprocessing_params": self.remover_options.remover.data_loader.filtering_params,
            "filters_params_svd": self.remover_options.svd_options.process_arguments,
            "filters_params_notch": self.remover_options.notch_options.process_arguments,
        }
        with open(path, "w") as f:
            json.dump(config, f, indent=4)
        self.log_box.log(f"Configuration saved at: {path}")

    def _convert_quality_to_dict(self, quality):
        """ "
        Convert the quality results to a dictionary for display.
        Parameters:
        -----------
        quality: list
            The quality results.

        Returns:
        --------
        dict
            The quality results in a dictionary format.
        """
        dict_to_return = {
            "kurtosis": [quality[0][0], quality[1][0]],
            "Line Length": [quality[0][1], quality[1][1]],
            "Median frequency": [quality[0][2], quality[1][2]],
            "FFT Amplitude": [quality[0][3], quality[1][3]],
        }
        return {k: [np.round(float(v[0]), 3), np.round(float(v[1]), 3)] for k, v in dict_to_return.items()}

    def show_config(self, idx):
        """
        Show the configuration and quality results (if applicable) for the specified channel index.
        Parameters:
        -----------
        idx: int
            The channel index to show the configuration and quality results for. Returns:
        --------
        None
        """
        quality = self.quality_svd if self.remover_options.current_filter == "svd" else self.quality_notch
        frame = (
            self.remover_options.svd_options.current_frame
            if self.remover_options.current_filter == "svd"
            else self.remover_options.notch_options.current_frame
        )
        quality_dict = self._convert_quality_to_dict(quality.get_quality(frame, idx))
        config = self.remover_options.get_current_config(idx)
        channel = self.remover_options.get_channels()[idx]
        self.remover_options.show_config(
            f"Informations for channel {channel}:\n\n"
            + self._text_from_config(config)
            + self._text_from_quality(quality_dict)
        )

    @staticmethod
    def _text_from_config(config):
        text = ""
        if config is None:
            return text
        for name, value in config.items():
            text += name + ": " + str(value) + "\n"
        return text

    @staticmethod
    def _text_from_quality(quality):
        text = ""
        if quality is None:
            return text
        for key, value in quality.items():
            text += f"{key}: Raw: {value[0]}; Processed: {value[1]}\n"
        return text


class StreamProcessingWidget(ProcessingWidget):
    def __init__(self, parent=None, process_rate=60):
        """
        Initialize the stream processing widget based on the parent widget and the processing rate.

        Parameters:
        -----------
        process_rate: int
            The expected processing rate in Hz.

        Returns:
        --------
        None
        """
        super().__init__(parent)
        self.counter = 0
        self.last_processed_counter = 0
        self.process_rate = process_rate
        self.timer = QTimer()
        self.timer.timeout.connect(self.process)
        self.fft_freqs = None
        self.processing = False
        self._partial_fct = None
        self.last_n_arrived = 0
        self.tmp_processed = []
        self.last_processed_time = None
        self.streaming_data = False
        self.frame_counter = 0
        self.frames = {}
        self.once_updated = False
        self.last_n_processed = 0
        self.running = False
        self.last_seen = None
        self.long_process_warning = False
        self.queue_process = None
        self.queue_plot = None
        self.process_args_event = None
        self.queue_process_args = None
        self.process_buffer = None
        self.is_running_event = None
        self.channels_mapping = None
        self.n_process = mp.cpu_count() - 4 if mp.cpu_count() > 2 else 1
        self.remover_options = StreamRemover(self)
        self.display_options = StreamDisplayWidget(self, enable=False)
        self.plot = StreamPlotter(self, rate=min(process_rate, 30))
        self.stream_widget = StreamWidget(self)
        self.finish_saving = None
        self.filter_disabled = False
        self._init_layout()

    @staticmethod
    def process(
        process_number,
        queue_in,
        queue_out,
        process_args_event,
        queue_process_args,
        runing_event,
        buff_len,
        channels_idxs,
        acquisition_rate,
        queue_save=None,
        # frame_event=None,
    ):
        """
        Start a process which will be kept active during the stream to process data in a while loop maner. This function is called by the multiprocessing module, it is threadsafe.
        Parameters:
        -----------
        queue_in: multiprocessing.Queue
            The input queue for the data.
        queue_out: multiprocessing.Queue
            The output queue for the processed data.
        process_args_event: multiprocessing.Event
            The event to signal that the processing arguments have changed.
        queue_process_args: multiprocessing.Queue
            The queue to receive the processing arguments.
        runing_event: multiprocessing.Event
            The event to signal the process to start.
        buff_len: int
            The length of the buffer to store the data. It should be long enough to contain the processing window.
        channels_idxs: list
            The list of channel indices to process within this process.
        acquisition_rate: float
            The acquisition rate in Hz.

        Returns:
        --------
        None

        """
        channel_configs = None
        channel_configs_glob = {i: {} for i in channels_idxs}
        process_buffer = {i: CircularBuffer(1, buff_len) for i in channels_idxs}
        last_t = {i: -np.inf for i in channels_idxs}
        fct = partial(
            RtArtifactRemover()._remove_artifact_from_windows,
            return_dict=False,
            data_rate=acquisition_rate,
            offline=False,
        )
        runing_event.wait()
        while runing_event.is_set():
            data = queue_in.get_stacked()
            if data is None:
                time.sleep(0.001)
                continue
            idxs = list(data.keys())
            for ch in idxs:
                process_buffer[ch].append(data[ch][0], data[ch][1])

            params_to_send = {ch: None for ch in idxs}
            if process_args_event.is_set():
                channel_configs = queue_process_args.get(timeout=0.02)
                process_args_event.clear()
                for ch in idxs:
                    if ch in channel_configs["channel_idxs"]:
                        channel_configs_glob[ch] = channel_configs
                        params_to_send[ch] = channel_configs

            if channel_configs is not None:
                for ch in idxs:
                    if ch in channel_configs["channel_idxs"]:
                        channel_configs_glob[ch] = channel_configs
            for ch in idxs:
                buf_data, buf_t = process_buffer[ch].get()

                mask = buf_t > last_t[ch]
                if not np.any(mask):
                    continue

                t_new = buf_t[mask]
                d_new = buf_data[0][mask]  # (n_samples,)

                last_t[ch] = t_new[-1]

                config = channel_configs_glob[ch] if channel_configs_glob[ch] != {} else None

                if config is None:
                    queue_out[ch].put_nowait((d_new, t_new, ch))
                    StreamProcessingWidget._add_to_save(
                        queue_save,
                        t_new[0],
                        ch,
                        d_new,
                        d_new,
                        params_to_send[ch],
                    )
                    continue

                window = config.get("process_window", None)

                if window is None or buf_data.shape[-1] < window:
                    queue_out[ch].put_nowait((d_new, t_new, ch))
                    StreamProcessingWidget._add_to_save(
                        queue_save,
                        t_new[0],
                        ch,
                        d_new,
                        d_new,
                        params_to_send[ch],
                    )
                    continue

                res = StreamProcessingWidget._process_worker(
                    fct,
                    buf_data[0, -window:],  # last window
                    buf_t[-window:],
                    config,
                    ch,
                    len(t_new),
                )

                queue_out[ch].put_nowait(res)
                StreamProcessingWidget._add_to_save(
                    queue_save,
                    buf_t[-len(t_new)],
                    ch,
                    res[0][-len(t_new) :],
                    buf_data[0, -len(t_new) :],
                    params_to_send[ch],
                )
            # if all last t value are superior than the acquisition rate, we set ready
            # if all([t_new[-1] > acquisition_rate for t_new in last_t.values()]):
            #     frame_event.set_ready(process_number)

    @staticmethod
    def _add_to_save(queue, t0, ch, processed_data, raw_data, params_to_send):
        if queue is not None:
            data_dict = {
                "t0": t0,
                "ch": ch,
                "processed": processed_data,
                "raw": raw_data,
                "config": params_to_send,
            }
            queue.put_nowait(data_dict)

    @staticmethod
    def _process_worker(fct, data, t, process_args, idx, n_new_data):
        """
        Process the data using the provided function and arguments. This function is called by the multiprocessing module, it is threadsafe.
        Parameters:
        -----------
        fct: function
            The function to process the data.
        data: numpy.ndarray
            The data to process.
        t: numpy.ndarray
            The time corresponding to the data.
        process_args: dict
            The arguments for the processing function.
        idx: int
            The index of the channel being processed.
        n_new_data: int
            The number of new data points to return.

        Returns:
        --------
        tuple
            The processed data, the corresponding time, and the channel index.
        """
        res = fct(data=data, **process_args)
        return res[0][-n_new_data:], t[-n_new_data:], idx

    def init_stream(
        self, display_window, queue_process=None, is_running_event=None, channels_mapping=None, save_queue=None
    ):
        """
        Initialize the stream widget for processing.
        Parameters:
        -----------
        display_window: int
            The size of the display window in seconds.
        queue_process: list of multiprocessing.Queue
            The list of input queues for the data for each process.
        is_running_event: multiprocessing.Event
            The event to signal the processes to start.
        channels_mapping: list of list
            The list of channel indices for each process.
        save_queue: multiprocessing.Queue
            The queue to save the processed data.

        Returns:
        --------
        None
        """
        time = np.arange(0, display_window)
        self.zarr_ds = None
        self.display_window = display_window
        self.queue_process = queue_process
        self.is_running_event = is_running_event
        self.channels_mapping = channels_mapping
        self.n_process = self.n_process if len(self.channels) > 1 else 1
        self.n_process = min(self.n_process, int(np.ceil(len(self.channels) / 2)))
        self.queue_plot = {i: CustomQueue(name="plot") for i in range(len(self.channels))}
        self.process_args_event = [mp.Event() for _ in range(self.n_process)]
        self.queue_save = save_queue
        self.queue_process_args = [CustomQueue(name="process_args") for _ in range(self.n_process)]
        self.parent.log_box.log(f"Starting stream with {self.n_process} processes...")
        self.fft_freqs = rfftfreq(display_window, 1 / self.acquisition_rate)
        # self.frame_event = SharedEvent(n_process = len(self.queue_process))
        self.display_options.enable()
        self.display_options.set_file_params(self.channels)
        self.remover_options.new_stream(self.channels, self.process_args_event, self.queue_process_args)
        self.ready = mp.Event()
        self.plot.initialize_data(
            self.stream_widget.server.buffer,
            time,
            self.channels,
            display_window,
            self.queue_plot,
            self.is_running_event,
            self.channels_mapping,
        )
        self.parent.toolbar.enable_filter_menu()
        self.parent.toolbar.radio_svd_filter_button.setEnabled(False)
        self.parent.toolbar.radio_notch_filter_button.setEnabled(True)
        self.update_filter("svd")
        self.running = True
        self.display_options.set_button_on()
        self.finish_saving = mp.Event()
        if self.stream_widget.save:
            self.save_path = self.stream_widget.save_path
        else:
            self.save_path = None
        self.start_processing()

    def start_processing(self):
        """
        Start the sub-process for processing the data.
        """
        self.processes = []
        for i in range(len(self.queue_process)):
            queues_tmp = {ch: self.queue_plot[ch] for ch in self.channels_mapping[i]}
            p = mp.Process(
                target=StreamProcessingWidget.process,
                args=(
                    i,
                    self.queue_process[i],
                    queues_tmp,
                    self.process_args_event[i],
                    self.queue_process_args[i],
                    self.is_running_event,
                    self.display_window,
                    self.channels_mapping[i],
                    self.acquisition_rate,
                    self.queue_save,
                ),
                daemon=True,
            )
            self.processes.append(p)
        self.save_process = mp.Process(
            target=self.stream_widget.stream_save.run,
            args=(
                self.queue_save,
                self.channels,
                self.acquisition_rate,
                self.finish_saving,
            ),

            daemon=False,
        )
        self.save_process.start()
        for p in self.processes:
            p.start()

    @property
    def acquisition_rate(self):
        return self.stream_widget.acquisition_rate

    def load_config(self, path):
        """
        Load a configuration file generated from this app and set the files and parameters accordingly.

        Parameters:
        -----------
        """
        if path == "" or os.path.exists(path) == False:
            return
        with open(path, "r") as f:
            config_data = json.load(f)
        self.stream_widget.set_value_from_config(config_data)

    def save_config(self, path=None):
        """
        Save the configuration file in JSON format.

        Parameters:
        -----------
        path: str
            The path to the configuration file.

        Returns:
        --------
        None
        """
        if path is None:
            path = QFileDialog.getSaveFileName(self, "Save configuration file", "", "JSON files (*.json)")[0]
            if path == "":
                return

        config = {
            "mode": "stream",
            "address": self.stream_widget.address,
            "port": self.stream_widget.port,
            "acquisition_rate": self.stream_widget.acquisition_rate,
            "display_window": self.stream_widget.display_window,
            "channel_names": self.stream_widget.channels,
            "save_path": self.stream_widget.save_path,
            "increment_suffix": self.stream_widget.increment_suffix,
        }
        with open(path, "w") as f:
            json.dump(config, f, indent=4)

    @property
    def channels(self):
        return self.stream_widget.channels

    def stop_processing(self):
        """
        Stop the processing sub-processes.
        """
        for p in self.processes:
            p.terminate()
            p.join()
        if self.finish_saving is not None:
            self.finish_saving.wait()
            self.save_process.terminate()
            self.save_process.join()
            self.finish_saving = None
        self.processing = False

    def update_filter(self, name="svd"):
        """
        Update the filter and update the plot and process arguments accordingly.
        Parameters:
        -----------
        name: str
            The name of the filter to use. It should be either "svd" or "notch".

        Returns:
        --------
        None
        """
        self.remover_options.update_filter(name)
        self.plot.update_filter(name)
        processed = self.get_processed_channels()
        if processed is not None:
            self.display_options.display_processed_btn.setEnabled(True)
        else:
            self.display_options.display_processed_btn.setEnabled(False)
        self.remover_options.show_config("")

    def set_paused(self, paused):
        """
        Set the paused state of the plot widget.
        Parameters:
        -----------
        paused: bool
            The paused state of the plot widget.


        Returns:
        --------
        None
        """
        if paused:
            self.plot.pause_plot(True)
        else:
            self.plot.pause_plot(False)
        self.paused = paused

    def stop_recording(self):
        self.stop_processing()

    def update_frame(self, frame_number):
        """
        Update the epochs number and update the plot.
        Parameters:
        -----------
        frame_number: int
            The frame number to update the plot with.

        Returns:
        --------
        None
        """
        if os.path.exists(self.stream_widget.stream_save.save_path):
            if self.zarr_ds is None:
                try:
                    self.zarr_ds = zarr.open(self.stream_widget.stream_save.save_path, mode="r")
                except Exception as e:
                    self.parent.log_box.log(f"Error while loading the data set: {repr(e)}")
                    return

            if not self.filter_disabled:
                self.remover_options.disable()
                self.parent.toolbar.filter_menu.setEnabled(False)
                self.filter_disabled = True
            slice_tmp = slice(
                int(frame_number * self.stream_widget.display_window),
                int(frame_number * self.stream_widget.display_window) + self.stream_widget.display_window,
            )
            print("processing_widget - update_frame", slice_tmp)
            self.plot.plot_data(
                self.zarr_ds["signals"]["raw"][:, slice_tmp],
                self.zarr_ds["signals"]["processed"][:, slice_tmp],
                self.zarr_ds["signals"]["time"][slice_tmp],
            )

    def update_streaming_frame(self, frame_number):
        """
        Update the epochs number and update the plot.
        Parameters:
        -----------
        frame_number: int
            The frame number to update the plot with.

        Returns:
        --------
        None
        """
        self.display_options.append_frame_number(frame_number)

    def save_zarrds(self, path, save_path=None):
        """
        Save the data to a Zarr dataset.
        Parameters:
        -----------
        """
        if save_path is None:
            save_path = QFileDialog.getSaveFileName(self, "Save stream session", "", "BioSigLive File (*.bio)")[0]
            if save_path == "":
                return False
        try:
            if self.stream_widget is None:
                save_stream = StreamSave(self.stream_widget._tmp_path, save_path)
            else:
                save_stream = self.stream_widget.stream_save
            save_stream.convert_to_file(save_path, zarr_ds_path=path)
            self.parent.log_box.log(f"Data saved to {save_path}")
        except Exception as e:
            self.parent.log_box.log(f"Error while saving data: {repr(e)}")
            return True

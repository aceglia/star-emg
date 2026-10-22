import numpy as np
from PyQt5.QtWidgets import (
    QWidget,
    QStackedWidget,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QPlainTextEdit,
    QMessageBox,
)
from PyQt5.QtCore import Qt

from ..automatic_remover import ArtifactRemover
from ..rt_automatic_remover import RtArtifactRemover
from .gui_utils import ChannelSelecter, ensure_list


class OptionWidget(QWidget):
    """
    Parent class for the removal filter options.
    """

    def __init__(self, type: str, parent=None):
        """
        Initialize the OptionWidget.
        Parameters:
        -----------
        type: str
            The type of the filter. Can be 'notch' or 'svd'.
        parent: QWidget, optional
            The parent widget.
        """
        super().__init__()
        self.type = type
        self.channel_selecter = None
        self.parent = parent
        self.current_frame = 0
        self.channels = []
        self.event_log = None
        self.queue = None
        self.stream_mode = False
        self.init_process_args = {
            "notch_filter": self.type == "notch",
            "quality_factor": 80,
            "frequency_peaks": 30,
            "first_peak": None,
            "hankel_size": 500,
            "hankel_delay": 1,
            "process_window": 10000,
            "factor": 0.5,
            "freq_bounds": [10, 500],
            "channel_idxs": None,
        }
        self.short_process_args = {}
        self.process_arguments = {}

        self.process_button = QPushButton("Process")
        self.process_button.setEnabled(False)
        self.process_button.clicked.connect(self.update_params)

        self.popup_button = QPushButton("Select channels to process")
        self.popup_button.clicked.connect(self.on_popup_button_clicked)

        self.process_shown_button = QPushButton("Select channels to process")
        self.process_shown_button.clicked.connect(self.on_process_shown_button)

        self.cancel_button = QPushButton("Cancel processing")
        self.cancel_button.clicked.connect(self.on_cancel_button_clicked)

        self.text_config = QPlainTextEdit()
        self.text_config.setReadOnly(True)
        self.text_config.setStyleSheet("background-color: transparent;border: 0;")

        # self.wind_to_proc_label = QLabel('Chose which part of the data to process.\n' \
        # '1) If nothing is writen it will process the whole data.' \
        # '2) If you want to process only a part of the data, you can write the start and end frame separated by a commainside brackets (e.g. [200, 1200]).\n' \
        # 'You can put as many brackets you want to process different parts of the data, if brackets overlap (e.g. [200, 400], [500, 700], ...).\n' \
        # '3) If you want to process repetitive parts of the data you can write the delay between the start of the windows (in ms), the first frame of the first windows and the windows lenght (e.g. [20, 0, 1000]).\n' \
        # 'The windows will be stack to be process all together by the same parameters.')
        # self.window_to_process_input = QLabel()
        # self.window_to_process_input.textChanged.connect(self.update_data_windows)

    def init(self, channels: list, frames: int, streaming: bool = False, event_log=None, queue=None):
        """
        Initialize the option widget with the channels information and the number of frames.

        Parameters:
        -----------
        channels: list
            The list of channels names.
        frames: int
            The number of frames. Only for Offline
        streaming: bool, optional
            Whether the data is streaming or not.
        event_log: multiprocessing.Event, optional
            The event log for multiprocessing. Only for streaming mode.
        queue: multiprocessing.Queue, optional
            Queue to send the parameters to the main process. Only for streaming mode.
        """
        self.channels = channels
        self.n_frames = frames
        self.streaming = streaming
        self.event_log = event_log
        self.queue = queue
        if self.type == "svd":
            self.set_automatic_hsize(Qt.Checked)
        self.init_process_args = {
            "notch_filter": self.type == "notch",
            "quality_factor": 80,
            "frequency_peaks": 30,
            "first_peak": None,
            "hankel_size": 500,
            "hankel_delay": 1,
            "process_window": 10000,
            "factor": 0.5,
            "freq_bounds": [10, 500],
            "channel_idxs": None,
        }
        self.short_process_args = {}
        self.process_arguments = {}
        self.channel_selecter = None

    def get_options(self):
        return self.__dict__

    def set_options(self, **options):
        for key, value in options.items():
            setattr(self, key, value)

    def get_option(self, option):
        return getattr(self, option)

    def on_process_shown_button(self):
        channels = self.parent.get_displayed_channels()
        self.channel_selecter.set_channels(channels)
        self.on_draw_clicked()

    def on_popup_button_clicked(self):
        if self.channel_selecter is None:
            self.channel_selecter = ChannelSelecter(self, self.channels, for_display=False)
        self.channel_selecter.show()

    def on_draw_clicked(self):
        idxs = self.channel_selecter.get_channel_idxs()
        if len(idxs) == 0:
            QMessageBox.warning(None, "No channel selected", "Please select at least one channel to process.")
            return
        self.channel_idxs = idxs
        self.process_button.setEnabled(True)
        self.channel_selecter.quit()

    def update_params(self):
        """
        Update the parameters of the filter based on the widget entries.
        """
        process_arguments = self.get_process_arguments()
        # if not self._check_config(process_arguments):
        #     self.parent.log_box.log("WARNING: Invalid configuration. Please check the parameters.")
        #     return
        if len(ensure_list(process_arguments["channel_idxs"])) == 0:
            self.parent.parent.log_box.log("Unable to process data. Please select a channel to process first.")
            # self.process_button.setEnabled(False)
        if not self.streaming:
            self.parent.process(**process_arguments)
        else:
            [(queue.put_nowait(process_arguments), event.set()) for queue, event in zip(self.queue, self.event_log)]
            self.parent.parent.log_box.log(f"Processing data with parameters: {process_arguments}")
        list_empty = (
            [None] * len(self.channels)
            if f"Frame_{self.current_frame}" not in self.process_arguments
            else self.process_arguments[f"Frame_{self.current_frame}"]
        )
        channel_names = self.channel_selecter.get_channel_names()
        self.channel_idxs = self.channel_selecter.get_channel_idxs()
        process_arguments["channel_name"] = []
        for c, ch in enumerate(self.channel_idxs):
            process_arguments["channel_name"].append(channel_names[c])
            list_empty[ch] = process_arguments.copy()
        self.process_arguments[f"Frame_{self.current_frame}"] = list_empty

    def update_frame(self, frame_number: int = 0):
        self.current_frame = frame_number

    @staticmethod
    def _check_empty(value: str) -> str | None:
        """
        Check if the input is empty and return None if it is, otherwise return the input.
        """
        return None if value == "" else value

    def get_process_arguments(self, keys_item: dict = None, value_item: dict = None):
        """
        Get the processign arguments as a dictionary.
        Parameters:
        -----------
        keys_item: dict, optional
            The keys to use in the dictionary.
        value_item: dict, optional
            The values to use in the dictionary.

        Returns:
        --------
        dict: The processing arguments as a dictionary.
        """
        args_item = self.init_process_args if keys_item is None or len(keys_item) == 0 else keys_item
        dic_item = value_item if value_item is not None else self.__dict__
        params_dict = {}
        for name, value in args_item.items():
            if name == "hankel_size" and self.type == "svd":
                params_dict[name] = self.hankel_size
                continue
            params_dict[name] = self._check_empty(dic_item.get(name, args_item[name]))
        return params_dict

    def load_config(self, config):
        self.process_arguments = config

    def get_short_config(self, value_item=None):
        return self.get_process_arguments(self.short_process_args, value_item)

    def get_args_by_idx(self, idx: int | None = None):
        """
        Get the processing arguments for a specific channel index of for the current frame.
        Parameters:
        -----------
        idx: int | None, optional
            The channel index to use. If None, return the processing arguments for all channels.

        Returns:
        --------
        dict: The processing arguments for the specific channel index or for all channels.
        """
        if f"Frame_{self.current_frame}" not in self.process_arguments:
            return
        if idx is not None:
            process_argument = self.process_arguments[f"Frame_{self.current_frame}"][idx]
            if process_argument is None:
                return
            return self.get_short_config(value_item=process_argument)
        else:
            return self.process_arguments[f"Frame_{self.current_frame}"]

    def on_cancel_button_clicked(self):
        self.parent.cancel_processing()

    def disable(self):
        for item in self.findChildren(QWidget):
            item.setEnabled(False)

    def enable(self, all=False):
        for item in self.findChildren(QWidget):
            item.setEnabled(True)
        if not all:
            self.process_button.setEnabled(False)
        if self.type == "svd":
            self.input_hankel.setEnabled(not self.automatic_hsize)

    # def update_data_windows(self, text):
    #     windows = check_list(text)
    def show_config(self, text):
        self.text_config.setPlainText(text)

    def _check_config(self):
        return True


class NotchOptions(OptionWidget):
    """
    Widget for the notch filter options based on the OptionWidget.
    """

    def __init__(self, parent=None):
        """
        Initialize the NotchOptions widget with the OptionWidget with type: 'notch'.
        """
        super().__init__("notch", parent)
        self.process_window = 10000
        self.quality_factor = 80
        self.frequency_peaks = 30
        self.params_changed = True
        self.first_peak = ""
        self.init_process_args["process_window"] = self.process_window
        self._init_layout()
        self.short_process_args = {
            "quality_factor": 80,
            "frequency_peaks": 30,
            "process_window": self.process_window,
            "first_peak": None,
        }

    def _init_layout(self):
        """
        Initialize the layout for the NotchOptions widget.
        """
        layout = QGridLayout()
        layout.addWidget(QLabel("<b><font size=5>Notch Remover Options</font></b>"), 0, 0, 1, 2, Qt.AlignCenter)
        layout.addWidget(QLabel("Quality Factor:"), 1, 0, 1, 1)
        self.input_quality = QLineEdit()
        self.input_quality.setText(str(self.quality_factor))
        self.input_quality.textChanged.connect(self.set_quality_factor)
        layout.addWidget(self.input_quality, 1, 1, 1, 1)

        layout.addWidget(QLabel("Stimulation frequency:"), 2, 0, 1, 1)
        self.input_freq = QLineEdit()
        self.input_freq.setText(str(self.frequency_peaks))
        self.input_freq.textChanged.connect(self.set_frequency_peaks)
        layout.addWidget(self.input_freq, 2, 1, 1, 1)

        layout.addWidget(QLabel("First peak frequency:"), 3, 0, 1, 1)
        self.input_first = QLineEdit()
        self.input_first.setText(str(self.first_peak))
        self.input_first.textChanged.connect(self.set_first_peak)
        layout.addWidget(self.input_first, 3, 1, 1, 1)

        self.input_wind = QLineEdit()
        self.input_wind.setText(str(self.process_window))
        self.input_wind.textChanged.connect(self.set_process_window)
        layout.addWidget(QLabel("Window length:"), 4, 0, 1, 1)
        layout.addWidget(self.input_wind, 5, 1, 1, 2)
        # layout.addWidget(self.wind_to_proc_label, 6, 0, 1, 2)
        # layout.addWidget(self.window_to_process_input, 6, 0, 1, 2)
        layout.addWidget(self.popup_button, 6, 0, 1, 2)
        # layout.addWidget(self.process_shown_button, 5, 1, 1, 1)
        layout.addWidget(self.process_button, 7, 0, 1, 2)
        layout.addWidget(self.text_config, 8, 0, 1, 2)
        layout.setAlignment(Qt.AlignTop)
        self.setLayout(layout)

    def set_quality_factor(self, text: str):
        if text == "":
            return
        self.quality_factor = float(text)

    def set_frequency_peaks(self, text: str):
        if text == "":
            return
        self.frequency_peaks = float(text)

    def set_first_peak(self, text: str):
        if text == "":
            return
        self.first_peak = float(text)

    def set_process_window(self, text: str):
        if text == "":
            return
        self.process_window = int(text)


class SVDOptions(OptionWidget):
    """
    Initialize the SVDOptions widget with the OptionWidget with type: 'svd'.
    """

    def __init__(self, parent=None):
        super().__init__("svd", parent)
        self.hankel_delay = 1
        self._hankel_size = 500
        self.process_window = 5000
        self.overlap = 0
        self.nb_principal_components = None
        self.factor = 0.35
        self.freq_bounds = [10, 300]
        self.automatic_hsize = True
        self.init_process_args["process_window"] = self.process_window
        self._init_layout()
        self.short_process_args = {
            "hankel_size": 500,
            "hankel_delay": 1,
            "process_window": self.process_window,
            "factor": 0.5,
            "freq_bounds": [10, 500],
        }

    def _init_layout(self):
        """
        Initialize the layout for the SVDOptions widget.
        """
        layout = QGridLayout()
        layout.addWidget(QLabel("<b><font size=5>SVD Remover Options</font></b>"), 0, 0, 1, 3, Qt.AlignCenter)
        layout.addWidget(QLabel("Window length:"), 1, 0, 1, 2)

        self.input_wind = QLineEdit()
        self.input_wind.setText(str(self.process_window))
        self.input_wind.textChanged.connect(self.set_process_window)
        layout.addWidget(self.input_wind, 1, 1, 1, 1)

        layout.addWidget(QLabel("Hankel size:"), 2, 0, 1, 1)
        self.input_hankel = QLineEdit()
        self.input_hankel.setText(str(self.hankel_size))
        self.input_hankel.textChanged.connect(self.set_hankel_size)
        self.check_auto_size = QCheckBox("Automatic size")
        self.check_auto_size.setChecked(self.automatic_hsize)
        self.check_auto_size.stateChanged.connect(self.set_automatic_hsize)
        self.set_automatic_hsize(Qt.Checked, update=False)
        layout.addWidget(self.input_hankel, 2, 1, 1, 1)
        layout.addWidget(self.check_auto_size, 2, 2, 1, 1)

        layout.addWidget(QLabel("Hankel delay:"), 3, 0, 1, 1)
        self.input_delay = QLineEdit()
        self.input_delay.setText(str(self.hankel_delay))
        self.input_delay.textChanged.connect(self.set_hankel_delay)
        layout.addWidget(self.input_delay, 3, 1, 1, 1)

        layout.addWidget(QLabel("Threshold:"), 4, 0, 1, 2)
        self.input_factor = QLineEdit()
        self.input_factor.setText(str(self.factor))
        self.input_factor.textChanged.connect(self.set_factor)
        layout.addWidget(self.input_factor, 4, 1, 1, 1)

        layout.addWidget(QLabel("Frequency bounds:"), 5, 0, 1, 1)
        self.input_low_freq = QLineEdit()
        self.input_low_freq.setText(str(self.freq_bounds[0]))
        self.input_low_freq.textChanged.connect(self.set_low_freq)
        layout.addWidget(self.input_low_freq, 5, 1, 1, 1)

        self.input_high_freq = QLineEdit()
        self.input_high_freq.setText(str(self.freq_bounds[1]))
        self.input_high_freq.textChanged.connect(self.set_high_freq)
        layout.addWidget(self.input_high_freq, 5, 2, 1, 1)

        # layout.addWidget(self.wind_to_proc_label, 5, 0, 1, 2)
        # layout.addWidget(self.window_to_process_input, 6, 0, 1, 2)
        layout.addWidget(self.popup_button, 6, 0, 1, 3)
        layout.addWidget(self.process_button, 7, 0, 1, 3)
        layout.addWidget(self.text_config, 8, 0, 1, 3)

        layout.setAlignment(Qt.AlignTop)
        self.setLayout(layout)

    def set_process_window(self, text: str):
        if text == "":
            return
        self.process_window = int(text)
        if self.automatic_hsize:
            self.set_automatic_hsize(Qt.Checked)

    def set_hankel_size(self, text: str):
        if text == "":
            return
        self._hankel_size = int(text)

    def set_factor(self, text: str):
        if text == "":
            return
        mult = 1
        if text.startswith("-"):
            mult = -1
            text = text[1:]
        self.factor = mult * float(text)

    def set_low_freq(self, text: str):
        if text == "":
            return
        self.freq_bounds[0] = int(text)

    def set_high_freq(self, text: str):
        if text == "":
            return
        self.freq_bounds[1] = int(text)

    def set_hankel_delay(self, text: str):
        if text == "":
            return
        self.hankel_delay = int(text)
        if self.automatic_hsize:
            self.set_automatic_hsize(Qt.Checked)

    def set_automatic_hsize(self, state, update=True):
        """
        Set the automatic hankel size based on the window length and hankel delay.
        Parameters:
        -----------
        state: Qt.Checked | Qt.Unchecked
            The state of the checkbox.
        """
        self.automatic_hsize = state == Qt.Checked
        self.input_hankel.setEnabled(not self.automatic_hsize)
        self.input_hankel.setText(str(self.hankel_size_from_window()))

    def hankel_size_from_window(self, factor: int = 8) -> int:
        """
        Function that compute the hankel size based on the window length and hankel delay. The factor is hard coded and is set to 8.

        Parameters:
        -----------
        factor: int, optional
            The factor to use in the computation. Default is 8.
        Returns:
        --------
        int: The hankel size.
        """
        self.process_window = int(self.input_wind.text())
        return max(int((self.process_window / factor) / self.hankel_delay), 1)

    @property
    def hankel_size(self):
        if self.automatic_hsize:
            return self.hankel_size_from_window()
        return self._hankel_size

    def _check_config(self, process_arguments):
        return True


class Remover:
    """
    Parent class for the remover class.
    """

    def __init__(self, parent=None):
        self.remover = None
        self.parent = parent
        self.is_initialized = False
        self.is_results = False
        self.sol_notch = False
        self.sol_svd = False
        self.notch_options = NotchOptions(self.parent)
        self.svd_options = SVDOptions(self.parent)
        self.process_widgets = QStackedWidget()
        self.process_widgets.addWidget(self.notch_options)
        self.process_widgets.addWidget(self.svd_options)
        self.process_widgets.setCurrentIndex(1)
        self.current_filter = "notch"
        self.filter_list = ["notch", "svd"]

    def update_filter(self, name):
        """
        Change the widget according to the selected filter.
        """
        self.current_filter = name
        self.process_widgets.setCurrentIndex(self.filter_list.index(name))
        filter = self.svd_options if self.current_filter == "svd" else self.notch_options
        if filter.channel_selecter is None:
            filter.process_button.setEnabled(False)

    def get_current_config(self, idx: int = None):
        """
        Get the current configuration for the selected filter.
        Parameters:
        -----------
        idx: int, optional
            The index of the configuration to retrieve. Default is None.
        Returns:
        --------
        dict: The current configuration.
        """
        filter = self.notch_options if self.current_filter == "notch" else self.svd_options
        return filter.get_args_by_idx(idx)

    def disable(self):
        self.svd_options.disable()
        self.notch_options.disable()

    def enable(self, all=False):
        self.svd_options.enable(all)
        self.notch_options.enable(all)

    def get_processed_channels(self):
        """
        Get the list of channels that have been processed.
        """
        config = self.get_current_config()
        if config is None:
            return
        return [i for i, conf in enumerate(config) if conf is not None]

    def get_displayed_channels(self):
        """
        Get the list of channels that are currently displayed.
        """
        return self.parent.display_options.channel_selecter.get_channel_idxs()

    def show_config(self, text):
        options = self.notch_options if self.current_filter == "notch" else self.svd_options
        options.show_config(text)

    def get_process_window(self):
        filter = self.svd_options if self.current_filter == "svd" else self.notch_options
        return filter.process_window


class OfflineRemover(Remover):
    """
    Class for the remover in offline mode. It inherits from the Remover class and is used to process the data in offline mode.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.processed_data = False

    def _init_remover(self, path_file: str, **kwargs):
        """
        Inititialize the remover with the data from the file.

        Parameters:
        -----------
        path_file: str
             The path to the data file.
        kwargs: dict
            Additional keyword arguments to pass to the ArtifactRemover.

        Returns:
        --------
        None
        """
        self.remover = ArtifactRemover(data=path_file, **kwargs)
        loaded = self.remover.data_loader.loaded_data
        if "preprocessing" in loaded:
            preprocessing = loaded["preprocessing"]
            same = [1 if preprocessing[key] == kwargs[key] else 0 for key in preprocessing.keys() if key != "data_rate"]
            if not any(same):
                kwargs = {key: preprocessing[key] for key in preprocessing.keys()}
                kwargs["data_rate"] = loaded["data_rate"]
                self.parent.parent.log_box.log(
                    f"WARNING: The data was preprocessed with different parameters than the ones you provided. Falling back to {kwargs}."
                )
        if "processed_data_notch" in loaded:
            if loaded["processed_data_notch"] is not None or loaded["processed_data_svd"] is not None:
                self.processed_data = True
        data_shape = self.remover.data_loader.init_data.shape
        window = 25_000
        total_epochs = data_shape[0]
        if data_shape[-1] > window and data_shape[0] == 1:
            total_epochs = int(np.ceil(data_shape[-1] / 25000))
            rate = self.remover.data_loader.data_rate
            epochs_duration = window * (1 / rate)
            self.parent.parent.show_split_windows(
                f"The data has {data_shape[-1]} points per channel. This may slowdown the programm."
                f"If you chose 'yes' your file will be splitted in {total_epochs} of {epochs_duration:.2f}s duration Frames. If the last frame is not full, it will be filled with 0."
            )
        if self.parent.parent._split == "&Yes":
            self._split_data(window, total_epochs, rate)
            if self.processed_data:
                self.remover.data_loader.loaded_data = self._split_loaded_data(loaded, window, total_epochs)
            self.parent.parent._split = "&No"
        elif self.parent.parent._split == "Cancel":
            self.remover = None

        for options in [self.notch_options, self.svd_options]:
            options.init(self.remover.data_loader.channel_names, self.remover.data_loader.init_data.shape[0])

    def _split_data(self, window: int, epochs: int, rate: float):
        """
        Split the data if the data is longer than 25000 points per channel as the processing would be too slow.
        Parameters:
        -----------
        window: int
            The window size to use for the processing.
        epochs: int
            The number of epochs to process.
        rate: float
            The data rate of the data.

        Returns:
        --------
        None
        """
        data = np.swapaxes(self.remover.data_loader.init_data, 0, 1)
        full_mat = np.zeros((data.shape[0], 1, int(epochs * window)))
        full_mat[..., : data.shape[-1]] = data
        full_mat = full_mat.reshape(data.shape[0], epochs, window)
        self.remover.data_loader.init_data = np.swapaxes(full_mat, 0, 1)
        time = np.linspace(0, int(epochs * window) / rate, int(epochs * window))
        self.remover.data_loader.time = time.reshape((epochs, window))

    def _split_loaded_data(self, loaded_data: dict, window: int, epochs: int):
        """
        Split the loaded data if the data is longer than 25000 points per channel as the processing would be too slow.
        Parameters:
        -----------
        loaded_data: dict
            The loaded data from the file.
        window: int
            The window size to use for the processing.
        epochs: int
            The number of epochs to process.

        Returns:
        --------
        None
        """
        for key in ["processed_data_notch", "processed_data_svd"]:
            if key in loaded_data and loaded_data[key] is not None:
                data = np.swapaxes(loaded_data[key], 0, 1)
                full_mat = np.zeros((data.shape[0], 1, int(epochs * window)))
                full_mat[..., : data.shape[-1]] = data
                full_mat = full_mat.reshape(data.shape[0], epochs, window)
                loaded_data[key] = np.swapaxes(full_mat, 0, 1)
        return loaded_data

    def set_file(
        self,
        file_path: str,
        data_rate: float = None,
        signal_filter: bool = False,
        center: bool = True,
        cutoff: list = [10, 450],
        order: int = 2,
    ):
        """
        Set the file to be processed.
        Parameters:
        -----------
        file_path: str
            The path to the data file.
        data_rate: float, optional
            The data rate of the data. If None, the data rate will be set to the default value.
        signal_filter: bool, optional
            Whether to apply a signal filter to the data. If None, the signal filter will be set to the default value.
        center: bool, optional
            Whether to center the data. If None, the data will be centered to the default value.
        cutoff: list, optional
            The cutoff frequencies for the signal filter. If None, the cutoff frequencies will be set to the default value.
        order: int, optional
            The order of the signal filter. If None, the order will be set to the default value.

        Returns:
        --------
        None
        """
        self.process_widgets.setCurrentIndex(1)
        self.current_filter = "svd"
        # for options in [self.notch_options, self.svd_options]:
        #     options.__init__(self.parent)
        self._init_remover(
            file_path, data_rate=data_rate, signal_filter=signal_filter, center=center, cutoff=cutoff, order=order
        )
        self.enable()

    def get_all_data(self):
        return self.remover.data_loader.init_data

    def get_rate(self):
        return self.remover.data_loader.data_rate

    def get_channels(self):
        return self.remover.data_loader.channel_names

    def set_channels(self, channels: list):
        """
        Set the channels to be processed.
        Parameters:
        -----------
        channels: list
            The list of channels to be processed.

        Returns:
        --------
        None
        """
        self.remover.data_loader.channel_names = channels
        for options in [self.notch_options, self.svd_options]:
            options.channels = channels
            if options.channel_selecter is not None:
                options.channel_selecter.set_channels(channels)

    def get_data(self, epochs: list = None, channel: list = None) -> np.ndarray:
        """
        Return the initial data for the specified epochs and channel. If epochs is None, return all epochs. If channel is None, return all channels.
        """
        data = self.remover.data_loader.init_data
        if epochs is not None:
            data = data[epochs, :, :]
        if channel is not None:
            data = data[:, channel, :]
        return data

    def update_frame(self, frame_number):
        for option in [self.notch_options, self.svd_options]:
            option.update_frame(frame_number)

    def get_cleaned_data(self, epochs: list = None, channel: list = None, data=None) -> np.ndarray:
        """
        Return the cleaned data for the specified epochs and channel. If epochs is None, return all epochs. If channel is None, return all channels.
        """
        data = self.remover.solution.output if data is None else data
        if epochs is not None:
            data = data[epochs, :, :]
        if channel is not None:
            data = data[:, channel, :]
        return data


class StreamRemover(Remover):
    """
    Class for the remover in stream mode. It inherits from the Remover class and is used to process the data in stream mode.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._adjust_value_for_stream()
        self.remover = None

    def _adjust_value_for_stream(self):
        """
        Adjust the values from the parent class to fit the stream mode.
        """
        self.svd_options.init_process_args["process_window"] = 500
        self.svd_options.init_process_args["hankel_size"] = 100
        self.notch_options.init_process_args["process_window"] = 2000
        self.svd_options.input_hankel.setText(str(self.svd_options.init_process_args["hankel_size"]))
        self.svd_options.input_wind.setText(str(self.svd_options.init_process_args["process_window"]))
        self.notch_options.input_wind.setText(str(self.notch_options.init_process_args["process_window"]))

    def new_stream(self, channels: list, events: list, queue_args: any):
        """
        Create a RtArtifactRemover for the new stream and initialize the options widgets with the channels information and the event log and queue for multiprocessing.

        Parameters:
        -----------
        channels: list
            The list of channels names.
        events: list
            The list of events.
        queue_args: multiprocessing.Queue
            The queue for multiprocessing.

        Returns:
        --------
        None
        """
        self.process_widgets.setCurrentIndex(1)
        self.current_filter = "svd"
        self.channels = channels
        self.remover = RtArtifactRemover()
        self.enable()
        for options in [self.notch_options, self.svd_options]:
            options.init(channels, len(channels), streaming=True, event_log=events, queue=queue_args)

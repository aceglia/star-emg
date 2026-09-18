from pathlib import Path
import threading

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLineEdit, QDialog, QLabel, QCheckBox
from PyQt5.QtCore import QObject, pyqtSignal

import numpy as np
import multiprocessing as mp
from ..processing_utils import Quality
from .popup_utils import ChannelsPopup, SaveStreamPopup
from .stream_utils import CustomQueue
from .save_utils import StreamSave
from .ced_talker.port_reader import PacketReader
import asyncio


class Bridge(QObject):
    data_received = pyqtSignal(object)


class StreamWidget(QWidget):
    """
    Class that handles the stream widget in the GUI.
    """
    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.channels = None
        self.channels_setter = None
        self.max_height = 40
        self.setFixedHeight(self.max_height)
        self.quality = Quality()
        self._init_layout()
        self.bridge = Bridge()
        self.n_process = parent.n_process
        self.paused = False
        self.save = False
        self.save_popup = None
        self.stream_save = None
        self.save_path = None
        self.use_zarr = True
        self.compress = True
        self.compression_level = 3

    def task(self, d, t):
        """
        The task that is called within the server after each new data received.
        It put the data into the queue for each channel to be processed by the main process and displayed in the GUI.
        """
        if not self.is_running_event.is_set():
            self.is_running_event.set()
        print(t[0])
        [self.queue_process[i].put_nowait((d[chan], t, chan)) for i, chan in self.channels_mapping.items()]

    def _init_layout(self):
        self.play_button = QPushButton("Play")
        self.play_button.setEnabled(False)
        self.play_button.clicked.connect(self._play)
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop)
        self.pause_button = QPushButton("Pause")
        self.pause_button.setEnabled(False)
        self.pause_button.clicked.connect(self._pause)

        self.adress_in = QLineEdit()
        self.adress_in.setText("127.0.0.1")
        self.port_in = QLineEdit()
        self.port_in.setText("COM110")
        self.ac_rate_in = QLineEdit()
        self.ac_rate_in.setText("2000")
        self.set_channels_button = QPushButton("Set Channels")
        self.set_channels_button.clicked.connect(self._set_channels)
        self.display_wind_in = QLineEdit()
        self.display_wind_in.setText("5")

        self.layout = QHBoxLayout()
        self.layout.addWidget(self.play_button)
        self.layout.addWidget(self.stop_button)
        self.layout.addWidget(self.pause_button)
        label = QLabel("Address:")
        label.setMaximumHeight(self.max_height)
        self.layout.addWidget(label)
        self.layout.addWidget(self.adress_in)
        label = QLabel("Port:")
        label.setMaximumHeight(self.max_height)
        self.layout.addWidget(label)
        self.layout.addWidget(self.port_in)
        label = QLabel("Acquisition rate:")
        label.setMaximumHeight(self.max_height)
        self.layout.addWidget(label)
        self.layout.addWidget(self.ac_rate_in)
        self.layout.addWidget(self.set_channels_button)
        self.layout.addWidget(QLabel("Display last (s):"))
        self.layout.addWidget(self.display_wind_in)

        # add checkbox to save the stream
        self.save_checkbox = QCheckBox("Save")
        self.save_checkbox.setCheckable(True)
        self.save_checkbox.clicked.connect(self._save_checkbox)
        self.layout.addWidget(self.save_checkbox)

        self.save_popup_button = QPushButton("Save options")
        self.save_popup_button.clicked.connect(self._save_popup)
        self.layout.addWidget(self.save_popup_button)

        self.setLayout(self.layout)

    def _play(self):
        """
        Start the stream.
        """
        self.parent.parent._check_for_unsaved_work()
        self.parent.parent.toolbar.save_button.setEnabled(False)
        self.parent.parent.toolbar.save_as_button.setEnabled(False)
        self._change_widget_state(not_playing=False)
        if not self.paused:
            if self.save_popup is not None:
                self._get_save_options()
            self.stream_save = StreamSave(
                use_zarr=self.use_zarr, compress=self.compress, compression_level=self.compression_level
            )
            save_queue = CustomQueue(name="save_queue")
            # self.parent.parent.log_box.log(f"Saving stream to: {self._tmp_path}")
            self.parent.parent.log_box.log(
                f"Launching the stream at: {self.address}:{self.port} waiting for a client..."
            )
            self.n_process = self.n_process if len(self.channels) > 1 else 1
            self.n_process = min(self.n_process, int(np.ceil(len(self.channels) / 2)))
            self.channels_mapping = {i: [] for i in range(self.n_process)}
            for i in range(len(self.channels)):
                self.channels_mapping[i % self.n_process].append(i)
            self.queue_process = [CustomQueue() for _ in range(self.n_process)]
            self.is_running_event = mp.Event()

            self.play_thread = threading.Thread(target=self._run_asyncio, daemon=True)
            self.play_thread.start()
            self.parent.init_stream(
                self.display_window,
                queue_process=self.queue_process,
                is_running_event=self.is_running_event,
                channels_mapping=self.channels_mapping,
                save_queue=save_queue,
            )
        else:
            self.parent.set_paused(False)
            self.paused = False

    def _run_asyncio(self):
        """
        Function to run the asyncio server. 
        """
        # self.server = AsyncTCPServer(self.address, self.port, buffer_length=self.display_window)
        # self.server.init_buffer(len(self.channels), dt=1 / self.acquisition_rate)
        # asyncio.run(self.server.start(task=self.task))
        self.server = PacketReader(self.port_in.text(), n_channels=len(self.channels), dt=1 / self.acquisition_rate, buff_size=self.display_window)
        self.server.task = self.task
        asyncio.run(self.server.receiver())

    def _save_checkbox(self):
        """
        Function to handle the save checkbox.
        """
        self.save = self.save_checkbox.isChecked()
        if self.save_popup is None:
            self._save_popup()

    def _save_popup(self):
        """
        Function to handle the save popup.
        """
        if self.save_popup is None:
            self.save_popup = SaveStreamPopup()

        if self.save_popup.exec_() == QDialog.Accepted:
            self._get_save_options()

    def _get_save_options(self):
        self.save_path = self.save_popup.save_path
        self.use_zarr = self.save_popup.use_zarr
        self.compress = self.save_popup.compress
        self.compression_level = self.save_popup.compression_level
        self.save = True

    def _stop(self):
        """
        Stop the stream.
        """
        self._change_widget_state(not_playing=True)
        self.parent.stop_recording()
        if self.server is not None and self.server.loop is not None:
            future = asyncio.run_coroutine_threadsafe(
                self.server.stop(),
                self.server.loop,
            )
            future.result(timeout=5)
        self.is_running_event.clear()
        if self.play_thread.is_alive():
            self.play_thread.join(timeout=5)
        self.parent.parent.toolbar.save_button.setEnabled(True)
        self.parent.parent.toolbar.save_as_button.setEnabled(True)

    def _pause(self):
        """
        Pause the stream.
        """
        self.play_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.paused = True
        self.parent.set_paused(True)

    def _set_channels(self, skip_dialog=True):
        """
        Set the channels for the stream so that the server can know how many channels are beeing streamed.
        """
        popup = ChannelsPopup(channels=self.channels)
        if not skip_dialog:
            if popup.exec_() == QDialog.Accepted:
                self.channels = popup.channels
                self.parent.display_options.set_file_params(self.channels)
        else:
            self.channels = popup.channels
            self.parent.display_options.set_file_params(self.channels)
        self.play_button.setEnabled(self.channels is not None)

    def get_data(self, n_chunks=None):
        """
        Get the data from the server buffer. This is used to get the data for all channels at once for plotting.
        """
        if self.server is not None and self.server.buffer is not None:
            return self.server.buffer.get()
        else:
            return None

    def _change_widget_state(self, not_playing: bool):
        self.adress_in.setEnabled(not_playing)
        self.port_in.setEnabled(not_playing)
        self.ac_rate_in.setEnabled(not_playing)
        self.set_channels_button.setEnabled(not_playing)
        self.display_wind_in.setEnabled(not_playing)
        self.save_checkbox.setEnabled(not_playing)
        self.stop_button.setEnabled(not not_playing)
        self.pause_button.setEnabled(not not_playing)
        self.play_button.setEnabled(not_playing)
        self.save_popup_button.setEnabled(not_playing)
        self.parent.display_options.sampling_frame.setEnabled(not not_playing)

    def set_value_from_config(self, config):
        """
        Set the values of the widget from a configuration dictionary.
        """
        self.adress_in.setText(config["address"])
        self.port_in.setText(str(config["port"]))
        self.ac_rate_in.setText(str(config["acquisition_rate"]))
        self.display_wind_in.setText(str(np.round(config["display_window"] / config["acquisition_rate"], decimals=2)))
        if len(config["channel_names"]) > 0:
            self.channels = config["channel_names"]
            self._set_channels(skip_dialog=True)

        if config["save_path"] is not None:
            self.save_popup = SaveStreamPopup()
            save_path = Path(config["save_path"])
            save_directory = save_path.parent
            save_filename = save_path.name
            self.save_popup.save_fold_input.setText(str(save_directory))
            self.save_popup.save_name_input.setText(str(save_filename))
            self.save_popup._update_fold_path(str(save_directory))
            self.save_popup._update_save_name(str(save_filename))
            if save_filename[-3:].isdigit():
                self.save_popup.increment_suffix_checkbox.setChecked(config["increment_suffix"])
                # self.save_popup.
            # self.save_popup.use_zarr = config['use_zarr']
            # self.save_popup.compress = config['compress']
            # self.save_popup.compression_level = config['compression_level']
            self.save_checkbox.setChecked(True)

    @property
    def address(self):
        return self.adress_in.text()

    @property
    def increment_suffix(self):
        if self.save_popup is not None:
            return self.save_popup.increment_suffix_checkbox.isChecked()
        else:
            return False

    @property
    def display_window(self):
        return int(float(self.display_wind_in.text()) * self.acquisition_rate)

    @property
    def port(self):
        return str(self.port_in.text())

    @property
    def acquisition_rate(self):
        return float(self.ac_rate_in.text())

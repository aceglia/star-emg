import pyqtgraph as pg
import numpy as np
from scipy.fft import rfft, rfftfreq
from PyQt5.QtWidgets import QGraphicsProxyWidget, QPushButton
from PyQt5.QtCore import Qt
from biosiglive.streaming.utils import CircularBuffer


class ChannelPlot:
    """
    Class use to plot a channel of data. This class is used for every channel to plot.
    This class will store the raw and process data to be plot.
    """

    def __init__(self, parent, channel=None, idx=None):
        """
        Initialize the ChannelPlot object.
        Parameters:
        -----------
        parent: Plotter
            The parent Plotter object.
        channel: str, optional
            The name of the channel to plot. If None, the channel will be named "Channel {idx}".
        idx: int, optional
            the index of the channel to plot. If None, the index will be set to 0.
        """
        self.parent = parent
        self.time = None
        self.freqs = None
        self.plot_item = None
        self.curves = None
        self.raw_idx = 0
        self.clean_idx = 1
        self.raw = None
        self.clean = None
        self.x_range = None
        self.name = channel
        self.idx = idx
        self.visible = True
        self.visible_pen_clean = pg.mkPen(color=(255, 0, 0), width=1)
        self.visible_pen_raw = pg.mkPen(color=(0, 0, 0, 256 // 6), width=1)
        self.pen_clean = pg.mkPen(color=(255, 0, 0), width=1)
        self.pen_raw = pg.mkPen(color=(0, 0, 0, 256 // 6), width=1)
        self.invisible_pen = pg.mkPen(color=(0, 0, 0, 0))
        self.fft_plot = False
        self.view = None
        self.proxy = None
        self.n_times_plotted = 0
        self.window_reached = False

    def init_plot(self, data, time, rate):
        """
        Initialize the plot for the channel.
        Parameters:
        -----------
        data: tuple
            The raw and clean data to plot. The first element is the raw data, the second element is the clean data.
        time: tuple
            The time corresponding to the raw and clean data. The first element is the time for the raw data, the second element is the time for the clean data.
        rate: int
            The sampling rate of the data.

        """
        self.time = time[0]
        self.freqs = rfftfreq(len(data[0]), d=1 / rate)
        self.plot_item = self.parent.addPlot(row=self.idx, col=0)
        # self.plot_item.setXRange(self.time[0], self.time[-1], padding=0)
        self.plot_item.setClipToView(True)
        self.plot_item.setDownsampling(auto=True, mode="peak")
        self.plot_item.setLabel("left", self.name, units="V")
        self.plot_item.getAxis("left").enableAutoSIPrefix(False)
        self.plot_item.showGrid(x=True, y=True, alpha=0.2)
        self.show_config_btn = QPushButton("i")
        self.show_config_btn.setMaximumWidth(10)
        self.show_config_btn.setEnabled(False)
        self.show_config_btn.clicked.connect(self.on_info_button)
        cursor = Qt.CrossCursor
        self.plot_item.setCursor(cursor)
        self.proxy_mouse = pg.SignalProxy(self.plot_item.scene().sigMouseMoved, rateLimit=60, slot=self.mouseMoved)
        self.proxy_btn = QGraphicsProxyWidget()
        self.proxy_btn.setWidget(self.show_config_btn)
        self.parent.addItem(self.proxy_btn, row=self.idx, col=1)

        self.view = self.plot_item.getViewBox()
        self.view.enableAutoRange(x=False, y=False)
        if not np.all(np.isfinite(self.time)):
            if rate is not None:
                start_time = 0
                end_time = len(data[0]) / rate
            else:
                start_time = 0
                end_time = len(data[0])
        else:
            start_time = self.time[0]
            end_time = self.time[-1]
        self.window = end_time - start_time
        self.plot_item.setXRange(start_time, end_time, padding=0)
        self.view.setLimits(xMin=start_time, xMax=end_time)
        self.raw, self.clean = data
        self.raw_fft = abs(rfft(self.raw))
        self.clean_fft = abs(rfft(self.clean))
        self.curves = self.plot_item.multiDataPlot(x=self.time, y=data)
        self._set_curve_params()
        self.current_start_time = 0

    def on_info_button(self):
        """
        Show the parameters and the analysis.
        """
        self.parent.show_config(self.idx)

    def set_visible(self, visible):
        """
        Set a channel plot visible or invisible.
        """
        self.proxy_btn.setVisible(visible)
        self.plot_item.setVisible(visible)
        self.visible = visible

    def _set_curve_params(self):
        """
        Set the parameters of the curves (color, width, etc.) according to the visibility of the raw and clean data.
        """
        for c, curve in enumerate(self.curves):
            curve.setPen([self.pen_raw, self.pen_clean][c])

    def update_plot(self, data=None, data_type="both", auto_range=True, time=None):
        """
        Update the current plot with new data.
        If data is None, the plot will be updated with the current raw and clean data stored in the object.

        Parameters:
        -----------
        data: tuple, optional
            The raw and clean data to plot. The first element is the raw data, the second element is the clean data.
        data_type: str, optional
            The type of data to plot. Can be "raw", "clean", or "both". Default is "both".
        auto_range: bool, optional
            Whether to automatically adjust the range of the plot. Default is True.
        time: tuple, optional
            The time corresponding to the raw and clean data. The first element is the time for the raw data, the second element is the time for the clean data. If None, the current time stored in the object will be used.
        """
        if time is not None:
            self.time = time
        if data is not None:
            if len(data) == 2:
                self.raw = data[0]
                self.clean = data[1]
            if len(data) == 1:
                if data_type == "raw":
                    self.raw = data[0]
                elif data_type == "clean":
                    self.clean = data[0]

        if not self.fft_plot and data is not None:
            if len(data) == 2:
                y = [self.raw, self.clean]
                x = [time[0], time[1]] if len(time) == 2 else self.time
            if len(data) == 1:
                y = [data[0]]
                x = [time[0]]

        elif self.fft_plot:
            self.raw_fft = abs(rfft(self.raw))
            self.clean_fft = abs(rfft(self.clean))
            x = [self.freqs] * 2
            y = [self.raw_fft, self.clean_fft]

        if not self.fft_plot and data is None:
            y = [self.raw, self.clean]
            x = self.time

        if auto_range:
            try:
                start = x[0][0] if len(x) == 2 else x[0]
                stop = x[0][-1] if len(x) == 2 else x[0]
            except Exception as e:
                raise RuntimeError("Error while updating the plot. The data might be empty.", repr(e))
            # self.plot_item.setXRange(start, stop, padding=0)
            self.view.setLimits(xMin=start, xMax=stop)
        auto_range = False
        self.view.enableAutoRange(x=auto_range, y=auto_range)
        if data_type == "raw" or data_type == "both":
            self.curves[0].setData(x=x[0], y=y[0], pen=self.pen_raw)
        if data_type == "clean" or data_type == "both":
            self.curves[1].setData(x=x[1], y=y[1], pen=self.pen_clean)

    def set_link_x(self, plot_item):
        """
        Link all the channel plots to have the same x-axis.
        Parameters:
        -----------
        plot_item: pg.PlotItem
            The plot item to link to. The x-axis of this plot item will be linked to the x-axis of the current plot item.
        """
        self.plot_item.setXLink(plot_item)

    def change_visibility(self, raw=True, clean=True):
        """
        Change the visibility of the raw and clean data by changing the color.
        Parameters:
        -----------
        raw: bool, optional
            Whether to show the raw data. Default is True.
        clean: bool, optional
            Whether to show the clean data. Default is True.

        """
        self.pen_clean = self.visible_pen_clean if clean else self.invisible_pen
        self.pen_raw = self.visible_pen_raw if raw else self.invisible_pen
        self._set_curve_params()

    def change_plot_type(self, fft=False):
        """
        Change the plot type to either time-domain or frequency-domain. Only for Offlineplot
        Parameters:
        -----------
        fft: bool, optional
            Whether to show the frequency-domain plot. Default is False.
        """
        if fft and not self.fft_plot:
            self.fft_plot = True
            self.view.setLimits(xMin=self.freqs[0], xMax=self.freqs[-1])
            self.plot_item.setXRange(0, self.freqs[-1], padding=0)
            self.plot_item.setLabel("left", self.name)
            self.update_plot()
        elif not fft and self.fft_plot:
            self.fft_plot = False
            start = self.time[0] if len(self.time) > 2 else self.time[0][0]
            end = self.time[-1] if len(self.time) > 2 else self.time[0][-1]
            self.view.setLimits(xMin=start, xMax=end)
            self.plot_item.setXRange(start, end, padding=0)
            self.plot_item.setLabel("left", self.name)
            self.update_plot()

    def mouseMoved(self, e):
        pos = e[0]
        # if self.plot_item.sceneBoundingRect().contains(pos):
        mousePoint = self.plot_item.vb.mapSceneToView(pos)
        x_y = [np.round(mousePoint.x(), 3), np.round(mousePoint.y(), 3)]
        # else:
        #     x_y = [' ', ' ']
        self.parent.update_mouse_pos(x_y)


class Plotter(pg.GraphicsLayoutWidget):
    """
    Global parent plotter class containing multiple channel plots.
    """

    pg.setConfigOption("background", "w")
    pg.setConfigOption("foreground", "k")
    pg.setConfigOption("leftButtonPan", False)

    def __init__(self, parent=None):
        """
        Initialize the Plotter object.
        """
        super().__init__()
        self.parent = parent
        self.plot_list = []
        self.channels = []
        self.visible_channels = []
        self.raw_data = None
        self.clean_notch = None
        self.clean_svd = None
        self.idx_to_plot = 0
        self.time = None
        self.current_filter = "notch"
        self.built = False
        self.timer = None

    def init_plots(self):
        """
        Init the channel plots
        """
        for c, channel in zip(self.channel_idxs, self.channel_names):
            data = [self.raw_data[self.idx_to_plot, c, :], self.clean_signal[self.idx_to_plot, c, :]]
            self.plot_list.append(ChannelPlot(self, channel, c))
            self.plot_list[-1].init_plot(data, [self.time[0]] * 2, self.parent.remover_options.get_rate())
            if c != 0:
                self.plot_list[c].set_link_x(self.plot_list[0].plot_item)

    def get_plot_by_name(self, name):
        names = [p.name for p in self.plot_list]
        return self.plot_list[names.index(name)]

    def get_plot_by_idx(self, idx):
        idxs = [p.idx for p in self.plot_list]
        return self.plot_list[idxs.index(idx)]

    def _reorder_channels(self, channels):
        return [c for c in self.channel_names if c in channels]

    def update_draw_params(self, plot_raw, plot_clean, plot_fft):
        """
        Called to update the parameters of the channel plots.

        Parameters:
        -----------
        plot_raw: bool
            Whether to show the raw data.
        plot_clean: bool
            Whether to show the clean data.
        plot_fft: bool
            Whether to show the frequency-domain plot. Only for OfflinePlotter.
        """
        for plot in self.plot_list:
            plot.change_visibility(plot_raw, plot_clean)
            plot.change_plot_type(plot_fft)

    def enable_config_button(self, idxs):
        for plot in self.plot_list:
            if plot.idx not in idxs:
                continue
            plot.show_config_btn.setEnabled(True)

    def update_config_button(self, process_config):
        for plot in self.plot_list:
            if process_config and len(process_config) >= plot.idx and process_config[plot.idx] is not None:
                plot.show_config_btn.setEnabled(True)
            else:
                plot.show_config_btn.setEnabled(False)

    def show_config(self, idx):
        self.parent.show_config(idx)

    def update_mouse_pos(self, pos):
        self.parent.update_mouse_pos(pos)

    @property
    def channel_names(self):
        return [chan[1] for chan in self.channels]

    @property
    def channel_idxs(self):
        return [chan[0] for chan in self.channels]

    @property
    def visible_channel_names(self):
        if self.visible_channels is None:
            return []
        return [chan[1] for chan in self.visible_channels]

    @property
    def visible_channel_idxs(self):
        if self.visible_channels is None:
            return []
        return [chan[0] for chan in self.visible_channels]


class OfflinePlotter(Plotter):
    """
    Offline plotter class containing multiple channel plots. This class is used for offline mode, where the data is already loaded and stored in the object.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

    def initialize_data(self, data, channels, time, cleaned_notch=None, cleaned_svd=None):
        """
        Initialize the data for the offline plotter.

        Parameters:
        -----------
        data: np.ndarray
            The raw data to plot.
        channels: list
            The list of channel names.
        time: np.ndarray
            The time corresponding to the raw data.
        cleaned_notch: np.ndarray, optional
            The cleaned data after notch filtering. If None, the raw data will be used as the clean data for the notch filter.
        cleaned_svd: np.ndarray, optional
            The cleaned data after SVD filtering. If None, the raw data will be used as the clean data for the SVD filter.
        """
        self.channels = [(c, chan) for c, chan in enumerate(channels)]
        self.visible_channels = self.parent.display_options.channel_selecter.get_selected_channels()
        self.raw_data = data
        self.clean_notch = data.copy() if cleaned_notch is None else cleaned_notch
        self.clean_svd = data.copy() if cleaned_svd is None else cleaned_svd
        self.time = time
        self.idx_to_plot = 0
        self.current_filter = "notch"
        if self.built:
            self.clear()
        self.plot_list = []
        self.init_plots()
        self.built = True

    def update_data(self, data, channel_idxs, frame_idxs, data_type="both", auto_range=True):
        """
        Update the data. Might be called after processing the data.
        Parameters:
        -----------
        data: np.ndarray
            The new data to plot.
        channel_idxs: list
            The list of channel indices to update.
        frame_idxs: list
            The list of frame indices to update.
        data_type: str, optional
            The type of data to update. Can be "raw", "clean", or "both". Default is "both".
        auto_range: bool, optional
            Whether to automatically adjust the range of the plot. Default is True.
        """
        if data_type == "both":
            self.raw_data[frame_idxs, channel_idxs, :] = data[0]
            self.clean_signal[frame_idxs, channel_idxs, :] = data[1]
        elif data_type == "raw":
            self.raw_data[frame_idxs, channel_idxs, :] = data
        elif data_type == "clean":
            self.clean_signal[frame_idxs, channel_idxs, :] = data
        self.update_frame(self.idx_to_plot, force=True, data_type=data_type, auto_range=auto_range)

    def update_frame(self, idx, force=False, data_type="both", auto_range=True, update_time=False):
        """
        Update the plot according to the frame index.

        Parameters:
        -----------
        idx: int
            The index of the frame to plot.
        force: bool, optional
            Whether to force the update of the plot. Default is False.
        data_type: str, optional
            The type of data to update. Can be "raw", "clean", or "both". Default is "both".
        auto_range: bool, optional
            Whether to automatically adjust the range of the plot. Default is True.
        update_time: bool, optional
            Whether to update the time of the plot. Default is False.
        """
        visible_idx = self.visible_channel_idxs
        has_changed = self.idx_to_plot != idx or force
        self.idx_to_plot = idx
        time_tmp = self.time[idx]
        for plot in self.plot_list:
            if plot.idx in visible_idx and plot.visible is False:
                plot.set_visible(True)
                plot.update_plot(
                    [self.raw_data[idx, plot.idx, :], self.clean_signal[idx, plot.idx, :]],
                    data_type,
                    auto_range,
                    time=[time_tmp] * 2,
                )
            elif plot.idx not in visible_idx and plot.visible is True:
                plot.set_visible(False)
            elif plot.idx in visible_idx and plot.visible is True and has_changed:
                plot.update_plot(
                    [self.raw_data[idx, plot.idx, :], self.clean_signal[idx, plot.idx, :]],
                    data_type,
                    auto_range,
                    time=[time_tmp] * 2,
                )

    def update_channels(self, channels):
        """
        Update the channels to plot. The subplots for those channels will be removed and not updated to increase efficiency.
        Parameters:
        -----------
        channels: list
            The list of channel names to plot.
        """
        # channels = [i[1] for i in channels]
        # # reordered_channels = self._reorder_channels(channels)
        # if self.visible_channels == reordered_channels:
        #     return
        self.visible_channels = channels
        self.update_frame(self.idx_to_plot)

    def update_filter(self, filter_type):
        """
        Update the plot according to the filter used for processing.
        Parameters:
        -----------
        filter_type: str
            The type of filter used for processing. Can be "notch" or "svd".
        """
        self.current_filter = filter_type
        self.update_frame(self.idx_to_plot, True, data_type="clean", auto_range=False)
        self.update_config_button(self.parent.remover_options.get_current_config())

    @property
    def clean_signal(self):
        return self.clean_notch if self.current_filter == "notch" else self.clean_svd


class StreamPlotter(Plotter):
    """
    Live plotter class containing multiple channel plots.
    """

    def __init__(self, parent=None, rate=60):
        super().__init__(parent)
        self.rate = rate
        self.timer = pg.QtCore.QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.is_streaming = False
        self._current_block = -1
        self.process_available = False
        self.display_window_sec = 5
        self.is_running_event = None
        self.paused = False

    def initialize_data(
        self, data_buffer, time, channels, display_windows, queue_plot, is_running_event, channels_mapping
    ):
        """
        Initialize the data for the live plotter.

        Parameters:
        -----------
        data_buffer: np.ndarray
            The raw data to plot.
        time: np.ndarray
            The time corresponding to the raw data.
        channels: list
            The list of channel names.
        display_windows: int
            The size of the window to display. If set too high, some lag can be visible.
        queue_plot: Queue
            The queue to get the processed data from.
        is_running_event: threading.Event
            The event to check if the processing is running. If not, the plot will not be updated.
        channels_mapping: dict
            The mapping of channels used for each process.
        """
        self.display_windows = display_windows
        self.queue_plot = queue_plot
        self.is_running_event = is_running_event
        self.channels_mapping = channels_mapping
        self.display_window_sec = self.display_windows / self.parent.acquisition_rate
        self.processed_svd_buffer = {i: CircularBuffer(1, self.display_windows) for i in range(len(channels))}
        self.processed_notch_buffer = {i: CircularBuffer(1, self.display_windows) for i in range(len(channels))}
        self.channels = [(c, chan) for c, chan in enumerate(channels)]
        self.visible_channels = self.parent.display_options.channel_selecter.get_selected_channels()
        self.raw_data = data_buffer
        self.time = time
        self.current_filter = "notch"
        if self.built:
            self.clear()
        self.plot_list = []
        self.init_plots()
        self.built = True

    def get_last_processed(self) -> np.ndarray | None:
        """
        Get the last processed data from the queue. If the queue is empty, return None.
        Returns:
        --------
        data: np.ndarray | None
            The last processed data from the queue. If the queue is empty, return None.

        """
        while True:
            try:
                data = self.queue_plot.get_nowait()
                return data
            except Exception:
                return

    def update_plot(self, data_type="both", auto_range=False, force=False):
        """
        udpate the plot according to the data in the queue.

        Parameters:
        -----------
        data_type: str, optional
            The type of data to update. Can be "raw", "clean", or "both". Default is "both".
        auto_range: bool, optional
            Whether to automatically adjust the range of the plot. Default is True.
        force: bool, optional
            Whether to force the update of the plot. Default is False. This parameter is used to avoid non nesserary updates when data didn't changes.
        """
        if self.is_running_event is None:
            return

        if not self.is_running_event.is_set() and not force:
            return

        visible_idx = self.visible_channel_idxs
        raw, t_raw = self.get_raw()
        process_data = self.get_data_from_queue(visible_idx, self.queue_plot)

        for plot in self.plot_list:
            if plot.idx in visible_idx and plot.visible is False:
                plot.set_visible(True)
            if plot.idx not in visible_idx and plot.visible is True:
                plot.set_visible(False)

        if self.paused:
            return

        if not self.parent.display_options.is_sampling_frame:
            block_idx = int(t_raw[-1].item() // self.display_window_sec)
            if self._current_block != block_idx:
                self.parent.update_streaming_frame(block_idx)
            return

        if self.parent.filter_disabled:
            self.parent.remover_options.enable(all=True)
            self.parent.parent.toolbar.filter_menu.setEnabled(True)
            self.parent.filter_disabled = False
        raw, t_raw = self.adjust_to_wind((raw, t_raw), type="raw")
        process_data = self.adjust_to_wind(process_data, type="clean", t_raw=t_raw)
        self.setUpdatesEnabled(False)
        [
            plot.update_plot(
                [raw[plot.idx], process_data[plot.idx][0][0]],
                data_type,
                auto_range,
                time=[t_raw, process_data[plot.idx][1]],
            )
            for plot in self.plot_list
            if plot.idx in visible_idx
        ]
        self.setUpdatesEnabled(True)
        self.process_available = False

    def get_data_from_queue(self, visible_channels, queues) -> dict:
        """
        Get data from the queue for the specified visible channels.

        Parameters:
        -----------
        visible_channels: list
            The list of channel names to update.
        queues: list
            The list of queues to get the processed data from.

        Returns:
        --------
        data: dict
            A dictionary containing the processed data for the specified visible channels. The keys are the channel indices, and the values are tuples containing the processed data and the corresponding time.
        """
        # for i in visible_channels:
        for i in range(len(queues)):
            dic_tmp = queues[i].get_stacked()
            if dic_tmp is not None:
                self.append_clean(dic_tmp[i][0], dic_tmp[i][1], i)
        return {ch: self.get_clean(idx=ch) for ch in visible_channels}

    def adjust_to_wind(self, data, type="raw", t_raw=None):
        """
        Adjust the plot to the current window.
        It is used to be sure that the processed and raw data are in the correct window as the process data might come after the raw data.
        It is also used to have a continuous time axis.
        Parameters:
        -----------
        data: tuple
            A tuple containing the data and the corresponding time.
        type: str, optional
            The type of data to update. Can be "raw" or "clean". Default is "raw".
        t_raw: np.ndarray, optional
            The time corresponding to the raw data. If None, the time will be calculated from the data. Default is None.
        """
        if type == "raw":
            data, t = data
            if t is not None and len(t) > 0 and np.isfinite(t[-1]):
                t_end = t[-1].item()
                block_idx = int(t_end // self.display_window_sec)
                if block_idx != self._current_block:
                    t_start = block_idx * self.display_window_sec
                    t_stop = (block_idx + 1) * self.display_window_sec
                    self.current_start_time = t_start
                    [
                        self.plot_list[i].plot_item.setXRange(t_start, t_stop, padding=0)
                        for i in range(len(self.plot_list))
                        if (self.plot_list[i].visible or i == 0)
                    ]
                    [
                        self.plot_list[i].view.setLimits(xMin=t_start, xMax=t_stop)
                        for i in range(len(self.plot_list))
                        if (self.plot_list[i].visible or i == 0)
                    ]
                    self._current_block = block_idx
                    self.parent.update_streaming_frame(block_idx)

        if type == "raw":
            t_start_idx = np.searchsorted(t, self.current_start_time)
            data = data[:, t_start_idx:]
            t = t[t_start_idx:]
            data = (data, t)
        elif type == "clean":
            for idx in data.keys():
                if data is None or data[idx] is None or data[idx][1] is None or len(data[idx][0]) == 0:
                    continue
                if data[idx][1][-1] <= self.current_start_time:
                    data[idx] = (np.empty((data[idx][0].shape[0], 0)), np.empty(0))
                    continue
                start_idx_tmp = np.searchsorted(data[idx][1], self.current_start_time)
                data[idx] = (data[idx][0][:, start_idx_tmp:], data[idx][1][start_idx_tmp:])
        else:
            raise ValueError(f"Type {type} not recognized. Must be 'raw' or 'clean'.")
        return data

    def update_data(self, data_svd=None, data_notch=None, idx=None):
        """
        Update the data for the live plotter.

        Parameters:
        -----------
        data_svd: np.ndarray, optional
            The processed data after SVD filtering. If None, the raw data will be used as the clean data for the SVD filter.
        data_notch: np.ndarray, optional
            The processed data after notch filtering. If None, the raw data will be used as the clean data for the notch filter.
        idx: int, optional

        Returns:
        --------
        None
        """
        if idx is not None:
            self.update_channels(data_notch, data_svd, idx)
            return
        if data_svd is not None:
            self.processed_svd_buffer.append(data_svd, fill_discontinuous=True)
        if data_notch is not None:
            self.processed_notch_buffer.append(data_notch, fill_discontinuous=True)
        self.process_available = True

    def update_channels(self, data_notch=None, data_svd=None, idx=None):
        """
        Update the channels with the provided data.

        Parameters:
        -----------
        data_notch: np.ndarray, optional
            The processed data after notch filtering. If None, the raw data will be used as the clean data for the notch filter.
        data_svd: np.ndarray, optional
            The processed data after SVD filtering. If None, the raw data will be used as the clean data for the SVD filter.
        idx: int, optional
            The index of the channel to update. If None, all channels will be updated.

        Returns:
        --------
        None
        """
        if data_svd is not None:
            self.processed_svd_buffer.append(data_svd, fill_discontinuous=True)
        if data_notch is not None:
            self.processed_notch_buffer.append(data_notch, fill_discontinuous=True)

    def update_filter(self, filter_type: str):
        """
        Update the plot according to the filter used for processing.
        Parameters:
        -----------
        filter_type: str
            The type of filter used for processing. Can be "notch" or "svd".
        """
        self.current_filter = filter_type

    def get_raw(self):
        return self.raw_data.get()

    def get_clean(self, idx):
        return (
            self.processed_notch_buffer[idx].get()
            if self.current_filter == "notch"
            else self.processed_svd_buffer[idx].get()
        )

    def append_clean(self, data, t=None, idx=None):
        clean_buffer = (
            self.processed_notch_buffer[idx] if self.current_filter == "notch" else self.processed_svd_buffer[idx]
        )
        clean_buffer.append(data, t, fill_discontinuous=True)

    def init_plots(self):
        """
        Initialize the plots for the live plotter. Put NaN value first to have a already present time axis.
        """
        nan_vect = np.full(self.display_windows, np.nan)
        for c, channel in zip(self.channel_idxs, self.channel_names):
            data = [nan_vect, nan_vect]
            self.plot_list.append(ChannelPlot(self, channel, c))
            self.plot_list[-1].init_plot(data, data, self.parent.acquisition_rate)
            if c != 0:
                self.plot_list[c].set_link_x(self.plot_list[0].plot_item)
            if self.timer.isActive():
                continue
            self.timer.start(1000 // self.rate)

    def update_channels_visibility(self, channels: list) -> None:
        """
        Update the channels visibility by removing the channels that are not in the list of channels to display. This is used to increase the efficiency of the plot by not updating the channels that are not visible.
        Parameters:
        -----------
        channels: list
            The list of channel names to display.

        Returns:
        --------
        None
        """
        self.visible_channels = channels
        self.update_plot(force=True)

    def start_plotting(self):
        self.is_streaming = True
        # self.timer.start(1000 // self.rate)

    def stop_plotting(self):
        self.is_streaming = False

    def pause_plot(self, pause):
        self.paused = pause

    def plot_data(self, raw, process_data, time):
        [
            plot.update_plot(
                [raw[plot.idx], process_data[plot.idx]],
                "both",
                True,
                time=[time, time],
            )
            for plot in self.plot_list
            if plot.visible is True
        ]

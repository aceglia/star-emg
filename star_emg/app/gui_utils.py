from PyQt5.QtWidgets import (
    QPushButton,
    QVBoxLayout,
    QWidget,
    QCheckBox,
)
from PyQt5.QtCore import QRunnable, QObject, pyqtSignal, pyqtSlot

from functools import partial

from PyQt5.QtWidgets import QPlainTextEdit
import datetime
import re


class LogBox(QPlainTextEdit):
    """
    Class to display log messages in a QPlainTextEdit widget.
    """

    def __init__(self):
        """
        Initialize the LogBox widget.
        """
        super().__init__()
        self.setReadOnly(True)

    def log(self, message: str) -> None:
        """
        Log message to the log box.

        Parameters:
        -----------
        message: str
            Message to log.

        Returns:
        --------
        None
        """
        self.appendPlainText(self._add_current_time(message))
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
        # QTimer.singleShot(600, self.calling_fct)

    def _add_current_time(self, message: str) -> str:
        """
        Add current time to the message as prefix.
        Parameters:
        -----------
        message: str
            Message to add the current time to.
        Returns:
        --------
        str: Message with current time as prefix.
        """
        return f"[{str(datetime.datetime.now())}] {message}"

    @staticmethod
    def calling_fct():
        """
        Dummy function to be called after logging a message.
        """
        return


def ensure_list(x: any):
    """
    Function to ensure that x is a list.

    Parameters:
    -----------
    x: any
        Object to check.
    Returns:
    --------
    list: x if x is already a list, else [x].
    """

    return x if isinstance(x, list) else [x]


def check_list(text):
    all_list = re.findall("\\[.*?\\]", text)
    final_list = []
    len_list = []
    for list in all_list:
        final_list.append([float(v.strip()) for v in list.strip("[]").split(",") if v.strip() != ""])
        len_list.append(len(final_list[-1]))
    if len(set(len_list)) != 1:
        raise RuntimeError(
            "You must chose one window modality. You have selected different window selection type for the same data."
        )
    return final_list


class ChannelSelecter(QWidget):
    """
    Widget for selecting channels.
    """

    def __init__(self, parent=None, channel_list=[], for_display=True, only_one=False):
        """
        Initialize the ChannelSelecter widget.
        Parameters:
        -----------
        parent: QWidget, optional
            The parent widget of the ChannelSelecter.
        channel_list: list, optional
            The list of channels to select from.
        for_display: bool, optional
            Whether the channel selecter is for display or for processing. If for display, the title of the widget will be "Select channel(s) to display", else it will be "Select channel(s) to process".
        only_one: bool, optional
            Whether only one channel can be selected.
        Returns:
        --------
        None
        """
        super().__init__()
        title = "Select channel(s) to display" if for_display else "Select channel(s) to process"
        self.setWindowTitle(title)
        self.checkbox_list = []
        self.only_one = only_one
        self.current_selected_channel = 0
        self.parent = parent
        layout = QVBoxLayout()
        for c, channel in enumerate(channel_list):
            self.checkbox_list.append(QCheckBox(channel))
            self.checkbox_list[-1].setChecked(not self.only_one)
            if self.only_one:
                self.checkbox_list[-1].stateChanged.connect(partial(self.on_state_changed, idx=c))
            layout.addWidget(self.checkbox_list[-1])
        if self.only_one:
            self.checkbox_list[0].setChecked(True)
            self.checkbox_list[0].setEnabled(False)
        self.select_all_button = QPushButton("Select all")
        self.select_all_button.clicked.connect(self.on_all_checked)
        self.unselect_all_button = QPushButton("Unselect all")
        self.unselect_all_button.clicked.connect(self.on_all_unchecked)
        if not self.only_one:
            layout.addWidget(self.select_all_button)
            layout.addWidget(self.unselect_all_button)
        button_name = "Draw" if for_display else "Apply"
        self.draw_button = QPushButton(button_name)
        self.draw_button.clicked.connect(self.parent.on_draw_clicked)
        layout.addWidget(self.draw_button)
        self.setLayout(layout)
        self.resize(300, 200)

    def on_all_unchecked(self):
        for checkbox in self.checkbox_list:
            checkbox.setChecked(False)

    def on_all_checked(self):
        for checkbox in self.checkbox_list:
            checkbox.setChecked(True)

    def on_state_changed(self, state, idx):
        if state == 2 and self.current_selected_channel != idx:
            self.checkbox_list[self.current_selected_channel].setChecked(False)
            self.checkbox_list[self.current_selected_channel].setEnabled(True)
            self.current_selected_channel = idx
            self.checkbox_list[idx].setChecked(True)
            self.checkbox_list[idx].setEnabled(False)

    def set_channels(self, channels):
        if len(channels) == 0:
            return
        for c, checkbox in enumerate(self.checkbox_list):
            if c in channels:
                checkbox.setChecked(True)
            else:
                checkbox.setChecked(False)

    def get_selected_channels(self):
        """
        Return the list of selected channels.

        Returns:
        --------
        list: List of selected channels.
        """
        selected_channels = []
        for c, checkbox in enumerate(self.checkbox_list):
            if checkbox.isChecked():
                selected_channels.append((c, checkbox.text()))
        return selected_channels

    def get_channel_idxs(self):
        """
        Get the indexs of the selected channels.
        Returns:
        --------
        list: List of indexs of the selected channels.
        """
        channels = self.get_selected_channels()
        return [i[0] for i in channels]

    def get_channel_names(self):
        """
        Get the names of the selected channels.
        Returns:
        --------
        list: List of names of the selected channels.
        """
        channels = self.get_selected_channels()
        return [i[1] for i in channels]

    def quit(self):
        self.close()


class WorkerSignals(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(Exception)


class Worker(QRunnable):
    """Worker thread.

    Inherits from QRunnable to handler worker thread setup, signals and wrap-up.
    """

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        """Initialise the runner function with passed args, kwargs."""
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.finished.emit(result)
        except Exception as e:
            self.signals.error.emit(str(repr(e)))

import os

from PyQt5.QtWidgets import (
    QMessageBox,
    QDialog,
    QGridLayout,
    QLabel,
    QLineEdit,
    QCheckBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QFileDialog,
)


def popup_warning_save(text, title, fct):
    wind = QMessageBox()
    wind.setText(text)
    wind.setWindowTitle(title)
    wind.setIcon(QMessageBox.Question)
    wind.setStandardButtons(QMessageBox.Save | QMessageBox.Ignore | QMessageBox.Cancel)
    wind.setDefaultButton(QMessageBox.Save)
    wind.buttonClicked.connect(fct)
    wind.exec_()


def popup_warning_continue(text, title, fct):
    wind = QMessageBox()
    wind.setText(text)
    wind.setWindowTitle(title)
    wind.setIcon(QMessageBox.Question)
    wind.setStandardButtons(QMessageBox.Ignore | QMessageBox.Cancel)
    wind.setDefaultButton(QMessageBox.Cancel)
    wind.buttonClicked.connect(fct)
    wind.exec_()


def popup_warning_split(text, title, fct):
    wind = QMessageBox()
    wind.setText(text)
    wind.setWindowTitle(title)
    wind.setIcon(QMessageBox.Question)
    wind.setStandardButtons(QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
    wind.setDefaultButton(QMessageBox.Yes)
    wind.buttonClicked.connect(fct)
    wind.exec_()


class FilterDialog(QDialog):
    """
    Windows for the prefiltering configuration when loading a file. The data rate can be als provided if not included in the file.
    """

    def __init__(self, parent=None, fs=None):
        """
        Initialize the dialog.
        Parameters:
        -----------
        parent: QWidget, optional
            The parent widget of the dialog.
        fs: float, optional
            The sample rate of the data. If not provided, it will be set to the value provided in the file.
        """
        super().__init__(parent)
        self.setWindowTitle("Data pre-filtering")
        layout = QGridLayout()
        self.fs = fs
        label = QLabel("Sample rate (Hz) (Optional if already in file):")
        self.fs_input = QLineEdit(str(fs) if fs is not None else "")
        layout.addWidget(label, 0, 0, 1, 1)
        layout.addWidget(self.fs_input, 0, 1, 1, 2)
        self.do_center_input = QCheckBox("Center signal")
        self.do_center_input.setChecked(True)
        layout.addWidget(self.do_center_input, 1, 0, 1, 3)
        self.do_filtering_input = QCheckBox("Zero-lag band pass filter")
        self.do_filtering_input.setChecked(True)
        self.do_filtering_input.stateChanged.connect(self.enable_filtering_params)
        layout.addWidget(self.do_filtering_input, 2, 0, 1, 3)
        label = QLabel("Cut-off frequencies (Low - High) (Hz):")
        self.low_cut = QLineEdit("10")
        layout.addWidget(label, 3, 0, 1, 1)
        layout.addWidget(self.low_cut, 3, 1, 1, 1)
        self.high_cut = QLineEdit("450")
        layout.addWidget(self.high_cut, 3, 2, 1, 1)
        self.order = QLineEdit("4")
        layout.addWidget(QLabel("Filter order:"), 4, 0, 1, 1)
        layout.addWidget(self.order, 4, 1, 1, 1)
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(self.ok_button, 5, 0, 1, 1)
        layout.addWidget(self.cancel_button, 5, 2, 1, 1)

        self.setLayout(layout)

    def enable_filtering_params(self, state):
        for widget in [self.low_cut, self.high_cut, self.order]:
            widget.setEnabled(state != 0)

    def get_filter_params(self):
        return {
            "data_rate": float(self.fs_input.text()) if self.fs_input.text() else self.fs,
            "cutoff": [float(self.low_cut.text()), float(self.high_cut.text())],
            "order": max(int(self.order.text()) // 2, 1),
            "signal_filter": self.do_filtering_input.isChecked(),
            "center": self.do_center_input.isChecked(),
        }


class ChannelsPopup(QDialog):
    """
    Windows for the configuration of the channels when setting up a new stream.
    """

    def __init__(self, channels=None):
        super().__init__()
        self.setWindowTitle("Channels configuration")
        self._channels = channels
        self._create_layout()
        if channels is not None:
            self._init_channels(channels)

    def _create_layout(self):
        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(1)
        self.table_widget.setHorizontalHeaderLabels(["Channel name"])
        self.add_device_button = QPushButton("Add channel")
        self.add_device_button.clicked.connect(self._on_add_channel)
        self.remove_device_button = QPushButton("Remove channel")
        self.remove_device_button.clicked.connect(self._remove_row)
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)

        self.layout = QGridLayout()
        self.layout.addWidget(self.table_widget, 0, 0, 1, 2)
        self.layout.addWidget(self.add_device_button, 1, 0)
        self.layout.addWidget(self.remove_device_button, 1, 1)
        self.layout.addWidget(self.ok_button, 2, 0)
        self.layout.addWidget(self.cancel_button, 2, 1)
        self.setLayout(self.layout)

    def _init_channels(self, channels):
        for channel in channels:
            self._add_channel(channel)

    def _on_add_channel(self):
        self._add_channel()

    def _add_channel(self, channel=None):
        row_index = self.table_widget.rowCount()
        self.table_widget.insertRow(row_index)
        name = f"Channel {row_index}" if (channel is None or channel == "") else channel
        self.table_widget.setItem(row_index, 0, QTableWidgetItem(name))

    def _remove_row(self):
        row_index = self.table_widget.currentRow()
        self.table_widget.removeRow(row_index)

    def get_channels(self):
        channels = []
        for i in range(self.table_widget.rowCount()):
            item = self.table_widget.item(i, 0)
            if item is not None:
                channels.append(item.text())
        return channels

    @property
    def channels(self):
        return self.get_channels()


class SaveStreamPopup(QDialog):
    """
    Windows for the configuration of the saving options when setting up a new stream.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Saving options")
        self.save_folder = None
        self.save_name = None
        self.use_zarr = True
        self.compress = True
        self.compression_level = 3

        self._create_layout()

    def _create_layout(self):
        layout = QGridLayout()
        layout.addWidget(QLabel("Select a folder:"), 0, 0)
        self.save_fold_input = QLineEdit("")
        self.save_fold_input.setText(self.save_folder if self.save_folder is not None else "")
        self.save_fold_input.textChanged.connect(self._update_fold_path)
        layout.addWidget(self.save_fold_input, 0, 1, 1, 2)
        layout.addWidget(QLabel("File name:"), 1, 0)
        self.save_name_input = QLineEdit("")
        self.save_name_input.setText(self.save_name if self.save_name is not None else "")
        self.save_name_input.textChanged.connect(self._update_save_name)
        layout.addWidget(self.save_name_input, 1, 1, 1, 2)

        # browse button to select the save path
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self._browse_save_folder)
        layout.addWidget(self.browse_button, 0, 3)

        # check box to increment the suffix of the file name to avoid overwriting existing files
        self.increment_suffix_checkbox = QCheckBox("Increment file name")
        self.increment_suffix_checkbox.setChecked(True)
        layout.addWidget(self.increment_suffix_checkbox, 2, 0, 1, 3)

        # TODO: add option to use zarr format and compression

        # self.use_zarr_checkbox = QCheckBox("Use Zarr format")
        # self.use_zarr_checkbox.setChecked(self.use_zarr)
        # self.use_zarr_checkbox.setToolTip(
        #     "Use Zarr format for saving data. Requires the 'zarr' package to be installed."
        # )
        # self.use_zarr_checkbox.stateChanged.connect(self._toggle_zarr_options)
        # layout.addWidget(self.use_zarr_checkbox, 3, 0, 1, 3)

        # self.compress_checkbox = QCheckBox("Compress data")
        # self.compress_checkbox.setEnabled(self.use_zarr)
        # self.compress_checkbox.setChecked(self.compress)
        # self.compress_checkbox.setToolTip(
        #     "Compress data when saving. Requires the 'numcodecs' package to be installed."
        # )
        # self.compress_checkbox.stateChanged.connect(self._check_compress)
        # layout.addWidget(self.compress_checkbox, 4, 0, 1, 3)

        # layout.addWidget(QLabel("Compression level (1-9):"), 5, 0)
        # self.compression_level_input = QLineEdit(str(self.compression_level))
        # self.compression_level_input.setEnabled(self.use_zarr and self.compress)
        # self.compression_level_input.setToolTip(
        #     "Set the compression level for saving data. 1 is the fastest, 9 is the most compressed."
        # )
        # self.compression_level_input.textChanged.connect(self._check_compression_level)
        # layout.addWidget(self.compression_level_input, 5, 1)

        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept_custom)
        layout.addWidget(self.ok_button, 3, 0)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(self.cancel_button, 3, 1)

        self.setLayout(layout)

    def _update_fold_path(self, text):
        if text == "":
            return
        self.save_folder = text

    def _update_save_name(self, text):
        if text == "":
            return
        self.save_name = text

    def _toggle_zarr_options(self, state):
        self.use_zarr = state
        self.compress_checkbox.setEnabled(state)
        self.compression_level_input.setEnabled(state and self.compress_checkbox.isChecked())

    def _check_compress(self, state):
        self.compress = state
        self.compression_level_input.setEnabled(state and self.use_zarr_checkbox.isChecked())

    def _check_compression_level(self):
        if self.compression_level_input.text() == "":
            return
        try:
            level = int(self.compression_level_input.text())
            if level < 1 or level > 9:
                raise ValueError
            self.compression_level = level
        except ValueError:
            QMessageBox.warning(self, "Warning", "Compression level must be an integer between 1 and 9.")
            self.compression_level_input.setText(str(self.compression_level))

    def accept_custom(self):
        if self.save_path is None:
            QMessageBox.warning(self, "Warning", "Please provide a save path.")
            return
        self.accept()

    def increment_suffix(self, path):
        """
        Increment the suffix from 00x to 00x+1 to avoid overwriting existing files.
        Parameters:
        -----------
        """
        while os.path.exists(path):
            base, ext = os.path.splitext(path)
            if base[-3:].isdigit():
                num = int(base[-3:]) + 1
                new_base = f"{base[:-3]}{num:03d}"
            else:
                new_base = f"{base}001"
            path = f"{new_base}{ext}"
        return path

    @property
    def save_path(self):
        if self.save_folder is None or self.save_name is None:
            return None
        path = os.path.join(self.save_folder, self.save_name)
        base, ext = os.path.splitext(path)
        if ext == "" and self.use_zarr:
            ext = ".stream"
            path += ext

        if self.increment_suffix_checkbox.isChecked():
            if not base[-3:].isdigit():
                path = f"{base}001{ext}"
        if os.path.exists(path):
            if self.increment_suffix_checkbox.isChecked():
                return self.increment_suffix(path)
            else:
                return path
        return path

    def _browse_save_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select a folder", "", QFileDialog.Option.ShowDirsOnly)
        self.save_fold_input.setText(path)
        self._update_fold_path(path)

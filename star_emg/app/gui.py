import shutil
import json
import os
from pathlib import Path
from PyQt5.QtWidgets import (
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QSplitter,
    QFileDialog,
    QStackedWidget,
)
import numpy as np
from PyQt5.QtCore import Qt

from star_emg.app.save_utils import ZarrRecording
from .gui_utils import LogBox
from .file_dialog import LoadDialog, SaveDialog
from .cache import Cache
from .popup_utils import popup_warning_split, popup_warning_continue, popup_warning_save

from .processing_widget import OfflineProcessingWidget, StreamProcessingWidget


class CustomToolBar:
    """
    This class creates a custom toolbar for the GUI. It contains two menus: "File" and "Filter". The "File" menu allows the user to load files, load configurations, save configurations, and quit the application. The "Filter" menu allows the user to select between a notch filter and an SVD filter. The toolbar also has methods to enable or disable the filter menu based on the state of the application.
    """

    def __init__(self, parent):
        self.menu_bar = parent.menuBar()
        self.parent = parent
        self._file_menu()
        self._filter_menu()
        self._stream_menu()

    def _file_menu(self):
        """
        This method creates the "File" menu and adds the necessary actions to it.
        """
        self.file_menu = self.menu_bar.addMenu("File")
        self.load_files_button = self.file_menu.addAction("Load file")
        self.load_files_button.triggered.connect(self.parent._load_file)
        self.load_files_button.setEnabled(True)
        self.load_files_button = self.file_menu.addAction("Load stream")
        self.load_files_button.triggered.connect(self.parent._load_stream)
        self.load_files_button.setEnabled(True)
        # self.load_config_button = self.file_menu.addAction("Load config")
        # self.load_config_button.triggered.connect(self.parent._load_config)
        # self.load_config_button.setEnabled(True)
        # self.save_config_button = self.file_menu.addAction("Save config")
        # self.save_config_button.setEnabled(False)
        # self.save_config_button.triggered.connect(self.parent._save_config)
        self.save_button = self.file_menu.addAction("Save")
        self.save_button.triggered.connect(self.parent.save)
        self.save_button.setEnabled(False)
        self.save_as_button = self.file_menu.addAction("Save As")
        self.save_as_button.triggered.connect(self.parent.save_as)
        self.save_as_button.setEnabled(False)
        self.quit_button = self.file_menu.addAction("Quit")
        self.quit_button.triggered.connect(self.parent.quit)

    def _filter_menu(self):
        """
        This method creates the "Filter" menu and adds the necessary actions to it.
        """
        self.filter_menu = self.menu_bar.addMenu("Filter")
        self.radio_notch_filter_button = self.filter_menu.addAction("Notch filter")
        self.radio_notch_filter_button.setEnabled(True)
        self.radio_notch_filter_button.triggered.connect(self.parent.notch_selected)

        self.radio_svd_filter_button = self.filter_menu.addAction("SVD filter")
        self.radio_svd_filter_button.setEnabled(False)
        self.radio_svd_filter_button.triggered.connect(self.parent.svd_selected)

        self.save_config_button = self.filter_menu.addAction("Save filter config")
        self.save_config_button.setEnabled(False)
        self.save_config_button.triggered.connect(self.parent._save_config)
        self.disable_filter_menu()

    def _stream_menu(self):
        self.stream_menu = self.menu_bar.addMenu("Stream")
        self.go_stream_button = self.stream_menu.addAction("Go in stream mode")
        self.go_stream_button.triggered.connect(self.parent.go_stream_mode)
        self.go_offline_button = self.stream_menu.addAction("Go in offline mode")
        self.go_offline_button.setEnabled(False)
        self.go_offline_button.triggered.connect(self.parent.go_offline_mode)
        # self.load_stream_config = self.stream_menu.addAction("Load stream config")
        # self.load_stream_config.triggered.connect(self.parent.load_stream_config)
        # self.save_stream_config = self.stream_menu.addAction("Save stream config")
        # self.save_stream_config.triggered.connect(self.parent.save_stream_config)

    def disable_filter_menu(self):
        """
        This method disables the filter menu. It is called when the application is in a state where the filters cannot be applied, such as when no file is loaded.
        """
        self.filter_menu.setEnabled(False)

    def enable_filter_menu(self):
        """
        This method enables the filter menu. It is called when the application is in a state where the filters can be applied, such as when a file is loaded.
        """
        self.filter_menu.setEnabled(True)

    def adjust_for_mode(self, offline=True):
        """
        This method adjusts the toolbar for stream mode. It disables the file menu and enables the appropriate buttons for stream mode.
        """
        self.load_files_button.setEnabled(offline)


class GUI(QMainWindow):
    """
    This class creates the main GUI for the StAR-EMG application. It contains a log box to display messages to the user, a processing widget to handle the file processing, and a custom toolbar for file and filter actions. The GUI also manages the state of the application, such as whether the current work is saved or not, and handles user interactions through various methods.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("StAR-EMG App")
        self.log_box = LogBox()
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        app_dir = os.getcwd()
        self._quit = False
        self._continue = False
        self.cache = Cache(cache_file=os.path.join(app_dir, "_pychache.json"))
        self.file_to_process = None
        self.current_filter = "notch"
        self.processing_widget = OfflineProcessingWidget(self)
        self.stream_processing_widget = StreamProcessingWidget(self)
        self.default_extension = ".npz"
        self.toolbar = CustomToolBar(self)
        # self.addToolBar(self.toolbar)
        self._init_layout()
        self.show()
        self._tmp_file_path = r".tmp_stream/recording.zarr"
        self._check_for_unsaved_work()
        self.saved_ok = True
        self._split = False
        self.save_as_popup = None
        self.default_save_name = None
        self.mode = "offline"
        self.default_base_name = None

    def _init_layout(self):
        """
        This method initializes the layout of the GUI, including the log box, processing widget, and clear log button.
        """
        self.clear_log_button = QPushButton("Clear Log")
        self.clear_log_button.clicked.connect(self.log_box.clear)
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.log_box)
        splitter.addWidget(self.clear_log_button)
        main_layout = QVBoxLayout()
        main_splitter = QSplitter(Qt.Vertical)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.processing_widget)
        self.stack.addWidget(self.stream_processing_widget)
        main_splitter.addWidget(self.stack)
        main_splitter.addWidget(splitter)
        main_layout.addWidget(main_splitter)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setAlignment(Qt.AlignTop)
        self.central_widget.setLayout(main_layout)

    def _check_for_unsaved_work(self):
        if os.path.exists(self._tmp_file_path):
            popup_warning_save(
                "Something went wrong. You have unsaved stream session. Do you want to save the work? ",
                "Warning",
                self.popup_stream_unsaved,
            )
            if self._delete_tmp:
                self.log_box.log("Unsaved work was not saved. It will be deleted.")
                # get the directory of the tmp file path
                tmp_dir = os.path.dirname(self._tmp_file_path)
                shutil.rmtree(tmp_dir)

    def popup_stream_unsaved(self, button):
        """
        Options for the popup warning when the user has unsaved work and tries to quit the application. If the user clicks "Save", it saves the current file and configuration, sets the _quit attribute to True, and allows the application to quit. If the user clicks "Ignore", it sets the _quit attribute to True, allowing the application to quit without saving. If the user clicks "Cancel", it sets the _quit attribute to False, preventing the application from quitting.
        """
        self._delete_tmp = True
        if button.text() == "Save":
            success = self.stream_processing_widget.save_zarrds(self._tmp_file_path)
            if not success:
                self._check_for_unsaved_work()
        elif button.text() == "Cancel":
            self._delete_tmp = False

    def go_stream_mode(self):
        """
        Set up widget for stream mode.
        """
        self.toolbar.go_offline_button.setEnabled(True)
        self.toolbar.go_stream_button.setEnabled(False)
        self.toolbar.adjust_for_mode(False)
        self.stack.setCurrentWidget(self.stream_processing_widget)
        self.toolbar.save_config_button.setEnabled(False)
        self.mode = "stream"

    def go_offline_mode(self):
        """
        Set up widget for offline mode.
        """
        self.toolbar.go_offline_button.setEnabled(False)
        self.toolbar.go_stream_button.setEnabled(True)
        self.toolbar.adjust_for_mode(True)
        self.stack.setCurrentWidget(self.processing_widget)
        self.mode = "offline"
        if self.processing_widget.file_path is None:
            self.toolbar.save_config_button.setEnabled(False)

    def notch_selected(self):
        """
        This method is called when the user selects the notch filter from the filter menu. It updates the current filter, enables/disables the appropriate buttons in the toolbar, logs the selection, and updates the processing widget to use the notch filter.
        """
        self.current_filter = "notch"
        self.toolbar.radio_svd_filter_button.setEnabled(True)
        self.toolbar.radio_notch_filter_button.setEnabled(False)
        self.log_box.log("Notch filter selected")
        self.stack.currentWidget().update_filter("notch")

    def svd_selected(self):
        """
        This method is called when the user selects the SVD filter from the filter menu. It updates the current filter, enables/disables the appropriate buttons in the toolbar, logs the selection, and updates the processing widget to use the SVD filter.
        """
        self.current_filter = "svd"
        self.toolbar.radio_notch_filter_button.setEnabled(True)
        self.toolbar.radio_svd_filter_button.setEnabled(False)
        self.log_box.log("SVD filter selected")
        self.stack.currentWidget().update_filter("svd")

    def _load_stream(self):
        from numcodecs import blosc

        blosc.use_threads = False
        blosc.set_nthreads(1)
        directory = QFileDialog.getExistingDirectory(
            self, "Select Stream Directory", self.cache.get_from_cache("last_dir")
        )
        if directory == "":
            return
        if not Path(directory).suffix == ".stream" and "zarr.json" not in os.listdir(directory):
            self.log_box.log(f"Selected directory is not a valid stream directory: {directory}")
            return
        try:
            self.log_box.log(f"Exporting stream to .npz file...")
            zarr_ds = ZarrRecording.load_dataset(directory)
            dic_to_save, _ = zarr_ds.to_dict()
            np.savez(Path(directory).with_suffix(".npz"), **dic_to_save)
            filename = str(Path(directory).with_suffix(".npz"))
            self._load_file(False, load_dialog=False, filename=filename)
        except Exception as e:
            self.log_box.log(f"Error loading stream: {e}")
            return

    def _load_file(self, _, load_dialog=True, filename=False):
        """
        Open a file dialog to load a file for processing. If the user has unsaved work, it prompts them with a warning before proceeding. Once a file is selected and loaded, it updates the default save name and enables the appropriate buttons in the toolbar.
        """
        if not self.saved_ok:
            popup_warning_continue(
                "You didn't save your work, it will be erased, do you want to continue?", "Warning", self.popup_continue
            )
            if not self._continue:
                return
        if load_dialog:
            dialog = LoadDialog(
                parent=self,
                caption="Load file",
                filter="Numpy archive (*.npz);; Matlab format (version < 7) (*.mat);;Text file (*.txt);; Biosiglive format (*.bio)",
                load_method=None,
            )
            if dialog.filename == "":
                return
            if self.mode == "stream":
                self.go_offline_mode()
            filename = dialog.filename

        self.processing_widget.set_file(filename)
        if self.processing_widget.canceled:
            return
        path_tmp = Path(self.processing_widget.file_path)
        self.default_base_name = os.path.join(str(path_tmp.parent), path_tmp.stem)
        self.default_save_name = os.path.join(
            str(path_tmp.parent), path_tmp.stem + "_processed" + self.default_extension
        )
        # self.default_extension = path_tmp.suffix
        self.toolbar.save_config_button.setEnabled(True)
        self.toolbar.save_button.setEnabled(True)
        self.toolbar.save_as_button.setEnabled(True)

    def _save_file(self):
        """
        Run the processing widget's save_file method to save the processed file. The file is saved with a name based on the default save name, with "_processed.mat" appended to it. It also logs the save action in the log box.
        """
        self.log_box.log(f"Saving file at: {self.default_save_name}")
        return self.processing_widget.save_file(self.default_save_name, self.default_extension)

    def _check_config(self, path):
        """
        Check if the configuration is stream or offline.
        """
        with open(path, "r") as f:
            config = json.load(f)
        if config["mode"] == "stream":
            self.go_stream_mode()
        elif config["mode"] == "offline":
            self.go_offline_mode()
        else:
            raise ValueError("Invalid mode in configuration file. Must be 'stream' or 'offline'.")
        self.stack.currentWidget().load_config(path)

    def _load_config(self):
        """
        Open a file dialog to load a configuration file for processing. If the user has unsaved work, it prompts them with a warning before proceeding. Once a configuration file is selected and loaded, it updates the default save name and enables the appropriate buttons in the toolbar.
        """
        if not self.saved_ok:
            popup_warning_continue(
                "You didn't save your work, it will be erased, do you want to continue?", "Warning", self.popup_continue
            )
            if not self._continue:
                return
        dialog = LoadDialog(
            parent=self,
            caption="Load configuration file",
            filter="File type (*.json)",
            load_method=self._check_config,
        )
        if self.stack.currentWidget() == self.stream_processing_widget:
            return

        if dialog.filename == "":
            return
        if self.processing_widget.canceled:
            return
        path_tmp = Path(self.processing_widget.file_path)
        self.default_base_name = os.path.join(str(path_tmp.parent), path_tmp.stem)
        self.default_save_name = os.path.join(str(path_tmp.parent), path_tmp.stem + "_processed" + path_tmp.suffix)
        self.toolbar.save_config_button.setEnabled(True)
        # self.toolbar.save_as_config_button.setEnabled(True)

    def _save_config(self):
        """
        Run the processing widget's save_config method to save the current configuration. The configuration is saved with a name based on the default save name, with "_configuration.json" appended to it. It also logs the save action in the log box.
        """
        if self.default_base_name is not None:
            file_path = str(self.default_base_name) + "_configuration.json"
        else:
            file_path = None
        self.stack.currentWidget().save_config(file_path)

    def quit(self):
        """
        Quit the application. If the user has unsaved work, it prompts them with a warning before proceeding. If the user chooses to save their work, it saves the current file and configuration before quitting. If the user chooses to ignore the warning, it quits without saving. If the user cancels the quit action, it does nothing and returns to the application.
        """
        if not self.saved_ok:
            popup_warning_save("Do you want to save and exit?", "Quit", self.popup_button)
            if self._quit:
                self.close()
        else:
            self.close()

    def log(self, message):
        """
        Add log to the log box.

        Parameters
        ----------
        message : str
            The message to be logged in the log box.
        """
        if self.log_box is not None:
            self.log_box.log(message)

    def popup_continue(self, button):
        """
        Options for the popup warning when the user has unsaved work and tries to load a new file or configuration. If the user clicks "Ignore", it sets the _continue attribute to True, allowing the action to proceed. If the user clicks "Cancel", it sets the _continue attribute to False, preventing the action from proceeding.
        """
        if button.text() == "Ignore":
            self._continue = True
        elif button.text() == "Cancel":
            self._continue = False

    def popup_button(self, button):
        """
        Options for the popup warning when the user has unsaved work and tries to quit the application. If the user clicks "Save", it saves the current file and configuration, sets the _quit attribute to True, and allows the application to quit. If the user clicks "Ignore", it sets the _quit attribute to True, allowing the application to quit without saving. If the user clicks "Cancel", it sets the _quit attribute to False, preventing the application from quitting.
        """
        if button.text() == "Save":
            self._save_files()
            self._quit = True
        elif button.text() == "Ignore":
            self._quit = True
        elif button.text() == "Cancel":
            self._quit = False

    def save_as(self):
        """
        Open a popup dialog to allow the user to enter a new name for the file they want to save. The default name in the input dialog is based on the current default save name, with the file extension removed. If the user confirms the new name, it updates the default save name with the new name and calls the save method to save the file with the new name.
        """
        # text, ok = QInputDialog.getText(
        #     self,
        #     "Export option",
        #     "Chose a name for the file:",
        #     QLineEdit.Normal,
        #     self.default_save_name.split("/")[-1],
        # )
        dialog = SaveDialog(
            parent=self,
            caption="Save As",
            filter="Numpy archive (*.npz);; Matlab format (version < 7) (*.mat);;Text file (*.txt);; Biosiglive format (*.bio)",
            save_method=None,
        )
        file_path = Path(dialog.filename)
        before = {
            "file_path": self.default_save_name,
            "extension": self.default_extension,
            "base_name": self.default_base_name,
        }
        if file_path is not None or file_path != "":
            self.default_save_name = file_path
            self.default_extension = file_path.suffix
            self.default_base_name = self.default_save_name.with_suffix("")
            is_saved = self._save_file()
            if not is_saved:
                self.default_save_name = before["file_path"]
                self.default_extension = before["extension"]
                self.default_base_name = before["base_name"]

    def show_split_windows(self, text):
        """
        Show a popup warning when the user tries to load a long file that may take a long time to process. The warning informs the user about the potential delay and asks if they want to split the file into smaller parts for processing. If the user chooses to split the file, it sets the _split attribute to True, allowing the application to proceed with splitting the file. If the user chooses not to split the file, it sets the _split attribute to False, allowing the application to proceed without splitting.
        """
        popup_warning_split(text, "File loading warning", self.popup_split)

    def popup_split(self, button):
        """
        Options for the popup warning when the user tries to load a long file. If the user clicks "Split", it sets the _split attribute to True, allowing the application to proceed with splitting the file. If the user clicks "Don't split", it sets the _split attribute to False, allowing the application to proceed without splitting.
        """
        self._split = button.text()

    def save(self):
        """
        Save the current file and configuration. It calls the _save_file and _save_config methods to save the processed file and the current configuration, respectively. If any errors occur during the saving process, it logs the error message in the log box.
        """
        try:
            self._save_file()
            # self._save_config()
        except Exception as e:
            self.log_box.log("Error occured while saving the files: ", str(repr(e)))

    def set_saved_ok(self, saved_ok):
        """
        Set the saved_ok attribute to indicate whether the current work is saved or not. If saved_ok is True, it disables the save button in the toolbar, indicating that there are no unsaved changes. If saved_ok is False, it enables the save button in the toolbar, indicating that there are unsaved changes that can be saved.
        """
        self.saved_ok = saved_ok

    def closeEvent(self, event):
        """Intercept the close action to run custom code."""
        self.quit()
        if self._quit:
            event.accept()  # Accept the close event and close the window
        else:
            event.ignore()  # Ignore the close event and keep the window open

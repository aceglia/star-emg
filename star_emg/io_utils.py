import csv
from enum import Enum
from itertools import zip_longest
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from scipy.io import loadmat

from biosiglive import load
from star_emg.processing_utils import filter_data

ArrayLike = np.ndarray


class FileType(Enum):
    TXT = "txt"
    BIO = "bio"
    MAT = "mat"


def write_txt_file(
    data: np.ndarray,
    path: str,
    delimiter: str = "\t",
    headers: list[str] | None = None,
) -> None:
    """
    Write data to a txt file.

    Parameters
    ----------
    data : np.ndarray
        Shape (n_epochs, n_channel, n_sample) or (n_channel, n_sample).
    path : str
        Output file path.
    delimiter : str
        Column delimiter.
    headers : list[str] | None
        Channel names.
    """
    if data.ndim not in (2, 3):
        raise ValueError("Data must be 2D or 3D")

    n_channels = data.shape[-2]

    if headers is None:
        headers = [f"channel_{i}" for i in range(n_channels)]

    # Start with a fresh file
    open(path, "w").close()

    if data.ndim == 3:
        for i, epochs in enumerate(data):
            with open(path, "a", newline="") as file:
                writer = csv.writer(file, delimiter=delimiter)

                writer.writerow(headers)

                # Shape: (n_channels, n_samples) -> rows = samples
                writer.writerows(epochs.T)

                if i < data.shape[0] - 1:
                    file.write("\n")
    else:
        with open(path, "w", newline="") as file:
            writer = csv.writer(file, delimiter=delimiter)

            writer.writerow(headers)

            # Shape: (n_channels, n_samples) -> rows = samples
            writer.writerows(data.T)


def load_txt_file(path: str, delimiter: str = "\t") -> Tuple[ArrayLike, List[str], ArrayLike, float]:
    """
    Load a TXT file.

    Parameters
    ------------
    path : str
    delimiter : str

    Returns
    --------
    tuple[np.ndarray, list[str], np.ndarray, float]
    """
    frames: List[List[List[str]]] = []
    data_rate = None

    with open(path, "r") as file:
        reader = csv.reader(file, delimiter=delimiter)
        rows = []
        len_row: int = -1

        for row in reader:
            len_row = len(row) if len_row == -1 else len_row
            if len(row) != len_row:
                frames.append(rows)
                rows = []
                continue
            rows.append(row)
        if rows:
            frames.append(rows)

    all_len = [len(row) for row in frames]
    channel_names = frames[0][:1][0]

    frames = [row[1 : min(all_len)] for row in frames]

    array = np.array(frames).astype(float)
    array = np.swapaxes(array, 1, 2)
    is_time_vector = check_for_time(array)
    time_vector = None
    if is_time_vector:
        data_rate = 1 / np.mean(np.diff(array[:, 0, :], axis=-1))
        channel_names = channel_names[1:]
        time_vector = array[:, 0, :]
        array = array[:, 1:, :]
    frame_idx = np.arange(0, len(frames))

    return array, channel_names, frame_idx, data_rate, time_vector


def check_for_time(data: np.ndarray) -> bool:
    """
    Check if the first column of the array is a time vector.

    Parameters
    ----------
    data : np.ndarray
        The input array to check.
    """
    if data.shape[1] < 2:
        return False
    return np.allclose(data[0, 0, 1], data[0, 0, 0] + np.diff(data[0, 0, :]).mean(), atol=1e-6)


def load_csv_file(path: str, delimiter: str = "\t") -> Tuple[ArrayLike, List[str], int, float]:
    """
    Load a CSV file.

    Parameters
    ------------
    path : str
    delimiter : str

    Returns
    --------
    tuple[np.ndarray, list[str], int, float]
    """
    rows = []

    with open(path, newline="") as file:
        reader = csv.reader(file, delimiter=delimiter)
        headers = next(reader)

        for row in reader:
            rows.append(row)

    array = np.array(rows).astype(float).T
    array = array[None]

    channel_names = headers
    frames = 1

    data_rate = None

    if headers[0] == "time":
        data_rate = 1 / np.mean(np.diff(array[0, :, 0]))
        channel_names = headers[1:]
        array = array[:, 1:, :]

    array[array == None] = np.nan

    return array, channel_names, frames, data_rate  # type: ignore


def ensure_array_dim(array: ArrayLike) -> ArrayLike:
    """
    Ensure array has 3 dimensions.

    Parameters
    ------------
    array : np.ndarray

    Returns
    --------
    np.ndarray
    """
    if array.ndim == 1:
        array = array[None, None]
    elif array.ndim == 2:
        array = array[None, :]
    elif array.ndim == 3:
        pass
    else:
        raise RuntimeError("Invalid shape")

    return array


def load_from_dict(data_dic: Dict[str, Any]) -> Tuple[ArrayLike, List[str], int, Optional[float]]:
    """
    Load from dictionary.

    Parameters
    ------------
    data_dic : dict

    Returns
    --------
    tuple
    """
    array = ensure_array_dim(data_dic["values"])
    frames = np.arange(array.shape[0])
    if "channel_names" in data_dic.keys():
        channel_names = data_dic["channel_names"]
    else:
        channel_names = [f"channel_{i}" for i in range(array.shape[1])]
    data_rate = None
    if "data_rate" in data_dic.keys():
        data_rate = data_dic["data_rate"]

    time_vector = None
    if 'time' in data_dic.keys():
        time_vector = data_dic['time'] if data_dic['time'].shape == array[:, 0, :] .shape else None
    return array, channel_names, frames, data_rate, time_vector, data_dic

def load_npz_file(path: str, channel_names: Optional[List[str]] = None) -> Tuple[ArrayLike, List[str], int, float]:
    """
    Load a .npz file.

    Parameters
    ------------
    path : str

    Returns
    --------
    tuple[np.ndarray, list[str], int, float]
    """
    data = np.load(path)
    if not ("values" in data):
        raise ValueError("No recognized data found")
    if channel_names is not None:
        data["channel_names"] = channel_names
    return load_from_dict(data)


def load_bio_file(
    data: str, channel_names: Optional[List[str]] = None
) -> Tuple[ArrayLike, List[str], int, Optional[float]]:
    """
    Load BIO file.

    Parameters
    ------------
    data : str
    channel_names : list[str] or None

    Returns
    --------
    tuple
    """
    loaded = load(data)

    if channel_names is not None:
        loaded["channel_names"] = channel_names

    return load_from_dict(loaded)


def _load_mat_spike(data_dict: dict) -> Tuple[ArrayLike, List[str], List[int], float]:
    """
    Loads mat file generated with the spike software.

    Parameters:
    -----------
    data_dict: dict
        The dictionary containing the data loaded from the .mat file. It is expected to have a specific structure where the keys correspond to channel names and the values contain the signal data and metadata.

     Returns:
     --------
     tuple
         A tuple containing the following elements:
         - array: A numpy array containing the signal data extracted from the .mat file.
         - chanel_names: A list of strings representing the names of the channels in the signal data.
         - frames: A list of integers representing the frame indices corresponding to the signal data.
         - data_rate: A float representing the data rate (sampling frequency) of the signal data.
    """
    channels = [key for key in data_dict.keys() if not key.startswith("__") and key != "file"]
    all_chans = [data_dict[key][0, 0] for key in channels]
    channel_content = list(all_chans[0].dtype.fields.keys())
    chanel_names = [str(chan[channel_content.index("title")][0]) for chan in all_chans]
    data_rate = 1 / float(all_chans[0][channel_content.index("interval")][0][0])
    frames = [0]
    idx_keyboard = [i for i, name in enumerate(chanel_names) if "keyboard" in name.lower()]
    if len(idx_keyboard) != 0:
        idx_keyboard = idx_keyboard[0]
        chanel_names.pop(idx_keyboard)
        all_chans.pop(idx_keyboard)
    list_array = [np.array(chan[channel_content.index("values")]).flatten() for chan in all_chans]
    arr_filled = [list(tpl) for tpl in zip(*zip_longest(*list_array))]
    array = np.vstack(arr_filled)[None, ...]
    array[array == None] = np.nan
    return array, chanel_names, frames, data_rate


def _get_chan_names(chaninfo: np.ndarray) -> List[str]:
    """
    Gets the channel names from the chaninfo structure in the .mat file.
    """
    return [str(chaninfo[i][1][0]) for i in range(chaninfo.shape[0])]


def _load_from_wave_data(wave_data: np.ndarray) -> Tuple[ArrayLike, List[str], List[int], float]:
    """
    Load from data extracted from a .mat file generated with the signal software.

    Parameters:
    -----------
    wave_data: np.ndarray
        The numpy array containing the data extracted from the .mat file. It is expected to have a specific structure where the first element contains the signal data and metadata.

     Returns:
     --------
     tuple
         A tuple containing the following elements:
         - array: A numpy array containing the signal data extracted from the .mat file.
         - chanel_names: A list of strings representing the names of the channels in the signal data.
         - frames: A list of integers representing the frame indices corresponding to the signal data.
         - data_rate: A float representing the data rate (sampling frequency) of the signal data.
    """
    items = list(wave_data[0][0].dtype.fields.keys())
    chanel_names = _get_chan_names(wave_data[0][0][items.index("chaninfo")].reshape(-1))
    frames = list(range(wave_data[0][0][items.index("frames")][0][0]))
    data_rate = 1 / wave_data[0][0][items.index("interval")][0][0]
    array = wave_data[0][0][items.index("values")]
    array = np.swapaxes(array, 0, -1)
    return array, chanel_names, frames, data_rate


def load_mat_file(path: str) -> Tuple[ArrayLike, List[str], List[int], float]:
    """
    Loads data from a mat file. Mat file can be generated with the signal or spike software.
    Parameters:
    -----------
    path : str
       The file path to the .mat file to be loaded. The method will attempt to load the data from the specified file path and extract the relevant signal data, channel names, frame indices, and data rate based on the structure of the .mat file.
    Returns:
    --------
    tuple
        A tuple containing the following elements:
        - array: A numpy array containing the signal data extracted from the .mat file.
        - chanel_names: A list of strings representing the names of the channels in the signal data.
        - frames: A list of integers representing the frame indices corresponding to the signal data.
        - data_rate: A float representing the data rate (sampling frequency) of the signal data.
    """
    try:
        mat_file = loadmat(path)
    except Exception:
        raise ValueError("Cannot load .mat file")

    if "file" in mat_file:
        file_name = str(mat_file["file"][0, 0][0][0])
        if "smr" in file_name.split(".")[-1]:
            return _load_mat_spike(mat_file)

    wave_key = [key for key in mat_file if "wave_data" in key][0]

    if len(wave_key) > 0:
        return _load_from_wave_data(mat_file[wave_key])

    raise ValueError("No recognized data found")

def load_npz_file(path: str) -> Tuple[ArrayLike, List[str], List[int], float]:
    """
    Loads data from a npz file.

    Parameters:
    -----------
    path : str
       The file path to the .npz file to be loaded. The method will attempt to load the data from the specified file path and extract the relevant signal data, channel names, frame indices, and data rate based on the structure of the .npz file.

    Returns:
    --------
    tuple
        A tuple containing the following elements:
        - array: A numpy array containing the signal data extracted from the .npz file.
        - chanel_names: A list of strings representing the names of the channels in the signal data.
        - frames: A list of integers representing the frame indices corresponding to the signal data.
        - data_rate: A float representing the data rate (sampling frequency) of the signal data.
    """
    try:
        npz_file = np.load(path, allow_pickle=True)
    except Exception:
        raise ValueError("Cannot load .npz file")

    if "values" in npz_file and "channel_names" in npz_file and "data_rate" in npz_file:
        return load_from_dict(npz_file)

    raise ValueError("No recognized data found")

def load_pkl_file(path: str) -> Tuple[ArrayLike, List[str], List[int], float]:
    """
    Loads data from a pkl file.

    Parameters:
    -----------
    path : str
       The file path to the .pkl file to be loaded. The method will attempt to load the data from the specified file path and extract the relevant signal data, channel names, frame indices, and data rate based on the structure of the .pkl file.

    Returns:
    --------
    tuple
        A tuple containing the following elements:
        - array: A numpy array containing the signal data extracted from the .pkl file.
        - chanel_names: A list of strings representing the names of the channels in the signal data.
        - frames: A list of integers representing the frame indices corresponding to the signal data.
        - data_rate: A float representing the data rate (sampling frequency) of the signal data.
    """
    try:
        import pickle
    except ImportError:
        raise ImportError("pickle module is not available")

    try:
        with open(path, "rb") as f:
            pkl_file = pickle.load(f)
    except Exception:
        raise ValueError("Cannot load .pkl file")

    if "values" in pkl_file and "channel_names" in pkl_file and "data_rate" in pkl_file:
        return load_from_dict(pkl_file)

    raise ValueError("No recognized data found")


class DataLoader:
    """
    Class for loading and processing data from various file formats. The DataLoader class can handle data in the form of file paths (strings) or directly as numpy arrays. It provides functionality for loading data, applying filtering, and managing data shapes for further processing. The class also includes methods for exporting processed data to CSV format.
    """

    def __init__(
        self,
        data: Union[str, ArrayLike],
        ignore_filtering: bool = False,
        **kwargs: Any,
    ) -> None:
        """
        Initializes the DataLoader instance by determining the type of input data (file path or numpy array) and loading the data accordingly. The method also retrieves data parameters and filtering parameters from the provided keyword arguments, applies filtering to the data if specified, and manages the shape of the data for further processing. If the stack_epochs option is enabled and the initial data has more than one frame, it applies stacking to the epochs dimension of the data.
        Parameters:
        -----------
        data: str or np.ndarray
            The input data to be loaded, which can be either a file path (string) pointing to a supported file format or a numpy array containing the signal data.
        stack_epochs: bool, optional
            A flag indicating whether to stack the epochs dimension of the data if it has more than one frame. If set to True, the method will apply stacking to the epochs dimension of the data, which can be useful for certain processing techniques that require a specific data shape.
        ignore_filtering: bool, optional
            A flag indicating whether to ignore the filtering step when loading the data. If set to True no filtering will be applied to the data, and the raw data will be loaded directly without any preprocessing. If set to False, the method will apply the specified filtering parameters to the data during the loading process.
        **kwargs: dict
            The expected dict can contain the following keys:
            - delimiter: The delimiter used in the file format (e.g., "\t" for .txt files).
            - channel_names: A list of strings representing the names of the channels in the signal data.
            - data_rate: A float representing the data rate (sampling frequency) of the signal data.
            - data_window: A tuple representing the start and end indices of the data window to be loaded.
            - cutoff: The cutoff frequency for filtering the data.
            - order: The order of the filter to be applied to the data.
            - center: Wether to center the data before filtering.
            - signal_filter: Wether to apply filtering to the data after artifact removal.
        Returns:
        --------
        None

        """
        self.path = data if isinstance(data, str) else None
        self.data = data if isinstance(data, np.ndarray) else None
        self.a, self.b = None, None
        self.gap_free = True
        self.stack_epochs_applied = False
        self._unstack_shape = None
        self.init_data = None
        self.frames = []
        self.channel_names = []
        self.loaded_data = None
        self.data_rate = None
        self.time_vector = None

        self.get_data_params(**kwargs)
        self.get_filtering_params(**kwargs)

        if self.path is not None or self.data is not None:
            self.load_data(ignore_filtering=ignore_filtering)

    def _apply_stack_epochs(self) -> None:
        """
        Applies stacking to the epochs dimension of the data. This method is called when the stack_epochs option is enabled and the initial data has more than one frame. It manages the shape of the data by swapping axes and reshaping it to create a new epochs dimension, allowing for further processing techniques that require a specific data shape.
        """
        self._unstack_shape = self.init_data.shape
        self.stack_epochs_applied = True
        if len(self.init_data.shape) != 3:
            return
        self.init_data = np.swapaxes(self.init_data, 0, 1)
        self.init_data = self.init_data.reshape(self.init_data.shape[0], -1)

    def get_unstacked_data(self) -> None:
        """
        Gets the unstacked data if the stack_epochs option was applied. This method is used to retrieve the original data shape after stacking has been applied to the epochs dimension. If the stack_epochs option was enabled and the initial data was reshaped, this method will reverse the stacking process by swapping axes and reshaping the data back to its original shape, allowing for further analysis or processing in its original format.
        """
        if self.stack_epochs_applied:
            data = self.init_data.reshape(self._unstack_shape[1], self._unstack_shape[0], self._unstack_shape[2])
            data = np.swapaxes(data, 0, 1)
            return data
        else:
            return self.init_data

    def get_filtering_params(self, **kwargs) -> None:
        """
        Gets the filtering parameters from the provided keyword arguments. This method retrieves the filtering parameters such as cutoff frequency, filter order, centering option, and signal filtering option from the keyword arguments and stores them in a dictionary attribute of the DataLoader class. These parameters will be used later when applying filtering to the data during the loading process or when explicitly calling the apply_filtering method.
        """
        filtering_params = ["cutoff", "order", "center", "signal_filter"]
        default = [450.0, 2, True, True]
        self.filtering_params = {}
        for k, key in enumerate(filtering_params):
            self.filtering_params[key] = kwargs.get(key, default[k])
        self.__dict__.update(self.filtering_params)

    def get_data_params(self, **kwargs) -> None:
        """
        Gets the loading parameters from the provided keyword arguments. This method retrieves the loading parameters such as delimiter, channel names, data rate, and data window from the keyword arguments and stores them in a dictionary attribute of the DataLoader class. These parameters will be used later when loading the data from files or when explicitly calling the load_data method to ensure that the data is loaded correctly based on the specified parameters.
        """
        data_params = ["delimiter", "channel_names", "data_rate", "data_window"]
        default = ["\t", None, None, None]
        self.loading_params = {}
        for k, key in enumerate(data_params):
            self.loading_params[key] = kwargs.get(key, default[k])
        self.__dict__.update(self.loading_params)

    def _load_files(self) -> None:
        """
        Loads file and set attrbutes data, channel_names, frames, and data_rate. This method is responsible for loading the data from the specified file path based on the file format (such as .txt, .bio, .mat, or .csv). It uses the appropriate loading function for each file format to extract the signal data, channel names, frame indices, and data rate from the file. If the data rate is not provided in the file and is specified in the loading parameters, it will use the provided data rate. If neither is available, it raises a ValueError indicating that the data rate must be provided if not loaded from the file.
        """
        self.time_vector = None
        self.loaded_data = None

        if self.path.endswith(".txt"):
            self.data, self.channel_names, self.frames, self.data_rate, self.time_vector = load_txt_file(
                self.path, self.delimiter
            )
        elif self.path.endswith(".bio"):
            self.data, self.channel_names, self.frames, self.data_rate, self.time_vector, self.loaded_data = load_bio_file(self.path, self.channel_names)
        elif self.path.endswith(".mat"):
            self.data, self.channel_names, self.frames, self.data_rate, self.loaded_data = load_mat_file(self.path)
        elif self.path.endswith(".csv"):
            self.data, self.channel_names, self.frames, self.data_rate = load_csv_file(self.path, self.delimiter)
        elif self.path.endswith(".npz"):
            self.data, self.channel_names, self.frames, self.data_rate, self.time_vector, self.loaded_data = load_npz_file(self.path)
        elif self.path.endswith(".pkl"):
            self.data, self.channel_names, self.frames, self.data_rate, self.time_vector, self.loaded_data = load_pkl_file(self.path)
        else:
            raise ValueError("File format not supported")
        if self.data_rate is None and self.loading_params["data_rate"] is not None:
            self.data_rate = self.loading_params["data_rate"]
        elif self.data_rate is None:
            raise ValueError("Data rate must be provided if not loaded from file")
        if self.loaded_data is not None:
            self.loaded_data = self._extract_items(self.loaded_data)

        if self.time_vector is None:
            self.time_vector = np.repeat(
                (np.arange(0, self.data.shape[-1]) / self.data_rate)[None],
                self.data.shape[0],
                axis=0,
            )

    def _extract_items(self, data_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts items when saved with numpy archive. This method extracts items from a dictionary and returns a new dictionary with the extracted items.
        """
        extracted = {}
        for key, value in data_dict.items():
            if isinstance(value, np.ndarray):
                extracted[key] = value.item() if value.size == 1 else value
            else:
                extracted[key] = value
        return extracted


    def load_data(self, ignore_filtering: bool = False) -> None:
        """
        Loads the data and applies filtering if specified. This method is responsible for loading the data from the file if a file path is provided, and then applying filtering to the data based on the specified filtering parameters. If the ignore_filtering flag is set to True, it will skip the filtering step and load the raw data directly. After loading and optionally filtering the data, it initializes the time attribute based on the data rate and sets a flag indicating that the data has been loaded successfully.
        Parameters:
        -----------
        ignore_filtering: bool, optional
            A flag indicating whether to ignore the filtering step when loading the data. If set to True, the method will skip the filtering process and load the raw data directly without any preprocessing. If set to False, the method will apply the specified filtering parameters to the data during the loading process, allowing for further analysis or processing on the filtered data.
        """
        if self.path is not None:
            self._load_files()

        if self.data_rate is None:
            raise ValueError("Data rate must be provided")

        self.init_data = self.apply_filtering() if not ignore_filtering else self.data  # type: ignore

        self.time = np.repeat(
            (np.arange(0, self.init_data.shape[-1]) / self.data_rate)[None],
            self.init_data.shape[0],
            axis=0,
        )
        self.gap_free = self.init_data.shape[0] == 1

        self.is_data_loaded = True

    def apply_filtering(self, data: Optional[ArrayLike] = None, offline: bool = True) -> ArrayLike:
        """ "
        Applies filtering to the data based on the specified filtering parameters. This method takes an optional data argument, which if provided, will be used for filtering instead of the data loaded from the file. It applies centering and filtering to the data using the center_and_filter function, which utilizes the specified cutoff frequency, filter order, centering option, signal filtering option, and data rate. The filtered data is then returned as a numpy array for further analysis or processing.

        Parameters:
        -----------
        data: np.ndarray, optional
            An optional numpy array containing the data to be filtered. If provided, this data will be used for filtering instead of the data loaded from the file. If not provided, the method will use the data attribute of the DataLoader instance for filtering.

        Returns:
        --------
        np.ndarray
            The filtered data as a numpy array after applying centering and filtering based on the specified parameters.
        """
        to_filter = data if data is not None else self.data  # type: ignore
        return self.center_and_filter(
            to_filter,
            center=self.center,
            signal_filter=self.signal_filter,
            cutoff=self.cutoff,
            fs=self.data_rate,
            order=self.order,
            offline=offline,
        )

    def center_and_filter(
        self,
        data: ArrayLike,
        center: bool = True,
        signal_filter: bool = False,
        cutoff: Union[float, List[float]] = 450.0,
        fs: float = 2000,
        order: int = 2,
        offline=True,
    ) -> ArrayLike:
        """
        Center and optionally filter a signal.

        Parameters
        ------------
        data : np.ndarray
        center : bool
        signal_filter : bool
        cutoff : float or list[float]
        fs : float
        order : int

        Returns
        --------
        np.ndarray
        """
        if center:
            data -= np.nanmean(data, axis=-1, keepdims=True)

        if signal_filter:
            filter_type = "band" if isinstance(cutoff, list) else "low"
            raise_error = False

            if filter_type == "low" and (cutoff / fs) >= 0.5:
                raise_error = True
            elif filter_type == "band" and (cutoff[1] / fs) >= 0.5:
                raise_error = True

            if raise_error:
                raise RuntimeError(f"Filter cutoff ({cutoff}) is not suitable for the frequency ({fs}).")

            data, self.a, self.b = filter_data(data, cutoff, order, fs, filter_type, offline, self.a, self.b)

        return data

    def flatten_data(self, data: ArrayLike) -> ArrayLike:
        """ "
        Flattens the data by reshaping it to have a shape of (num_channels x num_epochs, num_samples) while preserving the original data shape for later use.

        Parameters:
        -----------
        data: np.ndarray
            The input data to be flattened, which is expected to have a shape of (num_frames, num_channels, num_samples). The method will reshape this data to have a shape of (num_channels x num_epochs, num_samples) while keeping track of the original data shape for later use when unflattening the data back to its original format.

        Returns:
        --------
        np.ndarray
            The flattened data as a numpy array with a shape of (num_channels x num_epochs, num_samples), where num_epochs is the number of frames in the original data. The original data shape is stored in an attribute for later use when unflattening the data back to its original format.
        """
        self._data_shape = data.shape
        return data.reshape(-1, data.shape[-1])

    def unflatten_data(self, data: ArrayLike, data_shape: Optional[Tuple[int, ...]] = None) -> ArrayLike:
        """
        Unflattens the data by reshaping it back to its original shape based on the stored data shape or a provided data shape.

         Parameters:
        -----------
        data: np.ndarray
            The input data to be unflattened, which is expected to have a shape of (num_channels x num_epochs, num_samples). The method will reshape this data back to its original shape based on the stored data shape from when the data was flattened or a provided data shape if specified.
        data_shape: tuple, optional
            An optional tuple specifying the original data shape to be used for unflattening the data. If provided, this data shape will be used to reshape the data back to its original format. If not provided, the method will use the stored data shape from when the data was flattened to reshape the data back to its original format.

        Returns:
        --------
        np.ndarray
            The unflattened data as a numpy array reshaped back to its original format based on the stored data shape or the provided data shape. The method ensures that the data is reshaped correctly to match the original dimensions of the data before it was flattened.
        """

        shape = data_shape or self._data_shape
        return data.reshape(shape)


def export_csv(
    path: str,
    raw_data: ArrayLike,
    processed_data_svd: ArrayLike,
    processed_data_notch: ArrayLike,
    channels: List[str],
    rate: float,
) -> None:
    """
    Export data to text like file. This specific format is aimed to be used with Signal software but can be adapted for other software as well. The method takes the raw data, processed data from SVD and notch filtering, channel names, and data rate as input and exports the data to a CSV file at the specified path. The exported CSV file includes the raw data, processed data, channel names, and comments about the data rate, number of frames, and samples per frame for easy analysis and visualization in compatible software.

    Parameters
    ------------
    path : str
        The path to export the data
    raw_data : np.ndarray
        The raw data to be exported
    processed_data_svd : np.ndarray
        The data processed with SVD to be exported
    processed_data_notch : np.ndarray
        The data processed with notch filtering to be exported
    channels : list[str]
        The list of channel names corresponding to the data
    rate : float
        The data rate (sampling frequency) of the data being exported

    Returns
    --------
    None
    """
    final_mat: Optional[ArrayLike] = None

    for data in [raw_data, processed_data_notch, processed_data_svd]:
        data_stacked = data.transpose(1, 0, -1)
        data_stacked = data_stacked[:, :, :-1].reshape(raw_data.shape[1], -1)
        final_mat = data_stacked if final_mat is None else np.vstack((final_mat, data_stacked))

    channels.extend(sum([], [c + "_notch_processed" for c in channels] + [c + "_svd_processed" for c in channels]))

    comments = f"Data rate: {rate} | {raw_data.shape[0]} frames | {raw_data.shape[-1]} samples per frame\n"

    np.savetxt(
        path.replace(".mat", ".txt"),
        final_mat.T,
        header=comments + "\t".join(channels),
        delimiter="\t",
        comments="",
    )

import os
from pathlib import Path

import numpy as np
import multiprocessing as mp
from biosiglive.streaming.utils import CircularBuffer
import shutil

try:
    import zarr
except ImportError:
    zarr = None


class ChannelState:
    """
    State of one acquisition channel.
    """

    def __init__(self, channel: int, buf_size: int, dt: float):
        self.channel = channel
        self.buffer = CircularBuffer(2, buf_size)  # buffer for raw data
        self.last_t = -np.inf
        self.pending_config = []
        self.dt = dt

    def append(self, t0, raw, processed, config=None):
        n = len(raw)
        t = t0 + (np.arange(n) * self.dt)  # replaced later
        self.buffer.append(x=np.vstack([raw, processed]), t=t)
        self.last_t = t[-1]
        if config is not None:
            config["t"] = t0
            config["channel"] = self.channel
            self.pending_config.append(config)

    def get(self):
        data, t = self.buffer.get()
        return data[0], data[1], t  # raw, processed, t

    def get_pending_config(self):
        configs = self.pending_config
        self.pending_config = []
        return configs

    def get_t_range(self, t_start, t_stop):
        data, t = self.buffer.get()
        mask = (t >= t_start) & (t < t_stop)
        d, t = data[:, mask], t[mask]
        return d[0], d[1], t  # raw, processed, t


class StreamSave:
    def __init__(
        self,
        save_path=None,
        use_zarr=False,
        compress=True,
        compression_level=3,
        # logbox=None
    ):
        # self.logbox = logbox
        self.last_saved_t = 0
        self.save_path = save_path if save_path is not None else Path(".tmp_stream") / "recording.zarr"
        self.use_zarr = use_zarr
        if use_zarr and zarr is None:
            raise ImportError("Zarr is not installed. Please install it to use this feature.")
        self.compress = compress
        self.compression_level = compression_level
        self.data_queue = None
        self._save_ok = True
        # create folder for temporary zarr dataset and then hide it
        self._tmp_folder = ".tmp_stream"
        os.makedirs(self._tmp_folder, exist_ok=True)
        os.system(f'attrib +h "{self._tmp_folder}"')
        self.zarr_recorder = None

    def init_stream(self, n_channels, data_rate, channel_names=None, chunk_duration=5.0):
        if self._save_ok is False:
            pass  # add a popup windows
        self._save_ok = False
        self.n_chanels = n_channels
        self.data_rate = data_rate
        self.dt = 1 / data_rate
        self.channels_name = channel_names if channel_names is not None else [f"ch_{i}" for i in range(n_channels)]
        self.chunk_duration = chunk_duration
        self.chunk_samples = int(round(chunk_duration * data_rate))
        self.buffer_len = self.chunk_samples * 2  # some extra time to avoid losing data at the end of the recording
        self.states = {ch: ChannelState(ch, int(self.buffer_len), self.dt) for ch in range(n_channels)}

    def flush_chunk(self, root=None):
        raw = []
        processed = []
        config = []
        time = np.arange(self.chunk_samples) * self.dt + self.last_saved_t
        for state in self.states.values():
            r, p, t = state.get_t_range(self.last_saved_t, self.last_saved_t + self.chunk_duration)
            if time.shape[0] != t.shape[0]:
                time = t
            raw.append(r)
            processed.append(p)
            config.extend(state.get_pending_config())
        try:
            raw = np.vstack(raw)
            processed = np.vstack(processed)
        except Exception as e:
            print(f"Error occurred while stacking data: {str(repr(e))}")
            return
        self.append_to_zarr(raw, processed, time, config=config)

    def append_to_zarr(self, raw: np.ndarray, processed: np.ndarray, time: np.ndarray, config=[]) -> None:
        """
        Append one chunk of data to the Zarr store.

        Parameters
        ----------
        raw : np.ndarray
            Raw data of shape (n_channels, n_samples).
        processed : np.ndarray
            Processed data of shape (n_channels, n_samples).
        time : np.ndarray
            Time vector of shape (n_samples,).
        """
        n_samples = raw.shape[1]
        assert raw.shape == processed.shape
        assert time.shape[0] == n_samples

        self.zarr_recorder.append_signals(raw, processed, time)

        for cfg in config:
            self.zarr_recorder.append_config(cfg.pop("channel"), cfg.pop("t"), cfg)
        return self.zarr_recorder.get_size()

    def ready_until(self):
        return min(s.last_t for s in self.states.values())

    def add_packet(self, packet):
        state = self.states[packet["ch"]]
        raw = np.asarray(packet["raw"])
        processed = np.asarray(packet["processed"])
        n = len(raw)
        t = packet["t0"] + np.arange(n) * self.dt
        config = packet.get("config", None)
        state.append(t0=packet["t0"], raw=raw, processed=processed, config=config)
        state.last_t = t[-1]
        self.try_flush()

    def try_flush(self):
        if self.ready_until() - self.last_saved_t >= self.chunk_duration:
            self.flush_chunk()
            self.last_saved_t += self.chunk_duration

    def run(self, queue, channels, data_rate, finish_saving_event):
        self.init_stream(n_channels=len(channels), data_rate=data_rate, channel_names=channels)
        self._init_zarr() if self.use_zarr else None
        # ready_event.set()
        # self.parent.parent.log_box.log("Zarr writer is ready to receive data.")
        while True:
            try:
                packet = queue.get(timeout=0.1)
                self.add_packet(packet)
            except Exception as e:
                if not isinstance(e, mp.queues.Empty):
                    print(f"save_utils: error while saving", str(repr(e)))
                    break
                elif self.ready_until() - self.last_saved_t > 0:
                    self.flush_remaining()
                    break
        if self.save_path is not None:
            self.convert_to_file(self.save_path)
        finish_saving_event.set()

    def flush_remaining(self):
        """
        Flush the remaining data in the buffer to the Zarr store.
        """
        while self.ready_until() - self.last_saved_t > 0:
            self.flush_chunk()
            self.last_saved_t += self.chunk_duration

    def _init_zarr(self):
        """
        Initialize the Zarr store.

        Structure
        ---------
        recording.zarr/
        │
        ├── raw
        ├── processed
        ├── time
        ├── events/
        │     ├── timestamp
        │     ├── channel
        │     ├── type
        │     └── payload
        └── attrs
        """
        self.zarr_recorder = ZarrRecording(
            self.save_path,
            n_channels=self.n_chanels,
            sampling_rate=self.data_rate,
            channel_names=self.channels_name,
            chunk_seconds=self.chunk_duration,
        )
        return self.zarr_recorder.root

    def convert_to_file(self, output_path, zarr_ds_path=None):
        """
        Convert the Zarr dataset to a single file (e.g., .npz or .h5).

        Parameters
        ----------
        output_path : str
            Path to the output file.
        """
        if output_path is None and self.save_path is None:
            raise ValueError("Output path is not specified.")

        if self.zarr_recorder is None and zarr_ds_path is None:
            raise ValueError("Zarr recorder is not initialized.")

        if zarr_ds_path is not None:
            zarr_ds = ZarrRecording.load_dataset(zarr_ds_path)
        else:
            zarr_ds = self.zarr_recorder

        raw = zarr_ds.root["signals"]["raw"][:]
        processed = zarr_ds.root["signals"]["processed"][:]
        time = zarr_ds.root["signals"]["time"][:]
        meta = dict(zarr_ds.root.attrs)
        configs = zarr_ds.read_all_configs()
        self._save_ok = True
        # remove the temporary Zarr dataset
        # if self._tmp_path.exists():
        #     shutil.rmtree(self._tmp_folder)


class ZarrRecording:
    def __init__(
        self,
        path: str,
        n_channels: int,
        sampling_rate: float,
        channel_names: list[str],
        chunk_seconds: float = 5.0,
        root=None,
    ):
        self.path = Path(path)
        self.n_channels = n_channels
        self.sampling_rate = sampling_rate
        self.chunk_samples = int(chunk_seconds * sampling_rate)
        self.root = root if root is not None else self._create_dataset(channel_names)

    # ------------------------------------------------------------------
    # Dataset creation
    # ------------------------------------------------------------------

    def _create_dataset(self, channel_names):

        root = zarr.open(self.path, mode="w")

        # ==============================================================
        # Global metadata
        # ==============================================================

        root.attrs.update(
            {
                "sampling_rate": self.sampling_rate,
                "n_channels": self.n_channels,
                "channel_names": channel_names,
                "format_version": "1.0",
            }
        )

        # ==============================================================
        # Signals
        # ==============================================================

        signals = root.create_group("signals")

        signals.create_array(
            "raw",
            shape=(self.n_channels, 0),
            chunks=(self.n_channels, self.chunk_samples),
            dtype=np.float64,
        )

        signals.create_array(
            "processed",
            shape=(self.n_channels, 0),
            chunks=(self.n_channels, self.chunk_samples),
            dtype=np.float64,
        )

        signals.create_array(
            "time",
            shape=(0,),
            chunks=(self.chunk_samples,),
            dtype=np.float64,
        )

        # ==============================================================
        # Configurations
        # ==============================================================
        root.create_group("configs")
        for ch in range(self.n_channels):
            root["configs"].create_group(f"channel_{ch:02d}")

        return root

    # ------------------------------------------------------------------
    # Append signals
    # ------------------------------------------------------------------

    def append_signals(
        self,
        raw: np.ndarray,
        processed: np.ndarray,
        time: np.ndarray,
    ):

        sig = self.root["signals"]

        sig["raw"].append(raw, axis=1)
        sig["processed"].append(processed, axis=1)
        sig["time"].append(time)

    # ------------------------------------------------------------------
    # Save a configuration snapshot
    # ------------------------------------------------------------------
    def append_config(
        self,
        channel: list[int] | int,
        timestamp: float,
        parameters: dict,
    ):
        if isinstance(channel, list):
            for ch in channel:
                self.append_config(ch, timestamp, parameters)
            return

        channel_group = self.root["configs"][f"channel_{channel:02d}"]

        cfg_id = len(channel_group)

        cfg = channel_group.create_group(f"{cfg_id}")

        cfg.attrs["timestamp"] = float(timestamp)

        for key, value in parameters.items():
            if isinstance(value, np.ndarray):
                cfg.create_array(key, data=value)
            else:
                cfg.attrs[key] = value

    def read(
        self,
        channels=None,
        sample_slice=slice(None),
        processed=True,
    ):
        """
        Read a subset of the recording.

        Parameters
        ----------
        channels : int | list[int] | None
            Channels to read.
        sample_slice : slice
            Samples to read.
        processed : bool
            Read processed or raw signal.
        """

        signal_name = "processed" if processed else "raw"

        signals = self.root["signals"]

        if channels is None:
            channels = slice(None)

        data = signals[signal_name][channels, sample_slice]
        time = signals["time"][sample_slice]

        return data, time

    def read_time(
        self,
        t_start,
        t_stop,
        channels=None,
        processed=True,
    ):

        time = self.root["signals"]["time"][:]

        start = np.searchsorted(time, t_start)
        stop = np.searchsorted(time, t_stop)
        return self.read(
            channels=channels,
            sample_slice=slice(start, stop),
            processed=processed,
        )

    def read_config(self, channel: int, config_id: int) -> dict:
        """
        Read one configuration snapshot and return it as a dictionary.

        Parameters
        ----------
        channel : int
            Channel number.
        config_id : int
            Configuration index.

        Returns
        -------
        dict
            Configuration parameters.
        """

        cfg_path = f"configs/channel_{channel:03d}/{config_id:06d}"

        cfg = self.root[cfg_path]

        config = dict(cfg.attrs)

        # Read array parameters
        for key in cfg.array_keys():
            config[key] = cfg[key][:]

        return config

    def read_all_configs(self) -> dict:
        """
        Read all configuration snapshots for all channels.

        Returns
        -------
        dict
            Dictionary organized as:

            {
                "channel_xxx": {
                    config_id: {
                        parameter: value
                    }
                }
            }
        """

        all_configs = {}

        configs = self.root["configs"]

        for channel_name in configs.group_keys():

            channel_group = configs[channel_name]

            all_configs[channel_name] = {}

            for config_name in channel_group.group_keys():
                cfg = channel_group[config_name]
                config = dict(cfg.attrs)
                # Load array parameters
                for key in cfg.array_keys():
                    value = cfg[key][:]
                    # convert numpy arrays to lists
                    if value.ndim == 1:
                        value = value.tolist()

                    config[key] = value

                config_id = int(config_name)

                all_configs[channel_name][config_id] = config

        return all_configs

    def get_duration(self):
        """
        Get the size of the recording in seconds.
        """
        time = self.root["signals"]["time"][:]
        if len(time) == 0:
            return 0.0
        return float(time[-1] - time[0])

    def get_size(self):
        """
        Get the size of the recording in samples.
        """
        return self.root["signals"]["raw"].shape[1]

    @classmethod
    def load_dataset(cls, path):
        """
        Load an existing recording dataset.

        Parameters
        ----------
        path : str
            Path to the recording dataset.
        """

        root = zarr.open(path, mode="r")
        return cls(
            path=path,
            root=root,
            n_channels=root.attrs["n_channels"],
            sampling_rate=root.attrs["sampling_rate"],
            channel_names=root.attrs["channel_names"],
        )

    def close(self):
        """
        Close the Zarr dataset.
        """
        self.root.store.close()

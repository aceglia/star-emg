# Data formats

`StAR-EMG` reads EMG recordings from several file formats, or directly from
NumPy arrays. This page describes what each format must contain and how the
sampling rate is determined.

## Data layout

Internally, all data are arrays of shape `(n_epochs, n_channels, n_samples)`
(see {doc}`concepts`). Files with a single recording simply have one epoch.

The **sampling rate** (`data_rate`, in Hz) is required. It is read from the
file when the format provides it, and otherwise it must be given by you:

* in Python, with the `data_rate=` argument;
* in the GUI, in the *Sample rate (Hz)* field of the **Filter** dialog.

If the rate can neither be read nor is provided, loading stops with the error
*"Data rate must be provided if not loaded from file"*.

## Supported file formats

| Extension | Format                         | Epochs | Sampling rate read from file |
|-----------|--------------------------------|--------|------------------------------|
| `.txt`    | Delimited text (tab by default) | Several | Only if a time column is present |
| `.csv`    | Delimited text with header      | One    | Only if a `time` column is present |
| `.bio`    | BioSigLive file                 | Several | If `data_rate` is stored |
| `.mat`    | MATLAB file from CED Signal or Spike2 | Several (Signal frames) | Yes |
| `.npz`    | NumPy archive                   | Several | Yes (`data_rate` key) |

The `examples` folder of the repository contains sample files that you can use as
a template. It contains also a python file with all writing and loading data file format. 
The file "file_io.py" contains the functions to read and write the files formats. 

```{note}
The stream mode of the GUI save data in a `zarr` dataset format. It can be convert to `.npz` file using the `Load stream` option in the file menu. 
```

### Text files (`.txt`)

A text file contains a header line with the channel names, followed by one
line per sample and one column per channel. The default delimiter is a tab
(`"\t"`); use the `delimiter=` argument for something else.

```text
EMG1	EMG2
-9.0e-06	1.2e-05
-1.1e-05	1.0e-05
-1.1e-05	9.0e-06
...
```

* **Several epochs.** Put the epochs one after the other, separated by an
  empty line, each one starting with its own header line.
* **Time column.** If the first column is a time vector (regularly increasing
  values), it is detected automatically. The sampling rate is then computed
  from the time stamps (the inverse of the mean time step), the column is
  removed from the data, and its header is dropped from the channel names.
* The `write_txt_file` helper writes an array in this format:

  ```python
  from star_emg.io_utils import write_txt_file

  # data: (n_epochs, n_channels, n_samples) or (n_channels, n_samples)
  write_txt_file(data, "recording.txt", headers=["EMG1", "EMG2"])
  ```

### CSV files (`.csv`)

Same layout as text files (header line, one line per sample), but a CSV file
holds a single epoch. If the first header is exactly `time`, the first column
is read as time (in seconds), used to compute the sampling rate, and removed
from the data.

### BioSigLive files (`.bio`)

[BioSigLive](https://github.com/aceglia/biosiglive) files are efficient to
write in real time and are the format used by the synthetic artifact
generator. A `.bio` file stores a dictionary with the following keys:

| Key             | Content                                                    | Required |
|-----------------|------------------------------------------------------------|----------|
| `values`        | Array of 1, 2 or 3 dimensions (`samples`, `channels × samples` or `epochs × channels × samples`) | Yes |
| `data_rate`     | Sampling rate in Hz                                        | No, if you provide it elsewhere |
| `channel_names` | List of channel names                                      | No (names default to `channel_0`, `channel_1`, ...) |

```python
import numpy as np
from biosiglive import save

emg = np.random.randn(2, 100_000)            # 2 channels
save({"values": emg, "data_rate": 2000.0, "channel_names": ["TA", "SOL"]},
     "recording.bio", safe=False)
```

### MATLAB files (`.mat`)

`.mat` files exported from the CED software are supported:

* **Signal**: files containing a `wave_data` variable. Channel names, number
  of frames (loaded as epochs), sampling interval and values are read from the
  structure.
* **Spike2**: files exported from a `.smr` recording. Channel titles and the
  sampling interval are read from each channel. A channel named *Keyboard* is
  ignored. If channels have different lengths, the shorter ones are padded
  with `NaN`.

### NumPy files (`.npz`)

An `.npz` archive must contain three arrays: `values` (1-D, 2-D or 3-D),
`channel_names` and `data_rate`.

```python
import numpy as np

np.savez("recording.npz",
         values=emg[None],                     # (1, n_channels, n_samples)
         channel_names=np.array(["TA", "SOL"]),
         data_rate=2000.0)
```

### Zarr files (`.zarr`)
Zarr files are a format for storing large arrays in a distributed way. They are saved in a directory tree and
can be read and written using the `zarr` library.
```python
from star_emg.app.save_utils import ZarrRecording
from numcodecs import blosc
blosc.use_threads = False
blosc.set_nthreads(1)

if __name__ == "__main__":
    zarr_ds = ZarrRecording.load_dataset("data/test.stream")
    meta = dict(zarr_ds.root.attrs)
    print(meta)
    data_dict, configs = zarr_ds.to_dict() # returns a dictionary with the data and the filtering use during the stream
```

## Using arrays directly

In Python you can skip files and pass an array. Provide the sampling rate with
`data_rate`:

```python
from star_emg.automatic_remover import ArtifactRemover

remover = ArtifactRemover(data=emg.copy(), data_rate=2000, center=True,
                          signal_filter=True, cutoff=[10, 500])
```

```{warning}
When `center=True`, the array you pass is centered **in place**, and it must
have a floating-point type. Pass a copy (`emg.copy()`) and convert integer
data with `astype(float)` if you need to keep the original untouched.
```

## Pre-processing options

Before the artifact removal, the data can be centered and filtered. These
options are given as keyword arguments to `ArtifactRemover` (they are passed
on to `DataLoader`), or entered in the **Filter** dialog of the GUI.

| Argument        | Default | Description |
|-----------------|---------|-------------|
| `center`        | `True`  | Subtract the mean of each channel. |
| `signal_filter` | `True`  | Apply a Butterworth filter. |
| `cutoff`        | `450.0` | A number gives a low-pass filter; a list `[low, high]` gives a band-pass filter. Must be below half the sampling rate. |
| `order`         | `2`     | Butterworth filter order. |
| `data_rate`     | `None`  | Sampling rate (Hz), when not stored in the file. |
| `delimiter`     | `"\t"`  | Column delimiter for `.txt` and `.csv` files. |
| `channel_names` | `None`  | Override the channel names (for `.bio` files). |

In offline processing the filter is applied forward and backward (zero phase
lag). In real-time processing a causal filter is used.

```{tip}
The Filter dialog of the GUI offers a *Filter order* field (default 4). The GUI
divides this value by two before using it, because the zero-lag filter runs
forward and backward.
```

## Saving results

| What                                  | How |
|---------------------------------------|-----|
| Everything (raw, processed, singular values, filter coefficients) from Python | `sol.save("result.pkl")` writes a Python pickle (a dictionary with `init_data`, `output`, `s`, `s_reduced`, ...). |
| Raw and processed signals in a text file | `write_txt_file(sol.output, "clean.txt", headers=...)`. |
| From the GUI                          | **File > Save** / **Save As**; see {doc}`remover_app`. |

To reload a pickle:

```python
import pickle

with open("result.pkl", "rb") as f:
    result = pickle.load(f)
cleaned = result["output"]
```

```{warning}
Only load pickle files that you created yourself or that come from a source
you trust.
```

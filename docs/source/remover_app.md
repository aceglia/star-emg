# Graphical user interface

`StAR-EMG` includes a graphical application to load, filter, process,
inspect and save EMG data, offline or in real time, without writing any code.

There are two ways to start it:

* **Windows standalone application:** double-click `StAR-EMG.exe` (see
  {doc}`install`). No Python installation is needed.
* **Python package:** run `python examples/run_gui.py` from the repository
  root, or, in your own script:

  ```python
  import sys
  from PyQt5.QtWidgets import QApplication
  from star_emg.app.gui import GUI

  if __name__ == "__main__":
      app = QApplication(sys.argv)
      gui = GUI()
      app.exec()
  ```

Both give the same interface.

```{note}
The application writes a small file named `_pychache.json` in its working
folder to remember the last folder you used in the file dialogs. It can be
deleted safely.
```

## The main window

When the application starts, most controls are greyed out until a file is
loaded.

```{figure} images/gui_file_menu.png
:alt: StAR-EMG main window at start-up with the File menu open.
:width: 95%

The main window at start-up with the **File** menu open.
```

The window is organized in four areas:

| Area | Content |
|------|---------|
| **Menu bar** (top) | **File** (*Load file*, *Load stream*, *Save*, *Save As*, *Quit*), **Filter** (pre-filtering of the data) and **Stream** (real-time mode). |
| **Plot area** (left) | One plot per displayed channel, sharing the time axis. The raw signal is drawn as a thin grey line and the processed signal in red. |
| **Control panel** (right) | **SVD Remover Options** (top), channel information, and **Display options** (bottom). |
| **Log panel** (bottom) | Time-stamped messages about what the application is doing (loading, processing, errors). **Clear Log** empties it. |

## Offline processing

### Step 1: load a file

Choose **File > Load file** and select a recording. Supported formats are
`.txt`, `.csv`, `.bio`, `.mat` and `.npz` (see {doc}`data_formats`). The log
confirms the loading and the signals appear in the plot area.

If the file does not contain the sampling rate, enter it in the **Filter**
dialog (next step).

### Step 2: set the pre-filtering (optional)

Open the **Filter** menu to display the *Data pre-filtering* dialog.

```{figure} images/gui_filter_dialog.png
:alt: Data pre-filtering dialog.
:width: 50%

The *Data pre-filtering* dialog.
```

| Field | Description |
|-------|-------------|
| **Sample rate (Hz)** | Sampling rate of the data. Pre-filled when it is read from the file. |
| **Center signal** | Subtract the mean of each channel (on by default). |
| **Zero-lag band pass filter** | Apply a forward-backward Butterworth band-pass filter (on by default). |
| **Cut-off frequencies (Low - High) (Hz)** | Band-pass limits, 10 and 450 Hz by default. The high cut-off must be below half the sampling rate. |
| **Filter order** | Butterworth filter order (4 by default). |

Click **OK** to apply the settings.

### Step 3: choose the channels to process

Click **Select channels to process** in the control panel. A list of channels
opens, with a check box for each one and shortcuts to select or clear them
all. Only checked channels are processed. Processing fewer channels is faster.

```{figure} images/gui_channel_selector.png
:alt: Channel selection dialog.
:width: 40%

Selecting the channels to process.
```

### Step 4: set the processing parameters

The **SVD Remover Options** panel holds the parameters of the algorithm. Their
meaning is explained in {doc}`concepts`, and guidance on choosing them is given
in {doc}`parameters`.

| Field | Description |
|-------|-------------|
| **Window length** | Number of samples processed at a time (default 5000, maximum 10 000). |
| **Hankel size** and **Automatic size** | Number of rows of the Hankel matrix. When *Automatic size* is checked, the value is derived from the window length and the field cannot be edited. Uncheck it to type your own value. |
| **Hankel delay** | Delay (in samples) between consecutive rows of the matrix (default 1). |
| **Threshold** | Rejection threshold factor. Lower values remove more components (default 0.35). |
| **Frequency bounds** | Lower and upper frequency (Hz) for the accepted components (default 10 and 300). |

### Step 5: process

Click **Process**. Processing runs in the background so that the window stays
responsive. The log shows *Processing data...* and then *Data processing
done!*. Raw and processed signals are then displayed together.

```{figure} images/gui_main_offline.jpg
:alt: StAR-EMG main window after processing.
:width: 95%

After processing: the raw signal (grey) and the processed signal (red). The
channel information and the quality metrics are listed in the right panel.
```

Below the **Process** button, the information area summarizes, for the
selected channel, the parameters used and the quality metrics of the raw and
processed signals (kurtosis, line length, median frequency and FFT amplitude;
see {doc}`quality_metrics`). Use the small **i** button at the top right of a
channel plot to show the information of that channel.

### Step 6: inspect the results

The **Display options** panel controls what is shown.

| Control | Description |
|---------|-------------|
| **Frame** (*Previous*, *Next*, number box) | Move between the epochs (frames) of the file. You can also type the frame number. |
| **Select channels to show** | Choose which channels are drawn. |
| **Show all** | Display all the channels. |
| **Show processed** | Display only the channels that have been processed (available once processing is done). |
| **Raw** / **Processed** | Show or hide the raw (grey) and processed (red) curves. |
| **Show FFT** | Switch the plots to the frequency domain, to check that the peaks at the stimulation frequency and its harmonics have disappeared. |
| **Cursor position** | Time and amplitude under the mouse pointer. |

```{figure} images/gui_fft_view.png
:alt: Plot area in FFT mode.
:width: 90%

The same channel in the frequency domain (**Show FFT**).
```

The plots can be zoomed and panned with the mouse: scroll to zoom, drag to
pan, and right-click for the plot menu (including the option to reset the
view).

```{figure} images/results_graph_time.png
:alt: Zoom on a raw and a processed EMG signal.
:width: 90%

Close-up of a channel before (grey) and after (red) artifact removal.
```

### Step 7: save

Use **File > Save** or **File > Save As** once the processing is complete. The
original signals, the processed signals and all the processing parameters are
saved so that the analysis can be reproduced. Data can be saved in the same
format as the input file, by default it is saved as a numpy archive file (`.npz`). If saving in text or csv file format the filter parameters are ignored. You may save them using the **save filter config** button in the **Filter** dialog.


```{note}
The application may ask you to confirm before discarding results that have
not been saved: **Save**, **Ignore** (discard) or **Cancel**.
```

## Real-time processing

The **Stream** menu switches the application to real-time mode: data are
received continuously through a TCP/IP connection, processed on the fly in
parallel processes, and displayed as they arrive. The main differences with
the offline mode are that the data stream runs continuously (the display can
be paused) and that the amount of data shown is controlled by a display
window.

The set-up of the connection, the format of the data sent by your acquisition
system, and the recording of streamed data are described in {doc}`streaming`.

```{figure} images/gui_stream_running.png
:alt: StAR-EMG in real-time mode, displaying a streamed signal.
:width: 95%

The application in real-time mode.
```

## Tips

* Try your parameters on a short excerpt first, then apply them to the whole
  recording.
* Keep an eye on the log panel: loading, filtering and processing errors are
  reported there, because the standalone application has no console window.
* The graphical interface and the Python API give the same results for the
  same parameters. Copy the values shown in the GUI into your scripts to
  automate the processing of many files ({doc}`examples`).

<!-- TODO(verify): Load config file content/format for offline mode; exact Save formats offered by the Save dialog; what the "split" warning (Yes/No/Cancel) asks when loading multi-frame files. -->

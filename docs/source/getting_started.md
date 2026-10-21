# Getting started

This page takes you from a raw recording to a cleaned signal in a few minutes.
Choose the route that matches how you installed `StAR-EMG` (see {doc}`install`).

## Route 1: Windows application

1. Start `StAR-EMG.exe`.
2. Choose **File > Load file** and select your recording
   (`.txt`, `.csv`, `.bio`, `.mat` or `.npz`; see {doc}`data_formats`).
3. If asked, set the sampling rate and the pre-filtering options.
4. Click **Process**. The default parameters work for many recordings; see
   {doc}`parameters` to tune them.
5. Compare the raw (grey) and processed (red) signals, then save the result
   with **File > Save**.

```{figure} images/gui_main_offline.jpg
:alt: StAR-EMG main window after processing an EMG recording.
:width: 90%

The main window after processing. The raw signal is shown in grey and the
processed signal in red.
```

The complete walk-through, including real-time mode, is in {doc}`remover_app`.

## Route 2: Python

Create a script (or a notebook cell) and run:

```python
from star_emg.automatic_remover import ArtifactRemover

if __name__ == "__main__":
    # 1. Load the recording and apply the optional pre-processing
    remover = ArtifactRemover(
        data="my_recording.txt",   # path to a supported file
        center=True,               # remove the mean of each channel
        signal_filter=True,        # band-pass filter ...
        cutoff=[10, 500],          # ... between 10 and 500 Hz
    )

    # 2. Remove the artifacts
    sol = remover.process(hankel_size=450, process_window=5000, freq_bounds=[10, 300], factor=0.35)

    # 3. Quantify and visualize the result
    sol.analyse()
    sol.plot(signals=True, fft=True, show_analysis=True)

    # 4. Access the arrays directly
    cleaned = sol.output        # shape (n_epochs, n_channels, n_samples)
    raw = sol.init_data         # same shape, after the pre-processing
```

```{important}
Always keep the `if __name__ == "__main__":` guard. When `threads > 1`
`StAR-EMG` starts worker processes with the `spawn` method, which re-imports
your script. On Windows the guard is mandatory.
```

The result window opens with the raw and processed signals and their spectra:

```{figure} images/results_window.jpg
:alt: Result window showing raw and processed EMG and their FFT.
:width: 80%

Result window produced by `Solution.plot`.
```

## Route 3: real-time

Real-time processing is available from the GUI (Stream menu) and from the
`RtArtifactRemover` class. Start with {doc}`streaming` to understand how data
reach the application, then see {doc}`rt_remover`.

## Where to go next

| You want to...                                  | Read |
|-------------------------------------------------|------|
| Understand what the algorithm does              | {doc}`concepts` |
| Choose good parameter values                    | {doc}`parameters` |
| Know how to format your data                    | {doc}`data_formats` |
| Judge whether the cleaning worked               | {doc}`quality_metrics` |
| Use the GUI                                     | {doc}`remover_app` |
| See complete scripts                            | {doc}`examples` |
| Test the algorithm on synthetic artifacts       | {doc}`generator_app` |

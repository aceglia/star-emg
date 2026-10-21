# Offline artifact removal

The `ArtifactRemover` class processes a complete recording. It loads the data,
optionally centers and filters them, removes the artifacts window by window,
and returns a `Solution` object that holds the results and offers plotting,
analysis and saving.

## Basic example

```python
from star_emg.automatic_remover import ArtifactRemover

if __name__ == "__main__":
    # Path to a file (see "Data formats") or a numpy array of shape
    # (n_epochs, n_channels, n_samples). With an array, also give data_rate=...
    path_file = r"data\test001.txt"

    # 1. Load the data and set the pre-processing:
    #    centering and 10-500 Hz zero-phase band-pass filter.
    #    data_rate must be provided if it is not stored in the file.
    artifact_remover = ArtifactRemover(
        data=path_file, signal_filter=True, center=True, cutoff=[10, 500]
    )

    # 2. Remove the artifacts. The arguments are described in
    #    "Parameters and tuning" and in the API reference.
    sol = artifact_remover.process(
        hankel_size=450,        # rows of the Hankel matrix
        process_window=5000,    # samples decomposed at once
        hankel_delay=1,         # delay between rows of the Hankel matrix
        freq_bounds=[10, 300],  # accepted dominant frequencies (Hz)
        factor=0.35,            # rejection threshold factor
        threads=4,              # worker processes (1 = no multiprocessing)
    )

    # 3. Compute the quality metrics of the raw and processed signals.
    results = sol.analyse()

    # 4. Display the result (Tk window), with the analysis.
    sol.plot(signals=True, fft=True, singular_values=False,
             stack_epochs=False, show_analysis=True)

    # 5. Save everything (raw, processed, singular values) to a pickle file.
    sol.save("test001_processed.pkl")
```

```{important}
Keep the code under `if __name__ == "__main__":`. With `threads > 1` the worker
processes re-import your script, which is mandatory on Windows.
```

The window shows the raw (light blue) and processed (orange) signals, and
their spectra. **Previous** and **Next** move between epochs, and the drop-down
menu at the bottom selects the channel.

```{figure} images/results_window.jpg
:alt: Result window with raw and processed EMG and their FFT.
:width: 80%

Output of `sol.plot(...)`: raw and processed signal (top) and their FFT
(bottom), with the analysis results.
```

Set `stack_epochs=True` to concatenate the epochs into one continuous trace
per channel.

## The `Solution` object

`process` returns a `Solution`. The most useful attributes are:

| Attribute | Content |
|-----------|---------|
| `sol.init_data` | The signals that were processed (after centering/filtering), shape `(n_epochs, n_channels, n_samples)`. |
| `sol.output` | The processed signals, same shape. |
| `sol.data_rate` | Sampling rate (Hz). |

```python
import numpy as np

cleaned = sol.output[0, 0]          # first epoch, first channel
time = np.arange(cleaned.size) / sol.data_rate
```

## Processing selected channels or samples

```python
sol = artifact_remover.process(
    hankel_size=450,
    channel_idxs=[0],          # only the first channel (as a list)
    data_window=[0, 20000],    # only the first 20 000 samples
    process_window=5000,
)
```

To process only some epochs, select them in the array before creating the
`ArtifactRemover` (for example `emg[[0, 1]]`), see below.

The names of the channels and the sampling rate are available through
`artifact_remover.get_channel_names()` and `artifact_remover.get_data_rate()`.

## Working with a NumPy array

```python
import numpy as np
from star_emg.automatic_remover import ArtifactRemover

emg = np.asarray(my_emg, dtype=float)      # shape (n_epochs, n_channels, n_samples)
remover = ArtifactRemover(data=emg.copy(), data_rate=2000,
                          center=True, signal_filter=True, cutoff=[10, 500])
sol = remover.process(hankel_size=450, process_window=5000)
```

## Comparing with a notch filter

`StAR-EMG` includes a cascade of notch filters at the stimulation frequency
and its harmonics. It needs the stimulation frequency in advance, which makes
it a useful baseline against which to compare the SVD method.

```python
sol_notch = artifact_remover.process(
    notch_filter=True,
    frequency_peaks=50,     # stimulation frequency (Hz)
    quality_factor=30,      # higher = narrower notches
    process_window=5000,
)
sol_notch.analyse()
```

## Batch processing of a folder

```python
from pathlib import Path
from star_emg.automatic_remover import ArtifactRemover
from star_emg.io_utils import write_txt_file

if __name__ == "__main__":
    out_dir = Path("processed")
    out_dir.mkdir(exist_ok=True)

    for file in sorted(Path("data").glob("*.txt")):
        remover = ArtifactRemover(data=str(file), center=True,
                                  signal_filter=True, cutoff=[10, 500])
        sol = remover.process(hankel_size=450, process_window=5000,
                              freq_bounds=[10, 300], factor=0.35, threads=4)
        sol.analyse()
        write_txt_file(sol.output, str(out_dir / f"{file.stem}_clean.txt"),
                       headers=remover.get_channel_names())
        sol.save(str(out_dir / f"{file.stem}.pkl"))
        print("Done:", file.name)
```

## Arguments of `process`

The arguments of `ArtifactRemover.process` are listed and explained in
{doc}`parameters`, and in the API reference ({doc}`modules`).

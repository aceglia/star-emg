# Parameters and tuning

This page lists every processing parameter, shows how the names used in the
GUI map to those of the Python API, and gives a practical procedure to choose
values. The concepts behind each parameter are explained in {doc}`concepts`.

## Main parameters

| GUI label         | Python argument        | GUI default | API default | Description |
|-------------------|------------------------|-------------|-------------|-------------|
| Window length     | `process_window`       | 5000        | all data (max 10 000) | Number of samples decomposed at once. |
| Hankel size       | `hankel_size`          | 625 (automatic) | 300 | Number of rows $L$ of the Hankel matrix, i.e. the maximum number of components. |
| Automatic size    | -                      | on          | -           | The GUI sets the Hankel size from the window length (one eighth of it: 625 for 5000 samples). |
| Hankel delay      | `hankel_delay`         | 1           | 1           | Delay $\tau$, in samples, between consecutive rows of the matrix. |
| Threshold         | `factor`               | 0.35        | 0.5         | Factor $\lambda$ in the rejection rule. Lower value: more components removed. |
| Frequency bounds  | `freq_bounds`          | 10 - 300    | `[10, 450]` | Components whose dominant frequency is at or below the first value, or at or above the second one, are rejected. |

```{note}
The values shown in the GUI are starting points. Python defaults are different
from the GUI defaults, so the same recording can give a different result if
you do not set the parameters explicitly in both.
```

## Additional Python parameters

These arguments are available in `ArtifactRemover.process` (and, when
relevant, in the real-time classes).

| Argument | Default | Description |
|----------|---------|-------------|
| `threads` | `1` | Number of worker processes. With `1` everything runs in the main process. With more, each channel of each epoch is a task distributed to a pool of processes started with the `spawn` method (use the `if __name__ == "__main__":` guard). |
| `channel_idxs` | `None` | Channel(s) to process, as a **list** (for example `[0]` or `[0, 2]`). All channels if `None`. |
| `data_window` | `None` | `[start, stop]` in samples. Only this part of each signal is processed. |
| `randomized` | `False` | Use a randomized SVD (requires the optional `fbpca` package; the standard SVD is used with a message if it is missing). Faster on large matrices, approximate. |
| `nb_principal_components` | `None` | Keep only the first *k* components of the SVD before the rejection step. |
| `epsilon` | `None` | Discard components whose singular value is below this absolute value. |
| `notch_filter` | `False` | Use the notch-filter cascade instead of the SVD method. |
| `quality_factor` | `150` | Quality factor of each notch (higher means narrower notches). |
| `frequency_peaks` | `30` | Stimulation frequency (Hz) for the notch filters. |
| `first_peak` | `None` | Frequency (Hz) of the first notch if different from `frequency_peaks`. |
| `post_filter` | `False` | Reserved option, currently not functional. Leave it to `False` and use the pre-filter options instead (see {doc}`data_formats`). |

Additional options of the real-time classes are described in {doc}`rt_remover`.

```{warning}
Pass `channel_idxs` as a list. A bare `0` is interpreted as "not set" and
all channels are processed. To process only some epochs, select them in your
array before creating the `ArtifactRemover`.
```

## Choosing values: a practical procedure

1. **Pre-process correctly.** Center the signal and use a band-pass filter
   (for example 10 to 500 Hz) that is compatible with your sampling rate. The
   upper cutoff must stay below half the sampling rate.
2. **Pick a window length.** 5000 samples (2.5 s at 2 kHz) is a good first
   choice. Shorter windows track fast changes in stimulation better and are
   quicker to compute; longer windows give the decomposition more data.
   Remember that the window is capped at 10 000 samples.
3. **Keep the automatic Hankel size at first.** The Hankel size controls how
   many components are available to separate artifact from EMG. Increase it
   if artifact residues remain, decrease it if processing is too slow. The
   cost of the SVD grows quickly with this value.
4. **Set the frequency bounds around your EMG band of interest.** For surface
   EMG, `[10, 300]` to `[10, 450]` is typical. Raise the lower bound if slow
   drifts remain; remember the upper bound limits the bandwidth of the output.
5. **Adjust the threshold on a short, representative excerpt.**
   * Artifact residue still visible (sharp spikes in the signal, peaks at the
     stimulation harmonics in the FFT): **decrease** the threshold (for
     example from 0.35 to 0.25).
   * The processed signal looks too flat or has lost EMG bursts: **increase**
     the threshold (for example to 0.5).
6. **Check with the metrics.** Use the quality metrics ({doc}`quality_metrics`)
   and the FFT view to compare before and after. Apply the settings to the
   whole recording once you are satisfied.
7. **Save the parameters.** In the GUI, save the configuration (see
   {doc}`remover_app`); in Python keep the arguments in your script. This
   ensures reproducibility.

## Real-time parameters

In real-time operation the same parameters apply, plus a few that control the
trade-off between quality and speed.

| Parameter | Role |
|-----------|------|
| `window_size` (buffer length) | Number of recent samples decomposed every time a chunk arrives. It plays the role of `process_window`. |
| `chunk_size` | Number of samples received at each step. Smaller chunks give lower latency but need more frequent processing. |
| `hankel_size` | As above. In real-time keep it small enough that one step is processed faster than a chunk is acquired. |
| `update_svd_every` | Recompute which components are rejected only every *n* chunks and reuse the previous selection in between. Raises speed at the cost of slower adaptation. |

**Rule of thumb.** At a sampling rate $f_s$ and a chunk of $n$ samples, a new
chunk arrives every $n / f_s$ seconds. The processing of one step (printed at
the end of `process_all_data`, in ms and "FPS") must be shorter than that
delay, or data will accumulate. Test on a prerecorded file first, see
{doc}`rt_remover`.

## Tips for speed

* Use a NumPy/SciPy build linked with MKL ({ref}`optimized-linear-algebra-backend-mkl`).
* Reduce the window length or the Hankel size.
* Process only the channels you need (`channel_idxs`, or *Select channels to
  process* in the GUI).
* Use `threads` to distribute channels over several CPU cores (offline).
* Limit the threads of the linear-algebra library inside each process:
  `os.environ["MKL_NUM_THREADS"] = "1"` before importing NumPy.

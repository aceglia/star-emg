# Real-time artifact removal

The `RtArtifactRemover` class applies the same algorithm to data that arrive
**chunk by chunk**, as they do during an acquisition. It keeps the most recent
`window_size` samples in an internal circular buffer, runs the decomposition
on that window each time a chunk is added, and returns the cleaned samples that
correspond to the newest chunk (see {doc}`concepts`).

For convenience, a streamer class (`DataStreamer`) can feed the object from a
prerecorded file, so that you can tune the parameters and measure the speed
before connecting a real device.

```{note}
The real-time classes use the circular buffer and the TCP client of
[`biosiglive`](https://github.com/aceglia/biosiglive). See the note on the
`biosiglive` version in {doc}`install`.
```

## Main functions

| Function | Purpose |
|----------|---------|
| `RtArtifactRemover(window_size, data=None, update_svd_every=1, **loader_kwargs)` | Create the object. With `data` (a file or an array) it is set up to replay a recording; without `data` it is set up for a live stream. `loader_kwargs` are the pre-processing options (`center`, `signal_filter`, `cutoff`, `data_rate`, `chunk_size`, ...). |
| `process_chunk(chunk, **kwargs)` | Process one chunk of **one channel**, of shape `(1, n_samples)`. Returns `None` while the buffer is not yet full, and then an array of shape `(1, n_samples)` with the processed samples of the chunk. |
| `process_all_data(...)` | Replay the whole file (or part of it) chunk by chunk and return a `Solution`. Prints the mean processing time per chunk and the equivalent frame rate. |
| `streamer.get_next_chunk(n)` | Get the next `n` samples from the loaded file. Returns `(True, chunk)`, then `(False, None)` when no complete chunk remains. |

Only one channel can be processed at a time by `process_chunk`. To process
several channels, use one `RtArtifactRemover` per channel, in separate
processes (this is what the GUI does).

## Replaying a file in one call

`process_all_data` is the quickest way to evaluate the real-time behavior on a
recording. The arguments `hankel_size` and `notch_filter` must always be given.

```python
import os
os.environ["MKL_NUM_THREADS"] = "1"          # before importing numpy

from star_emg.rt_automatic_remover import RtArtifactRemover

if __name__ == "__main__":
    path_file = r"data\test001.txt"

    process_window = 600                     # samples in the sliding window
    artifact_remover = RtArtifactRemover(
        data=path_file,
        window_size=process_window,
        chunk_size=20,                       # samples received per step
        signal_filter=False,
        center=True,
    )

    sol = artifact_remover.process_all_data(
        hankel_size=100,
        channel_idxs=[0],                    # process the first channel
        data_window=[0, 2000],               # only the first 2000 samples
        notch_filter=False,                  # SVD method
        freq_bounds=[0, 200],
        factor=0.3,
        hankel_delay=1,
        update_svd_every=1,                  # recompute the rejection at every chunk
    )

    sol.analyse()
    sol.plot(signals=True, fft=True, singular_values=False,
             stack_epochs=False, show_analysis=True)
```

The messages printed at the end give the total time and the mean time per
chunk. **The time per chunk must be shorter than the duration of a chunk**
(`chunk_size / data_rate`) for the processing to keep up with a live
acquisition.

## Processing chunk by chunk

This example shows the loop you would run inside an acquisition program. Here
the chunks come from the streamer, but they could come from any source.

```python
import numpy as np

from star_emg.rt_automatic_remover import RtArtifactRemover
from star_emg.solution import Solution

if __name__ == "__main__":
    window_size = 500
    artifact_remover = RtArtifactRemover(
        window_size=window_size,
        data=r"data\test001.txt",
        signal_filter=False,
        center=True,
        chunk_size=20,
        data_rate=2000,
    )

    is_data = True
    global_output = None
    global_input = None
    while is_data:
        # Get the next chunk of data: shape (n_channels, chunk_size)
        is_data, chunk = artifact_remover.streamer.get_next_chunk(
            artifact_remover.streamer.chunk_size
        )
        if not is_data:
            break

        # Process one channel. The output has shape (1, chunk_size)
        output = artifact_remover.process_chunk(
            chunk[0:1],
            window_size=window_size,     # size of the sliding window
            hankel_size=150,
            freq_bounds=[10, 200],
            factor=0.2,
        )
        if output is None:
            # The buffer is not full yet: nothing to output
            continue

        # Store the output and the corresponding input
        global_output = output if global_output is None else np.concatenate((global_output, output), axis=-1)
        global_input = chunk[0:1] if global_input is None else np.concatenate((global_input, chunk[0:1]), axis=-1)

    # Gather the results in a Solution to analyze and plot them
    sol = Solution(data_rate=artifact_remover.streamer.data_rate)
    sol.from_dict({"init_data": global_input, "output": global_output})
    sol.analyse()
    sol.plot(signals=True, fft=True, singular_values=False,
             stack_epochs=False, show_analysis=True)
```

The result window is the same as in the offline processing
({doc}`offline_remover`).

```{note}
Because the buffer must be filled before any output is produced, the first
`window_size` samples have no processed counterpart. In the loop above, a chunk
is stored only when an output exists, so `global_input` and `global_output` have
the same length and can be compared directly.
```

## Using it with a live stream

For a live source, create the object without `data` and pass the sampling
rate:

```python
artifact_remover = RtArtifactRemover(window_size=600, center=True,
                                     signal_filter=False, data_rate=2000)
```

then call `process_chunk` with each new chunk read from your device. To get
the data from a TCP connection and to use the graphical interface instead of
writing your own loop, see {doc}`streaming`.

## Tuning for speed

* `window_size` and `hankel_size` have the largest effect on the computing
  time.
* `update_svd_every=n` computes the list of rejected components only every
  `n` chunks and reuses it in between.
* Use an MKL-based NumPy/SciPy ({ref}`optimized-linear-algebra-backend-mkl`)
  and set `MKL_NUM_THREADS=1` when several processes run in parallel.
* Real-time processing uses a causal filter for the optional pre-filtering,
  unlike the zero-phase filter used offline, so a small difference between
  offline and real-time results is expected.

# Real-time streaming

`StAR-EMG` can clean EMG while it is being acquired. This page explains how
data reach the application, how to configure the connection, how to test the
set-up with a prerecorded file, and how to read back what was recorded.

## How it works

```text
  acquisition system / script                        StAR-EMG (GUI)
 ┌───────────────────────────┐   TCP/IP    ┌─────────────────────────────────┐
 │ sends chunks of samples   │ ──────────► │ TCP server  ─►  processing      │
 │ (channels x samples)      │             │ (one process per channel)       │
 │ + time stamps             │             │            ─►  display + saving │
 └───────────────────────────┘             └─────────────────────────────────┘
```

* The GUI runs a **TCP/IP server**. Your acquisition software (the *client*)
  connects to it and sends the signal in small chunks (for instance 20
  samples at a time) together with their time stamps.
* Each channel is processed in its own process, so that several channels can
  be handled in parallel. Multiprocessing is enabled by default in the
  live-streaming GUI.
* Raw and processed data are displayed in real time. The display can be
  paused, while the data stream keeps running.
* Raw data, processed data, time stamps and the processing parameters can be
  recorded during the session.

The processing itself is the one described in {doc}`concepts`, applied to a
sliding window of the most recent samples.

```{figure} images/gui_stream_menu.png
:alt: Stream menu of the StAR-EMG application.
:width: 60%

The **Stream** menu.
```

```{figure} images/gui_stream_settings.png
:alt: Stream settings window with address, port, acquisition rate and channel names.
:width: 60%

Stream settings: address, port, acquisition rate, display window, channel
names and saving options.
```

## Starting a session

1. Start the application and open the **Stream** menu.
2. Load or enter the stream configuration (address, port, acquisition rate,
   channels) and start the server.
3. Start your acquisition software (the client) so that it connects to the
   address and port of the server and begins to send data.
4. Choose the channels to display and to process, and set the processing
   parameters ({doc}`parameters`). The parameters can be changed while the
   stream is running.
5. Stop the stream when the session is over. The recording is closed and the
   files are written at the location given by `save_path`.

```{important}
Start the server in `StAR-EMG` **before** launching the client: the client
connects to a server that must already be listening.
```

## Testing with a prerecorded file

You do not need an acquisition system to try the real-time mode. The script
`examples/dummy_file_streamer.py` plays a recorded file back to the server, as
if it were a live acquisition. It uses the TCP client of `biosiglive`.

```python
import asyncio
import time

import numpy as np
from biosiglive.streaming.async_client import AsyncTCPClient
from star_emg.io_utils import DataLoader


async def main(data, chunk_size=20, data_rate=2000):
    client = AsyncTCPClient("127.0.0.1", 12345)   # address and port of the GUI server
    await client.connect()

    # Cut the (n_channels, n_samples) signal in chunks of `chunk_size` samples
    chunks = [data[:, i : i + chunk_size] for i in range(0, data.shape[-1], chunk_size)]

    dt_sample = 1 / data_rate
    dt = chunk_size / data_rate           # one chunk every `dt` seconds
    t0 = 0.0
    count = 0
    t_next = time.perf_counter()

    while True:
        t_next += dt
        data_tmp = chunks[count % len(chunks)]            # loop over the file
        t = np.round(t0 + np.arange(chunk_size) * dt_sample, 4)   # time stamps (s)
        t0 += np.round(chunk_size * dt_sample, 4)
        try:
            await client.send_array(data_tmp, sample_time=t)
        except Exception:
            break                                          # the server was closed
        sleep_time = t_next - time.perf_counter()
        if sleep_time > 0:
            await asyncio.sleep(sleep_time)                # keep the real-time pace
        else:
            t_next = time.perf_counter()
        count += 1


if __name__ == "__main__":
    loader = DataLoader(r"data\test001.txt", center=True)
    loader._apply_stack_epochs()          # concatenate epochs: (n_channels, n_samples)
    asyncio.run(main(loader.init_data, chunk_size=20, data_rate=loader.data_rate))
```

Things to note in this example:

* each message contains an array of shape `(n_channels, chunk_size)` and a
  vector of `chunk_size` time stamps in seconds (`sample_time`);
* the pace of the loop reproduces the acquisition rate: a chunk of
  `chunk_size` samples is sent every `chunk_size / data_rate` seconds;
* the file is replayed in a loop, so the stream never ends until you stop the
  server;
* set the `acquisition_rate` of the server to the sampling rate of the file
  (`loader.data_rate`).

## Connecting your own acquisition system

To feed `StAR-EMG` from your own software, send chunks of data to the server
the same way the example does, using the `AsyncTCPClient` of
[`biosiglive`](https://github.com/aceglia/biosiglive). In your acquisition
loop, replace the file chunks by the newest samples read from the device:

```python
chunk = read_new_samples_from_device()        # shape (n_channels, n_new_samples)
timestamps = timestamps_of(chunk)             # shape (n_new_samples,), in seconds
await client.send_array(chunk, sample_time=timestamps)
```

Check that:

* the channel order matches `channel_names`;
* the sampling rate matches `acquisition_rate`;
* the chunks have a regular size and arrive at a regular pace.

```{note}
It is possible to use another client to send data to the server. To do so, please check the `biosiglive` documentation for more information about the protocol. 
```

## Reading back a recording

Streamed sessions are written progressively on disk. The recording contains
the raw signals, the processed signals, the time stamps and the processing
parameters that were active during the session. `examples/save_zarr_dataset.py`
shows how to open a recording from Python and plot it. It requires the `zarr`
package.

```python
from pathlib import Path
from star_emg.app.save_utils import ZarrRecording
import matplotlib.pyplot as plt

STEAM_PATH = Path("data") / "test.stream"

from numcodecs import blosc

blosc.use_threads = False
blosc.set_nthreads(1)

if __name__ == "__main__":
    zarr_ds = ZarrRecording.load_dataset(STEAM_PATH)
    meta = dict(zarr_ds.root.attrs)
    print(meta)
    data_dict, configs = zarr_ds.to_dict()
    zarr_ds.close()
    plt.plot(data_dict["time"][10000:20000], data_dict["values"][0, 0, 10000:20000], label="Raw Signal")
    plt.plot(
        data_dict["time"][10000:20000], data_dict["processed_data_svd"][0, 0, 10000:20000], label="Processed Signal"
    )
    plt.legend()
    plt.show()
```

## Using the real-time classes without the GUI

The `RtArtifactRemover` class gives access to the same processing in Python,
for instance to integrate it into your own acquisition software. See
{doc}`rt_remover`.

## Performance and troubleshooting

* **Processing slower than acquisition.** If one step takes longer than the
  duration of a chunk, the display lags behind. Reduce the window length or
  the Hankel size, process fewer channels, increase the value of
  `update_svd_every`, and make sure that NumPy/SciPy use MKL
  ({ref}`optimized-linear-algebra-backend-mkl`).
* **CPU oversubscription.** Because each channel runs in its own process, set
  `MKL_NUM_THREADS=1` so that the processes do not compete for the same cores.
* **The client cannot connect.** Check that the server is running, that the
  address and port are the same on both sides, and that a firewall does not
  block the port.
* **Distorted time axis or shifted frequencies.** The `acquisition_rate` does
  not match the real sampling rate of the data.

"""
This script aims to stream data from a file to a server using asyncio and TCP.
It meant to be used for testing TCP/IP server like in the application.
"""

import numpy as np
from biosiglive.streaming.async_client import AsyncTCPClient
from star_emg.io_utils import DataLoader
import asyncio


async def main(data, chunk_size=20, data_rate=2000):
    client = AsyncTCPClient("127.0.0.1", 12345)
    await client.connect()
    chunks = [data[:, i : i + chunk_size] for i in range(0, data.shape[-1], chunk_size)]

    dt_sample = 1 / data_rate
    t0 = 0.0
    count = 0
    import time

    t_next = time.perf_counter()
    dt = 0.01
    while True:
        t_next += dt
        if count >= data.shape[-1]:
            count = 0
        data_tmp = chunks[count % len(chunks)]
        t = np.round(t0 + np.arange(chunk_size) * dt_sample, 4)
        t0 += np.round(chunk_size * dt_sample, 4)
        try:
            await client.send_array(data_tmp, sample_time=t)
        except Exception as e:
            break
        now = time.perf_counter()
        sleep_time = t_next - now

        if sleep_time > 0:
            await asyncio.sleep(sleep_time)
        else:
            t_next = now
        count += 1


if __name__ == "__main__":
    import numpy as np

    path_file = r"data\example.txt"
    loader = DataLoader(path_file, center=True)
    loader._apply_stack_epochs()

    asyncio.run(main(loader.init_data, chunk_size=20, data_rate=loader.data_rate))

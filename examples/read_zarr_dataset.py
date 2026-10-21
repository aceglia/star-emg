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

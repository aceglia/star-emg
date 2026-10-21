import numpy as np
from star_emg.io_utils import write_txt_file, load_txt_file, load_npz_file, load_bio_file
from biosiglive import save

if __name__ == "__main__":
    data, chan_names, epochs, fs, time, loaded_raw = load_npz_file("data/example.npz")
    print("Loaded data shape:", data.shape)
    print("Channel names:", chan_names)
    print("Epochs:", epochs)
    print("Sampling frequency:", fs)
    print("Time shape:", time.shape[1])

    # Write a txt file from raw data
    array_to_write = np.concatenate((time[:, None, :], data), axis=1)
    headers = ["Time"] + list(chan_names)
    delimiter = "\t"
    write_txt_file(array_to_write, "data/example.txt", headers=headers, delimiter=delimiter)
    data, chan_names, epochs, fs, time = load_txt_file("data/example.txt")
    print("------ Loaded data from written txt file ------")
    print("Loaded data shape:", data.shape)
    print("Channel names:", chan_names)
    print("Epochs:", epochs)
    print("Sampling frequency:", fs)
    print("Time shape:", time.shape[1])

    # Create a dictionary to save as a Numpy archive or a Biosiglive file
    data_dict = {"values": data, "channel_names": chan_names, "data_rate": fs, "time": time}  # optional  # optional

    # Save a .npz file using numpy
    np.savez("data/example.npz", **data_dict)
    data, chan_names, epochs, fs, time, loaded_raw = load_npz_file("data/example.npz")
    print("------ Loaded data from written npz file ------")
    print("Loaded data shape:", data.shape)
    print("Channel names:", chan_names)
    print("Epochs:", epochs)
    print("Sampling frequency:", fs)
    print("Time shape:", time.shape[1])

    # Write to a .bio file using biosiglive
    save(data_dict, "data/example.bio", safe=False)
    data, chan_names, epochs, fs, time, loaded_raw = load_bio_file("data/example.bio")
    print("------ Loaded data from written bio file ------")
    print("Loaded data shape:", data.shape)
    print("Channel names:", chan_names)
    print("Epochs:", epochs)
    print("Sampling frequency:", fs)
    print("Time shape:", time.shape[1])

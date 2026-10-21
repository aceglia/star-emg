"""
This file is an example of how to use the ArtifactRemover class from the star_emg library.
It demonstrates how to process data and analyze the results. The data used in this example is a file located at 'data\example.mat'.
"""

import numpy

from star_emg.automatic_remover import ArtifactRemover

if __name__ == "__main__":
    # Data need to be either a path to a file or a numpy array
    # If data is a numpy array, it should be of shape (n_epochs, n_channels, n_samples)
    file = r"D:\Downloads\06-26_13-47-21_hifreq.npz"
    import numpy as np

    data = np.load(file)
    with np.load(file) as data:
        fs = data["fs"]
        emg = data["emg"][None]
    emg = np.swapaxes(emg, 1, 2)  # Swap axes to have shape (n_epochs, n_channels, n_samples)
    from biosiglive import save, load

    dict = {"data_rate": fs, "values": emg}
    save(dict, r"D:\Downloads\06-26_13-47-21_hifreq.bio", safe=False)
    data = load(r"D:\Downloads\06-26_13-47-21_hifreq.bio")
    path_file = r"data\test001.txt"
    artifact_remover = ArtifactRemover(data=path_file, signal_filter=True, center=True, cutoff=[10, 500])
    from star_emg.io_utils import write_txt_file

    init_data = artifact_remover.data_loader.init_data
    write_txt_file(init_data[2:], r"data\emg_with_artifact.txt", headers=["EMG1", "EMG2"])
    write_txt_file(init_data[0:1], r"data\emg_clean.txt", headers=["EMG1", "EMG2"])

    sol = artifact_remover.process(
        hankel_size=450,
        randomized=False,
        channel_idxs=None,
        first_peak=40,
        threads=4,
        nb_principal_components=None,
        post_filter=False,
        notch_filter=True,
        quality_factor=10,
        frequency_peaks=80,
        hankel_delay=1,
        process_window=5000,
        freq_bounds=[10, 300],
        factor=0.35,
    )
    results = sol.analyse()
    sol.plot(signals=True, fft=True, singular_values=False, stack_epochs=False, show_analysis=True)

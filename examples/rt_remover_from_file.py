"""
Example showing the use of the RtArtifactRemover class to remove artifacts from a prerecorded file to try the filtering.
"""

import os

os.environ["MKL_NUM_THREADS"] = "1"

from star_emg.rt_automatic_remover import RtArtifactRemover

if __name__ == "__main__":
    # Data need to be either a path to a file or a numpy array
    # If data is a numpy array, it should be of shape (n_epochs, n_channels, n_samples)
    path_file = r"data\test001.txt"

    process_window = 600
    h_delay = 1
    h_size = int((process_window / 6) / h_delay)
    h_size = 100
    print("Hankel matrix size is: ", "(", h_size, ",", process_window - (h_size - 1) * h_delay, ")")
    notch_filter = False
    artifact_remover = RtArtifactRemover(
        data=path_file, chunk_size=20, window_size=process_window, signal_filter=False, center=True
    )
    channel = 0
    sol = artifact_remover.process_all_data(
        hankel_size=h_size,
        randomized=False,
        channel_idxs=[channel],
        data_window=[0, 2000],
        threads=1,
        nb_principal_components=None,
        epsilon=None,
        notch_filter=notch_filter,
        quality_factor=30,
        frequency_peaks=50,
        first_peak=75,
        hankel_delay=h_delay,
        update_svd_every=1,
        factor=0.3,
        freq_bounds=[0, 200],
    )
    results = sol.analyse()
    sol.plot(signals=True, fft=True, singular_values=False, stack_epochs=False, show_analysis=True)

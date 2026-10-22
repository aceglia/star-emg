******************
About `StAR-EMG`
******************

`StAR-EMG` is an open-source software package for removing stimulation
artifacts from electromyographic recordings acquired during transcutaneous
spinal cord stimulation. The package implements a singular value
decomposition (SVD)-based filtering approach that can adapt to changes in
stimulation parameters without requiring prior knowledge of the stimulation
frequency or waveform. The software supports both offline processing and
real-time operation, enabling immediate visualization of artifact-reduced EMG
signals during experimental and clinical sessions.

To facilitate adoption by researchers and clinicians, `StAR-EMG` is
distributed as a Python package, a standalone Windows application with a
graphical user interface, and a C++ library for integration into external
software. By providing real-time access to artifact-reduced EMG signals,
`StAR-EMG` enables more effective monitoring of muscle activity and may
support the optimization of stimulation protocols for neurorehabilitation and
neuromodulation applications.

Why StAR-EMG?
=============

Continuous transcutaneous spinal cord stimulation (ctSCS) is a non-invasive
neuromodulation technique that can improve motor function in people with
neurological disorders such as spinal cord injury. EMG is the standard tool to
assess the neuromuscular response to stimulation, but the stimulation
artifacts it produces can be several times larger than the muscle activity
itself.

Existing approaches (hardware blanking, template subtraction, notch filtering,
empirical mode decomposition) usually require extra instrumentation, break
when the stimulation intensity, frequency or waveform changes, may remove
frequency components that matter for EMG analysis, or cannot run in real
time. `StAR-EMG` was designed to address these limitations: it adapts to
changing stimulation settings, needs no *a priori* knowledge of them, and
runs in real time, which makes it possible to watch muscle responses while
stimulation parameters are being tuned.

Key features
============

* **SVD-based artifact removal** that adapts automatically to the stimulation
  settings.
* **Offline and real-time processing**, including streaming through a TCP/IP
  connection.
* **Windows standalone application** with a graphical interface for loading,
  filtering, processing, inspecting and saving EMG data.
* **Python API** with multiprocessing support for batch analyses.
* **C++ library** of the SVD-based algorithm for integration in external
  software.
* **Several input formats**: text, CSV, BioSigLive (``.bio``), MATLAB
  (``.mat``) and NumPy (``.npz``).
* **Signal-quality metrics** to quantify the effect of the processing.
* **Notch-filter baseline** applied sequentially at the stimulation frequency
  and its harmonics, for comparison purposes.
* **Synthetic artifact generator** (library and GUI) to develop, benchmark
  and tune artifact-removal algorithms under controlled conditions.

How to cite
===========

If you use `StAR-EMG` in your work, please cite the method paper:

    Ceglia A., Hoang Quang N., Iorio-Morin C., Barthélemy D. (2026).
    *Direct assessment of muscle activation during spinal cord stimulation
    using automated artifact removal.* Neuromodulation: Technology at the
    Neural Interface, 29(1), S169.

Authors and acknowledgements
============================

`StAR-EMG` is developed by Amedeo Ceglia (Department of Neurosurgery,
Université de Sherbrooke) whith the support of Christian Iorio-Morin (Université de Sherbrooke) and
Dorothy Barthélemy (School of Rehabilitation, Université de Montréal; CRIR).

This work was supported by the Fonds de recherche du Québec and the New
Frontiers in Research Fund through the
[Re-move project](https://www.usherbrooke.ca/medecine/actualites/nos-grands-dossiers/projet-re-move).

License
=======

`StAR-EMG` is released under the Apache License 2.0. See the ``LICENSE`` file
in the repository.

Links
=====

* Documentation: https://aceglia.github.io/star-emg/ 
* Source code: https://github.com/aceglia/star-emg
* Bug tracker: https://github.com/aceglia/star-emg/issues

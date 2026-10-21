========
Examples
========

Complete, commented scripts that use the `StAR-EMG` Python API. The source of
each script is also provided in the ``examples`` folder of the repository.
Replace the data paths with your own recordings (see :doc:`data_formats`).

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - Example
     - What it shows
   * - :doc:`offline_remover`
     - Load a file, remove the artifacts, analyze, plot and save. Includes
       multi-channel processing, multiprocessing, the notch-filter
       comparison and batch processing of a folder.
   * - :doc:`rt_remover`
     - Process data chunk by chunk with ``RtArtifactRemover``, from a
       prerecorded file or from a stream, as in a live acquisition.
   * - :doc:`generate_synthetic_signal`
     - Add synthetic stimulation artifacts to a clean EMG signal to test and
       tune the algorithm.

.. toctree::
   :maxdepth: 2

   offline_remover
   rt_remover
   generate_synthetic_signal

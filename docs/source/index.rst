StAR-EMG documentation
======================

**StAR-EMG** (*Stimulation Artifact Removal in EMG*) removes stimulation
artifacts from electromyographic (EMG) recordings acquired during
transcutaneous spinal cord stimulation, offline or in real time, without prior
knowledge of the stimulation frequency or waveform.

It is available in three forms. Pick the one that fits your needs:

.. list-table::
   :header-rows: 1
   :widths: 22 48 30

   * - Form
     - Best for
     - Start here
   * - **Windows application** (``StAR-EMG.exe``)
     - Clinicians and researchers who want a graphical tool, with no
       programming and no installation.
     - :doc:`install`, then :doc:`remover_app`
   * - **Python package** (``star_emg``)
     - Scripted analyses, batch processing, integration into custom
       pipelines, access to every parameter.
     - :doc:`install`, then :doc:`getting_started`
   * - **C++ library**
     - Embedding the algorithm in external, performance-critical software.
     - :doc:`cpp`

.. toctree::
   :maxdepth: 2
   :caption: Getting started

   about
   install
   getting_started

.. toctree::
   :maxdepth: 2
   :caption: User guide

   concepts
   data_formats
   parameters
   remover_app
   streaming
   quality_metrics
   generator_app

.. toctree::
   :maxdepth: 2
   :caption: Python examples

   examples

.. toctree::
   :maxdepth: 2
   :caption: C++ library

   cpp

.. toctree::
   :maxdepth: 2
   :caption: Reference

   modules

.. toctree::
   :maxdepth: 2
   :caption: Help and development

   faq
   development

Indices
-------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

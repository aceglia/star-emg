# Installation

`StAR-EMG` can be used in three ways. You only need to follow the section that
matches your use case.

| I want to...                                          | Use                      | Section |
|-------------------------------------------------------|--------------------------|---------|
| Process EMG with a graphical tool, without coding      | Windows standalone app   | [Standalone Windows application](#standalone-windows-application) |
| Script analyses or integrate `StAR-EMG` in my own code | Python package           | [Python package](#python-package) |
| Embed the algorithm in C++ software                    | C++ library              | [C++ library](#c-library) |

(standalone-windows-application)=
## Standalone Windows application

The standalone application is a Windows-only build of the graphical interface.
It bundles its own Python runtime, so **nothing else needs to be installed**.

1. Download the latest `StAR-EMG` release from the
   [GitHub repository](https://github.com/aceglia/star-emg).
2. Extract the archive to a folder of your choice (for example
   `C:\Tools\StAR-EMG`).
3. Double-click **`StAR-EMG.exe`** in the extracted folder.

```{figure} images/app_folder.png
:alt: Content of the extracted StAR-EMG folder on Windows, with StAR-EMG.exe highlighted.
:width: 70%

The extracted application folder. Launch `StAR-EMG.exe`.
```

```{important}
The application is distributed as a **folder**, not as a single file. Keep
`StAR-EMG.exe` together with all the other files and sub-folders that came with
it. To make a shortcut, right-click the `.exe` and choose *Send to > Desktop
(create shortcut)* instead of moving the file.
```

```{note}
The standalone application does not necessarily contain the most recent
developments of the Python package. It is rebuilt and updated at every
release.
```

Once the application opens, continue with {doc}`remover_app`.

(python-package)=
## Python package

### Requirements

* Python **3.10 or later**.
* The packages listed below. Most of them are installed automatically when you
  use `conda` or `pip`; the table tells you what each one is used for.

| Package        | Needed for                                                        | Required |
|----------------|-------------------------------------------------------------------|----------|
| `numpy`, `scipy` | Core algorithm (SVD, FFT, filtering)                            | Always |
| `matplotlib`   | Result window (`Solution.plot`, based on Tk)                      | Always |
| `biosiglive`   | `.bio` files, circular buffer and TCP client used by the real-time tools | Always (see note below) |
| `control`      | Synthetic artifact generator (transfer functions)                 | Generator |
| `PyQt5`, `pyqtgraph` | Graphical interfaces (processing GUI and generator GUI)      | GUI |
| `fbpca`        | Randomized SVD (`randomized=True`)                                | Optional |
| `cma`          | Experimental parameter optimizer (`star_emg.optimizer`)           | Optional |
| `tkinter`      | Result window. Included with the standard Python installers and with conda Python | Always |

```{note}
`biosiglive` is developed in parallel with `StAR-EMG`. The real-time features
rely on its `CircularBuffer` and `AsyncTCPClient` classes, which are not
available in every published release. If you get an `ImportError` mentioning
one of these names, install the development version of `biosiglive` from
GitHub:

    pip install git+https://github.com/aceglia/biosiglive.git
```

### Installing from conda

```bash
conda install -c conda-forge star_emg
```

### Installing from the sources

1. Clone or download the
   [repository](https://github.com/aceglia/star-emg) and open a terminal in its
   root folder.
2. Create an environment with the dependencies provided in `environment.yml`:

   ```bash
   conda env create -f environment.yml
   conda activate star_emg
   ```

3. Install the dependencies that are not part of that file:

   ```bash
   pip install control
   pip install git+https://github.com/aceglia/biosiglive.git
   ```

4. Install the package from the root folder of the repository:

   ```bash
   pip install .
   ```

If you plan to modify the code, use an editable install instead
(`pip install -e .`).

### Checking the installation

```bash
python -c "import star_emg; print('StAR-EMG imported successfully')"
```

To open the graphical interface from Python, run the script provided in the
`examples` folder:

```bash
python examples/run_gui.py
```

and, for the synthetic artifact generator:

```bash
python examples/run_generator_gui.py
```

(optimized-linear-algebra-backend-mkl)=
### Optimized linear algebra backend (MKL)

The SVD and the FFT dominate the computing time. For best performance (and in
particular for real-time use) it is **strongly recommended** to use NumPy and
SciPy linked against the **Intel Math Kernel Library (MKL)**, which provides
highly optimized BLAS and LAPACK routines.

The easiest way to get such a build is through conda:

```bash
conda install -c conda-forge numpy scipy "libblas=*=*mkl" "liblapack=*=*mkl"
```

If NumPy and SciPy were previously installed without MKL, remove them first:

```bash
conda remove numpy scipy --force
```

**Verify the backend.** On Windows, list the installed packages:

```bash
conda list | findstr "blas mkl openblas numpy scipy"
```

(on Linux/macOS replace `findstr` with `grep -E`). The output should contain
entries similar to:

```text
libblas    xxx    ..._mkl
libcblas   xxx    ..._mkl
liblapack  xxx    ..._mkl
mkl        xxx
```

A more reliable runtime check uses `threadpoolctl`:

```bash
conda install threadpoolctl
```

```python
from threadpoolctl import threadpool_info

for library in threadpool_info():
    print(library)
```

The output should contain `'user_api': 'blas'` and `'internal_api': 'mkl'`.

```{tip}
When several channels are processed in parallel processes (the `threads`
argument of `ArtifactRemover.process`, or the real-time GUI), limit the number
of threads used by MKL inside each process to avoid oversubscribing the CPU.
Set the environment variable **before** importing NumPy:

    import os
    os.environ["MKL_NUM_THREADS"] = "1"
```

(c-library)=
## C++ library

The C++ library implements the SVD-based artifact removal only (no file
reading, no GUI, no notch filter). Build instructions are given in {doc}`cpp`.

## Using the documentation examples

Several examples refer to a `data` folder that contains sample recordings
(for instance `data\test001.txt`). Replace these paths with your own files; see
{doc}`data_formats` for the accepted formats.

# Development

This page is for people who want to modify `StAR-EMG`, run its tests, build
this documentation, or produce the Windows application.

## Repository layout

| Folder / file | Content |
|---------------|---------|
| `star_emg/` | The Python package. |
| `star_emg/automatic_remover.py` | `ArtifactRemover`, the offline remover. |
| `star_emg/rt_automatic_remover.py` | `RtArtifactRemover`, the real-time remover. |
| `star_emg/decomposition_utils.py` | Hankel matrix, SVD, component rejection, reconstruction. |
| `star_emg/processing_utils.py` | Per-channel processing, windowing, notch filter, multiprocessing helpers. |
| `star_emg/io_utils.py` | `DataLoader`, file readers and writers, filtering. |
| `star_emg/solution.py`, `plot_utils.py` | `Solution` object, quality metrics and result window. |
| `star_emg/streaming_utils.py` | `DataStreamer`, used to replay a file in chunks. |
| `star_emg/generator.py`, `generator_utils.py` | Synthetic artifact generator and amplitude modulator. |
| `star_emg/generator_app/` | Graphical interface of the generator. |
| `star_emg/app/` | Graphical interface of the artifact remover (offline and stream). |
| `star_emg/optimizer/` | Experimental optimization of processing parameters. |
| `cpp_package/` | C++ library and demo ({doc}`cpp`). |
| `examples/` | Example scripts and sample configurations. |
| `tests/` | Unit tests (`pytest`). |
| `docs/` | This documentation (Sphinx). |
| `run_gui.spec`, `hook-f2py.py` | PyInstaller files used to build the Windows application. |

## Running the tests

```bash
pip install pytest
pytest tests
```

## Building the documentation

The documentation is written with [Sphinx](https://www.sphinx-doc.org) using
the Read the Docs theme. Pages are written in reStructuredText (`.rst`) or
Markdown (`.md`, through MyST). The heavy dependencies (PyQt5, biosiglive,
...) are mocked in `docs/source/conf.py`, so you only need the documentation
requirements:

```bash
pip install -r docs/requirements.txt
cd docs
make html              # on Windows: make.bat html
```

Open `docs/build/html/index.html` in your browser. The project is built
automatically by Read the Docs from `.readthedocs.yaml`, using
`docs/environment_doc.yml`.

### Adding screenshots

All images are in `docs/source/images/`. The pages already reference every
screenshot by file name. To replace a placeholder, save your screenshot under
**the same file name** in that folder (see `images/README.md` for the list of
names and what each one should show). Prefer PNG for interface screenshots.
No change to the pages is necessary.

## Building the Windows application

The standalone application is built with [PyInstaller](https://pyinstaller.org)
from the `run_gui.spec` file, in an environment where `star_emg` and all its
dependencies are installed:

```bash
pip install pyinstaller
pyinstaller run_gui.spec
```

The spec file packages the script `run_gui.py` (provided in `examples/`) as a
windowed application (no console) in a **folder** (`dist/`) that contains the
executable and its libraries. The extra hook `hook-f2py.py` is used to keep
the build compatible with NumPy. Distribute the whole folder, for instance as
a zip archive.

## Contributing

Bug reports, questions and pull requests are welcome on the
[GitHub repository](https://github.com/aceglia/star-emg). When you change a
function signature or a default value, please update the corresponding page of
this documentation ({doc}`parameters`) at the same time.

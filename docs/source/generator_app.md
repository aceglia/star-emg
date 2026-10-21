# Artifact generator application

The **Artifact Generator** is a small graphical tool to design synthetic
stimulation artifacts and to see immediately what they look like. It is
aimed at developing, benchmarking and tuning artifact-removal methods. The
model behind the templates is described in {doc}`generate_synthetic_signal`.

Start it from Python with:

```bash
python examples/run_generator_gui.py
```

or from your own script:

```python
import sys
from PyQt5.QtWidgets import QApplication
from star_emg.generator_app.generator_gui import GUI

if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = GUI()
    app.exec()
```

```{note}
The generator application is part of the Python package and is started from
Python. The Windows standalone application launches the processing GUI only.
The generator requires the `PyQt5`, `pyqtgraph` and `control` packages
({doc}`install`).
```

## The window

```{figure} images/generator_gui.jpg
:alt: Artifact generator window with the template and the stimulation train on the left and the parameters on the right.
:width: 95%

The artifact generator. Top left: the artifact template. Bottom left: the
resulting stimulation train. Right: the template parameters.
```

| Area | Content |
|------|---------|
| **Toolbar** (top) | **Load config**, **Save**, **Save As** and **Quit**. |
| **Template plot** (top left) | The artifact template. The thin grey curve is the smooth response computed from the transfer function; the red curve is the template resampled at the sampling rate and the duration you chose, which is the one actually used to build the train. |
| **Signal plot** (bottom left) | The train of artifacts generated at the stimulation frequency. |
| **Parameters** (right) | The values that define the template and the train. |
| **Log** (bottom) | Messages. **Clear Log** empties it. |

## Parameters

| Field | Python argument | Description |
|-------|-----------------|-------------|
| **Transfert function denominator** (three boxes) | `den` | Coefficients $a$, $b$, $c$ of $H(s) = 1/(a s^2 + b s + c)$. |
| **Step delays** (two boxes) | `delay_1`, `delay_2` | Delays of the second and third steps of the biphasic template. |
| **Amplitude (around 1)** | `amplitude` | Amplitude of the template. |
| **Sum factors (+/-/+)** (three boxes) | `factors` | Weights of the three steps. |
| **Transfert function** | - | Read-only display of the resulting transfer function. |
| **Stimulation frequency** | `stimulation_frequency` | Frequency of the artifact train (Hz). |
| **Sampling rate** | `sampling_rate` | Sampling rate of the signal (Hz). |
| **Template_duration** | `artifact_duration` | Duration of one artifact (s). |

**Generate template** recomputes the template and the train with the current
values.

### Random values

The denominator, delay, amplitude, factor and template-duration fields accept
either one value, or **two values between brackets**, `[min, max]`. In the second case a random value is drawn between
the bounds each time a template is generated:

```text
Denominator:   [0.02, 0.025]   0.5   12
Template_duration:   [0.0055, 0.006]
```

Click **Generate template** several times to see the variability of the
artifacts. The same notation is used by the Python API.

### Display options

| Option | Effect |
|--------|--------|
| **Apply phase inversion** | Alternate the polarity of consecutive artifacts. |
| **Show FFT** | Show the frequency content of the train, to check at which frequencies the artifacts put their energy. |
| **Cursor position** | Coordinates of the mouse pointer on the plots. |

## Typical workflow

1. Start with the default values and click **Generate template**.
2. Adjust the denominator, delays and factors until the template resembles the
   artifact in your recordings. Compare with a raw EMG recording of your own.
3. Set the stimulation frequency, the sampling rate and the duration.
4. Use brackets to add variability if the amplitude or the shape of your real
   artifacts changes from one pulse to the next.
5. Choose **Save As** and store the configuration as a `.json` file. **Save**
   writes to the same file again.
6. Use the configuration in Python to contaminate a clean recording, as shown in
   {doc}`generate_synthetic_signal`, and save the resulting signal as a `.bio`
   file.
7. Load the contaminated file in the processing GUI or in a script to test the
   artifact removal.

To come back to a previous design, use **Load config**.

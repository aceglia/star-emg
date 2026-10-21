# Generate a synthetic signal

The synthetic artifact generator superimposes artificial stimulation
artifacts on a **clean** EMG recording. Because the clean signal is known, you
can measure how well an artifact-removal method recovers it, develop new
methods, or tune the parameters of `StAR-EMG` under controlled and
reproducible conditions.

The templates can be designed visually with the generator application
({doc}`generator_app`) and then used from Python as shown here.

## The artifact model

An artifact is modeled as the response of a second-order system to a biphasic
square pulse. The system is described by the transfer function

$$
H(s) = \frac{1}{a s^2 + b s + c}
$$

where the coefficients $a$, $b$ and $c$ shape the temporal characteristics of
the artifact (the denominator coefficients `den`, listed in the order
`[a, b, c]`). A biphasic pulse is the sum of three steps with alternating
signs, so the template is built from three copies of the step response $y(t)$:

$$
\text{template}(t) = f_1\, y(t) - f_2\, y(t - d_1) + f_3\, y(t - d_2)
$$

where $d_1$ and $d_2$ are the delays of the second and third steps
(`delay_1`, `delay_2`) and $f_1, f_2, f_3$ are weighting factors (`factors`,
sign pattern `+ / - / +`). The template is normalized, scaled by `amplitude`,
and resampled to the requested duration `artifact_duration` (in seconds).
It is then repeated at the stimulation frequency over the whole signal.

```{note}
The delays $d_1$ and $d_2$ are expressed on the time axis of the step response
(whose length is `T = 1`), not in seconds of the final artifact. The whole
template is then compressed to `artifact_duration` seconds.
```

## Random variability

Real artifacts are never perfectly identical. For each of the parameters
`artifact_duration`, `amplitude`, `delay_1`, `delay_2`, and for each
coefficient of `num`, `den` and `factors`, you can provide either:

* a **single value**: the same value is used for every artifact; or
* a **pair `[min, max]`**: a new random value, drawn uniformly between the
  bounds, is used for **each** artifact of the train.

Random values are rounded to three decimals, so intervals narrower than 0.001
have no effect.

## Amplitude modulation

The `Modulator` multiplies the artifact train by an envelope, to mimic changes
of the stimulation intensity during a recording.

| `modulation_type` | Behavior | Parameters |
|-------------------|----------|------------|
| `"constant"` | The train is multiplied by a constant. | `constant_factor` |
| `"linear"` | The factor increases linearly from `min` to `max` over the whole signal. | `min`, `max` |
| `"steps"` | The factor changes by steps from `min` to `max`. | `min`, `max`, and **either** `step_length` (samples per step) **or** `step_inc` (increment of the factor) |

The modulation is applied once, as a single envelope, over the whole signal
provided.

## Generating a signal and saving it

```python
import numpy as np

from star_emg.generator import ArtifactGenerator
from star_emg.generator_utils import Modulator
from star_emg.io_utils import DataLoader

if __name__ == "__main__":
    generator = ArtifactGenerator()

    # Load a clean EMG recording (no stimulation artifacts)
    data_path = r"data\clean_emg.txt"
    data_loader = DataLoader(data=data_path, signal_filter=False, center=True)
    # first epoch, first channel: a 1-D array of shape (n_samples,)
    signal = np.asarray(data_loader.init_data[0, 0, :], dtype=np.float64)

    frequencies = [30, 50, 80]       # stimulation frequencies (Hz)
    modulations = ["linear", "steps"]

    for m in modulations:
        # The same modulator object is used for every frequency
        modulator = Modulator(modulation_type=m, min=0, max=1.2,
                              step_inc=None, step_length=9629)
        for f in frequencies:
            generator.apply_artifact_to_signal(
                signal,
                artifact_duration=[0.0055, 0.006],   # s, random in [min, max]
                stimulation_frequency=f,             # Hz
                sampling_rate=data_loader.data_rate, # Hz
                delay_1=[0.1, 0.15],                 # delay of the 2nd step
                delay_2=[0.22, 0.27],                # delay of the 3rd step
                num=[1],                             # numerator of H(s)
                den=[[0.02, 0.025], [0.4, 0.5], [14, 18]],  # a, b, c of H(s)
                amplitude=np.max(signal),            # scaled by the modulation
                phase_inversion=False,               # alternate polarity?
                factors=[[0.95, 1.05], [1.95, 2.05], [0.95, 1.05]],  # f1, f2, f3
                modulator=modulator,
            )
            generator.save(data_path.replace(".txt", f"_with_artifacts_{f}Hz_{m}.bio"))
```

`apply_artifact_to_signal` returns the contaminated signal and keeps the clean
signal. `generator.save(path)` writes a `.bio` file that contains

* `signal_with_artifacts` (also stored under `values`, so the file can be
  opened directly by `StAR-EMG` and by the GUI),
* `init_signal`, the clean signal that you started from, usable as ground
  truth,
* `data_rate` and all the parameters of the artifact.

## Using a template saved from the generator application

When you save a configuration from the generator GUI ({doc}`generator_app`) you
get a JSON file like this one (`examples/config.json`):

```json
{
    "amplitude": 1,
    "delay_1": 0.1,
    "delay_2": 0.2,
    "num": [1],
    "den": [0.02, 0.518, 12.0],
    "T": 1,
    "factors": [1, 2, 1],
    "sampling_rate": 2000,
    "duration": 0.007,
    "stim_freq": 30
}
```

Use it from Python:

```python
import json
from star_emg.generator import ArtifactGenerator
from star_emg.generator_utils import Modulator

with open("config.json") as f:
    cfg = json.load(f)

contaminated = ArtifactGenerator().apply_artifact_to_signal(
    signal,
    artifact_duration=cfg["duration"],
    stimulation_frequency=cfg["stim_freq"],
    sampling_rate=cfg["sampling_rate"],
    delay_1=cfg["delay_1"],
    delay_2=cfg["delay_2"],
    num=cfg["num"],
    den=cfg["den"],
    amplitude=cfg["amplitude"] * abs(signal).max(),   # the GUI amplitude is relative (about 1)
    factors=cfg["factors"],
    modulator=Modulator(modulation_type="constant", constant_factor=1),
)
```

```{note}
In the generator application the amplitude is expressed relative to a unit
template ("around 1"). In Python the amplitude is in the unit of your signal,
so scale it to the amplitude of your EMG (for example, a multiple of
`np.max(signal)`).
```

## Evaluating the removal against the ground truth

```python
import numpy as np
from biosiglive import load
from star_emg.automatic_remover import ArtifactRemover

if __name__ == "__main__":
    path = "clean_emg_with_artifacts_50Hz_linear.bio"
    truth = np.asarray(load(path)["init_signal"]).ravel()   # clean signal

    remover = ArtifactRemover(data=path, center=False, signal_filter=False)
    sol = remover.process(hankel_size=400, process_window=5000,
                          freq_bounds=[10, 450], factor=0.35)

    raw = sol.init_data[0, 0]
    cleaned = sol.output[0, 0]
    print("Correlation with the clean signal, before:", np.corrcoef(raw, truth)[0, 1])
    print("Correlation with the clean signal, after: ", np.corrcoef(cleaned, truth)[0, 1])
```

Try different values of `factor`, `hankel_size` and `freq_bounds` and keep the
ones that bring the processed signal closest to the clean one.

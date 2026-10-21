# Signal-quality metrics

How do you know the artifact removal worked? Looking at the signal and its
spectrum is always the first check. `StAR-EMG` also computes four numerical
indicators for the raw and the processed signal of every channel and every
epoch. They are displayed in the GUI (right panel and channel information) and
returned by `Solution.analyse()` in Python.

```{figure} images/results_window.jpg
:alt: Result window with the analysis text and the FFT with dashed markers.
:width: 80%

Result window with the analysis enabled. The text at the top of the signal
plot reports kurtosis and line length. In the FFT plot, the dashed vertical
lines mark the median frequency and the dashed horizontal lines the FFT
amplitude, in the colors of the raw and processed signals.
```

## The four metrics

| Metric | What it measures | What to expect after a successful removal |
|--------|------------------|--------------------------------------------|
| **Kurtosis** | How "spiky" the signal is. The signal is cut in blocks of `kw` samples (100 by default); the excess kurtosis of each block is computed and the values are averaged. Samples exactly equal to zero are ignored. | Lower. Large, brief artifact spikes give a high kurtosis; a noise-like EMG gives values close to 0. |
| **Line length** | The sum of the absolute variations between neighboring samples, normalized by the standard deviation and the length of the signal. It captures the roughness of the signal. | Lower, because the sharp artifact transitions are removed. |
| **Median frequency** | The frequency that splits the power spectrum in two halves of equal energy. | Moves away from the stimulation frequencies and their harmonics towards a value typical of EMG. |
| **FFT amplitude** | A robust maximum of the FFT magnitude below `maxw` (150 Hz by default): bins that are outliers are discarded first, then a high percentile is taken (99.5 for the raw and 99.9 for the processed signal by default). | Same, as the robust maximum should exclude the sharp peak due to the artifact. |

In the GUI screenshot of {doc}`remover_app`, one channel went from a kurtosis
of 8.49 (raw) to 0.026 (processed) and from a median frequency of 195.6 Hz to
59.8 Hz.

```{note}
These metrics are indicators, not proof. They are computed without a reference
(ground-truth) signal, so they cannot tell the difference between removed
artifact and removed EMG. Always combine them with a visual inspection of the
time signal and of the spectrum, and compare channels or conditions only with
the same parameters.
```

## Computing the metrics in Python

```python
sol = remover.process(hankel_size=450, process_window=5000)
results = sol.analyse()

# `results` is a dictionary. Each entry is a list [raw, processed] of arrays
# of shape (n_epochs, n_channels).
raw_kurtosis, processed_kurtosis = results["kurtosis"]
print("Kurtosis, epoch 0, channel 0:",
      raw_kurtosis[0, 0], "->", processed_kurtosis[0, 0])

for name in ["kurtosis", "Line Length", "Median frequency", "FFT Amplitude"]:
    raw, processed = results[name]
    print(f"{name:18s} raw={raw[0, 0]:.4g}  processed={processed[0, 0]:.4g}")
```

Optional keyword arguments of `analyse` change the way the metrics are
computed:

| Argument | Default | Meaning |
|----------|---------|---------|
| `kw` | `100` | Block length (samples) for the kurtosis. |
| `maxw` | `150` | Upper frequency (Hz) for the FFT amplitude. |
| `percentile` | `[99.5, 99.9, 99.9]` | Percentiles used for the FFT amplitude of the raw, processed and (unused) reference signal. |
| `fft_freqs` | `None` | Precomputed frequency vector. |

To display the metrics in the result window, call `analyse()` first, then
`sol.plot(..., show_analysis=True)`. Calling `plot(show_analysis=True)`
before `analyse()` raises an error.

# How StAR-EMG works

This page explains the method implemented in `StAR-EMG` so that you can
choose parameters with confidence and interpret the results. The approach
follows the one published in Ceglia et al. (2026) (see {doc}`about`).

## The problem

During transcutaneous spinal cord stimulation, every stimulation pulse
produces a large, brief deflection in the EMG. At typical stimulation
frequencies (tens of Hz) these deflections repeat many times per second and
can be several times larger than the muscle activity. In the spectrum, they
appear as sharp peaks at the stimulation frequency and its harmonics,
superimposed on the broadband EMG spectrum.

Because the stimulation frequency, intensity and waveform often change during
a session, methods that rely on a fixed template or on fixed notch
frequencies need to be re-tuned each time. `StAR-EMG` instead looks for the
*signature* of the artifact (a narrow-band, highly repetitive component) and
removes it, wherever it is.

## Overview of the algorithm

The algorithm works on one channel at a time and on successive windows of
that channel.

```text
 raw channel
     |
     |  (optional) centering + band-pass filter
     v
 split into windows of `process_window` samples
     |
     v   for each window
 1. build the Hankel (delay-embedding) matrix H
 2. singular value decomposition  H = U S V^T
 3. for each right singular vector v_k: measure how "peaky" its spectrum is
 4. reject the components that look like artifacts  (set s_k = 0)
 5. rebuild H, then rebuild the signal by anti-diagonal averaging
     |
     v
 cleaned channel
```

### 1. Hankel matrix

For a window $x_0, \dots, x_{N-1}$, the Hankel matrix has $L$ rows
(`hankel_size`) and $K = N - (L-1)\tau$ columns, where $\tau$ is the delay
between consecutive rows (`hankel_delay`):

$$
H_{i,j} = x_{i\tau + j}, \qquad i = 0,\dots,L-1,\quad j = 0,\dots,K-1 .
$$

Each row is a shifted copy of the window. A repetitive artifact therefore
shows up as a strongly structured, low-rank pattern in $H$.

```{note}
$L$ and $\tau$ must satisfy $N > (L-1)\tau$, otherwise the matrix cannot be
built and an error is raised.
```

### 2. Singular value decomposition

The matrix is decomposed as

$$
H = U \, \Sigma \, V^{\mathsf T} = \sum_{k} \sigma_k \, u_k v_k^{\mathsf T}.
$$

The rows of $V^{\mathsf T}$ (the right singular vectors $v_k$, each of length $K$)
are temporal components of the window, ordered by decreasing energy
$\sigma_k$. Large, periodic artifacts are captured by a few
high-energy components. The more stochastic EMG is spread over many
components.

### 3. Spectral analysis of each component

For every right singular vector $v_k$, `StAR-EMG` computes its FFT and extracts two
numbers:

* the **dominant frequency** $f_k$, the frequency of the largest spectral
  peak;
* the **peak energy ratio** $\rho_k$, the power at that peak divided by the
  mean power in a neighborhood (±5 % of the spectrum length) around it. A pure
  or narrow-band oscillation (artifact-like) has a large $\rho_k$; a
  broadband component (EMG-like) has a small one.

The ratio is then normalized by its largest value across components,
$r_k = \rho_k / \max_j \rho_j$.

### 4. Component rejection

A component is rejected when **either** condition holds:

1. its dominant frequency is outside the accepted band,
   $f_k \le f_{\min}$ or $f_k \ge f_{\max}$ (`freq_bounds`);
2. its normalized peak ratio is unusually high compared with the other
   components of the window,

   $$
   r_k > \operatorname{median}(r) + \lambda \cdot \operatorname{std}(r),
   $$

   where $\lambda$ is the `factor` parameter (called **Threshold** in the GUI).

The singular values of the rejected components are set to zero.

* A **smaller** $\lambda$ lowers the threshold, so **more** components are
  rejected (stronger cleaning, with a higher risk of removing EMG).
* A **larger** $\lambda$ rejects fewer components (gentler cleaning, with a
  higher risk of leaving artifact residue).

Because condition 1 discards components dominated by frequencies above
$f_{\max}$, the upper bound also acts as a soft limit on the bandwidth of the
output.

### 5. Reconstruction

The cleaned matrix $\tilde H = U\,\tilde\Sigma\,V^{\mathsf T}$ (with the
rejected $\sigma_k$ set to zero) is converted back to a one-dimensional
signal by averaging each anti-diagonal (every sample of the signal appears
several times in $H$; the cleaned estimates are averaged).

## Windowing

Long recordings are processed window by window, and each window gets its own
decomposition and its own set of rejected components. This is what makes the
method adaptive: if the stimulation intensity or frequency changes during the
recording, each window is cleaned according to what it contains.

* The window length is `process_window` samples (**Window length** in the
  GUI). It is capped at **10 000 samples**.
* Windows do not overlap. When the last window would be shorter than
  `process_window`, it is extended backwards so that it keeps the full length;
  the part that was already processed is discarded.

## Offline and real-time operation

| | Offline (`ArtifactRemover`, GUI offline mode) | Real-time (`RtArtifactRemover`, GUI stream mode) |
|---|---|---|
| Input | A whole file | Successive small chunks of data |
| Processing unit | Consecutive non-overlapping windows | A sliding window (buffer) that is refreshed by every chunk |
| Pre-filter | Zero-phase (forward-backward) | Causal (forward only) |
| Output | The whole cleaned recording | The cleaned latest chunk |
| Cost control | `threads` (a pool of worker processes, one task per channel) | `update_svd_every` (reuse the rejected components for several chunks) |

In real-time mode the latest `window_size` samples are kept in a circular
buffer. Each time a chunk arrives, the algorithm runs on the buffer and
returns the part corresponding to the newest chunk. The first
`window_size` samples are used to fill the buffer and produce no output.

The computing time grows with the window length and with the Hankel size, so
the real-time parameters are a compromise between cleaning quality and
latency; see {doc}`parameters`.

## The notch-filter alternative

For comparison, `StAR-EMG` includes a classical alternative: a cascade of
IIR notch filters placed at the stimulation frequency and its harmonics. The
notch frequencies are

$$
f_i = f_\text{first} + i \cdot f_\text{stim}, \qquad i = 0, 1, 2, \dots
$$

up to the Nyquist frequency, where $f_\text{stim}$ is `frequency_peaks` and
$f_\text{first}$ is `first_peak` (equal to `frequency_peaks` if not given).
The `quality_factor` controls the width of each notch (higher means narrower).
Unlike the SVD approach, this method needs the stimulation frequency in
advance and removes everything at the notch frequencies, including EMG.

## Data model

All processing functions work on arrays of shape

```text
(n_epochs, n_channels, n_samples)
```

An *epoch* is an independent recording segment (for instance one stimulation
trial, or one frame of a CED Signal file). Every (epoch, channel) pair is
processed independently as a one-dimensional signal. Data with fewer
dimensions are accepted: a 1-D array is interpreted as one epoch and one
channel, and a 2-D array as one epoch with several channels.

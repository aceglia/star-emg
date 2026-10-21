# Frequently asked questions

## Installation and start-up

**The Windows application does not start, or closes immediately.**
Make sure you extracted the whole archive and that `StAR-EMG.exe` is still in
the folder with all its other files (see {doc}`install`). The application has
no console window: when it runs, errors are written in the log panel at the
bottom of the window.

**`ImportError: cannot import name 'CircularBuffer'` (or `AsyncTCPClient`).**
The installed version of `biosiglive` is too old. Install the development
version: `pip install git+https://github.com/aceglia/biosiglive.git`.

**The result window of `sol.plot()` does not open / `No module named 'tkinter'`.**
The result window uses Tk. Use a Python distribution that includes Tk (the
standard installers and conda do; some Linux distributions need an extra
package such as `python3-tk`).

**My script hangs or restarts itself when `threads > 1`.**
Put the code that creates the `ArtifactRemover` and calls `process` under
`if __name__ == "__main__":`. Worker processes re-import your script, which
is mandatory on Windows.

## Loading data

**`Data rate must be provided if not loaded from file`.**
The file does not store its sampling rate. Pass `data_rate=` in Python, or
enter the rate in the **Filter** dialog of the GUI. See {doc}`data_formats`.

**`Filter cutoff (...) is not suitable for the frequency (...)`.**
The upper cut-off of the band-pass filter must be below half the sampling
rate. Lower the cut-off or check that the sampling rate is correct.

**My file contains a time column.**
It is detected automatically when the values increase regularly, and used to
compute the sampling rate. Make sure it is the first column.

## Processing

**`L and tau too large`.**
The Hankel matrix does not fit in the window: `hankel_size` and `hankel_delay`
must satisfy `(hankel_size - 1) * hankel_delay < window length`. Reduce the
Hankel size or increase the window. See {doc}`concepts`.

**Some artifact remains after processing.**
Lower the threshold (`factor`), increase the Hankel size, or check that the
frequency bounds include the artifact frequencies. Look at the FFT with
**Show FFT** to see which peaks remain. See {doc}`parameters`.

**The processed signal looks too flat, or EMG bursts are lost.**
The cleaning is too aggressive. Increase the threshold, and check the upper
frequency bound.

**The GUI and my script give different results.**
The default values are not the same (for example threshold 0.35 in the GUI,
0.5 in the Python API). Set every parameter explicitly in both. See
{doc}`parameters`.

**Processing is slow.**
Reduce the window length and the Hankel size, process fewer channels, use
`threads`, and use NumPy/SciPy with MKL
({ref}`optimized-linear-algebra-backend-mkl`).

**Why is the window length limited to 10 000 samples?**
The decomposition cost grows quickly with the window. Longer recordings are
processed window by window, each with its own decomposition, which also lets
the method follow changes of the stimulation.

## Real-time

**The display lags behind the acquisition.**
Processing one chunk takes longer than receiving it. See *Performance and
troubleshooting* in {doc}`streaming`.

**The client cannot connect to the GUI.**
Start the server first, check the address and port, and check your firewall.

## Other

**Can I use StAR-EMG on Linux or macOS?**
The Python package and the C++ library are not limited to Windows. The
standalone application is Windows-only.

**How do I report a bug or ask for a feature?**
Open an issue on the
[GitHub repository](https://github.com/aceglia/star-emg/issues).

**How do I cite StAR-EMG?**
See {doc}`about`.

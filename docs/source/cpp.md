# C++ library

The `cpp_package` folder of the repository contains a C++ implementation of
the SVD-based artifact-removal algorithm. It is intended for integration into
external, performance-critical software, such as real-time acquisition
programs or audio/DSP plug-ins, where a Python runtime is not an option.

## What it contains (and what it does not)

| Included | Not included (use the Python package or do it in your code) |
|----------|-------------------------------------------------------------|
| Hankel matrix construction | Reading and writing data files |
| SVD of the Hankel matrix (Eigen) | Centering and band-pass pre-filtering |
| Spectral analysis of the components (pocketfft) and component rejection | Splitting a long recording into windows |
| Reconstruction by anti-diagonal averaging | Multi-channel handling (one channel per call) |
| | The notch-filter alternative |
| | Quality metrics |

The algorithm is the same as in the Python package ({doc}`concepts`).
Windowing, filtering and the management of several channels are left to the
calling code: call `remove_artifact` once per window and per channel.

## Requirements

* A C++17 compiler (MSVC, GCC or Clang) and [CMake](https://cmake.org) 3.15 or later.
* An internet connection for the first configuration: CMake downloads
  [Eigen](https://eigen.tuxfamily.org) (branch `5.0`) and
  [pocketfft](https://github.com/mreineck/pocketfft) (C++ version)
  automatically with `FetchContent`.
* *Optional:* Intel oneAPI MKL, to accelerate the linear algebra (see below).

## Building

From the `cpp_package` folder:

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
```

This builds the `star_emg` library and a demonstration program, `demo_app`.
To run the demo, place the sample file `demo/signal.txt` in the folder from
which you start the executable, because the program opens it by relative
path.

### Using MKL

When the Intel oneAPI MKL is found, the library is compiled to use it for the
linear algebra, which gives a significant speed-up. The MKL location is set
in `CMakeLists.txt`:

```cmake
set(MKL_ROOT "C:/Program Files (x86)/Intel/oneAPI/mkl/2026.0")
```

Edit this line so that it points to your own MKL installation. If the
`mkl.h` header is not found at that location, the build falls back to Eigen's
own routines.

## API

The public interface is in `star_emg/remover.h`.

```cpp
star_emg::Remover remover;

star_emg::RemovalResult result = remover.remove_artifact(
    signal,          // const star_emg::Vector&: one channel, one window
    L,               // int: number of rows of the Hankel matrix (hankel_size)
    tau,             // int: delay between rows (hankel_delay)
    data_rate,       // double: sampling rate in Hz
    lower_freq,      // double: lower frequency bound (default 10.0)
    upper_freq,      // double: upper frequency bound (default 450.0)
    factor,          // double: rejection threshold factor (default 0.5)
    svd_threshold    // double: drop singular values <= this value (default 0.0 = keep all)
);
```

The parameters have the same meaning as in the Python package
({doc}`parameters`): `L` is `hankel_size`, `tau` is `hankel_delay`,
`lower_freq` and `upper_freq` are `freq_bounds`, `factor` is `factor`, and
`svd_threshold` plays the role of `epsilon`.

`RemovalResult` contains:

| Member | Content |
|--------|---------|
| `cleaned_signal` | The processed signal (a vector with the length of the input). |
| `hankel` | The Hankel matrix built from the input. |
| `U`, `S`, `Vh` | The thin SVD of the Hankel matrix (after the optional truncation). |
| `rejected_idx` | Indices of the components that were rejected. |

`star_emg::Vector` and `star_emg::Matrix` are Eigen types
(see `star_emg/Types.h`).

### Minimal example

```cpp
#include <iostream>
#include <vector>

#include "star_emg/remover.h"

int main()
{
    const double fs = 2000.0;              // sampling rate (Hz)
    std::vector<double> samples = /* fill with one window of one channel */;

    star_emg::Vector window =
        Eigen::Map<star_emg::Vector>(samples.data(), samples.size());

    star_emg::Remover remover;
    auto result = remover.remove_artifact(window, /*L=*/100, /*tau=*/1, fs,
                                          /*lower_freq=*/10.0,
                                          /*upper_freq=*/450.0,
                                          /*factor=*/0.3);

    std::cout << "Rejected " << result.rejected_idx.size() << " components\n";
    // result.cleaned_signal holds the processed window
    return 0;
}
```

The window must be longer than `(L - 1) * tau`; otherwise an exception
(`std::runtime_error`) is thrown.

## Integrating into your project

Link your target against the `star_emg` library built by CMake and include the
header from the `include` folder. Because the library uses Eigen, compile with
the same C++17 settings. If you copy the sources into your own build system,
you need `src/SignalDecomposition.cpp`, `src/FFT.cpp`, `src/remover.cpp` and
the headers in `include/star_emg`, plus Eigen and pocketfft on the include
path.

## Choosing parameters for real-time use

The cost of one call grows with the window length and with `L`. Measure the
time per call on your target machine (the demo prints it) and choose `L` and
the window length so that it is below the duration of the chunk you receive.
The guidance of {doc}`parameters` applies.

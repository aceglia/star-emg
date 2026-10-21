# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

sys.path.insert(0, os.path.abspath("../../"))

# -- Project information -----------------------------------------------------

project = "StAR-EMG"
copyright = "2026, aceglia"
author = "Amedeo Ceglia, Christian Iorio-Morin, Dorothy Barthélemy"
release = "0.0.1"

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinx.ext.autosummary",
    "myst_parser",
]

autosummary_generate = True
napoleon_numpy_docstring = True

# The API reference is built without installing the heavy / GUI / hardware
# dependencies: they are mocked so that autodoc can import every module on
# Read the Docs.
autodoc_mock_imports = [
    "PyQt5",
    "pyqtgraph",
    "biosiglive",
    "control",
    "cma",
    "fbpca",
    "zarr",
    "tkinter",
    "matplotlib.backends.backend_tkagg",
]
# -- Options for MyST ---
myst_enable_extensions = [
    "dollarmath",
    "amsmath",
    "colon_fence",
    "deflist",
]
myst_heading_anchors = 3

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "images/README.md"]

# -- Options for HTML output -------------------------------------------------

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_theme_options = {
    "navigation_depth": 3,
    "collapse_navigation": False,
}

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

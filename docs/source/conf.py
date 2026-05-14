# Configuration file for the Sphinx documentation builder.
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import json
import pathlib
import sys

# Project source root (two levels above docs/source/)
_ROOT = pathlib.Path(__file__).parents[2]
sys.path.insert(0, str(_ROOT))

# Local Sphinx extensions live in docs/source/_ext/
sys.path.insert(0, str(pathlib.Path(__file__).parent / "_ext"))

with open(_ROOT / "versions.json", "r") as f:
    __version__ = json.load(f)["latest"]

# – Project information —————————————————–

project = "HealthAnalyser"
copyright = "2026, Jonathan Grill"
author = "Jonathan Grill"
release = __version__

# – General configuration —————————————————

extensions = [
    # Python autodoc
    "sphinx.ext.apidoc",
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinx_autodoc_typehints",
    # React/JSX autodoc  (docs/source/_ext/react_autodoc.py)
    "react_autodoc",
    # Other
    "sphinx_design",
    "sphinx.ext.intersphinx",
    "sphinx_tippy",
    "sphinx.ext.githubpages",
    "myst_parser",
]

myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "html_image",
    "linkify",
    "strikethrough",
    "tasklist",
]

# – Python autodoc –––––––––––––––––––––––––––––
autodoc_default_options = {
    "members": True,
    "private-members": True,
    "undoc-members": True,
    "show-inheritance": True,
}
apidoc_modules = [
    {"path": "../../src", "destination": "src", "separate_modules": True},
]

# – Napoleon ––––––––––––––––––––––––––––––––

napoleon_numpy_docstring = False
napoleon_use_admonition_for_examples = True

# – Intersphinx ———————————————————––
intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "redis": ("https://redis.readthedocs.io/en/stable/", None),
    "pandas": ("https://pandas.pydata.org/docs/", None),
}

# – React/JSX autodoc —————————————————––
"""Handled by _ext/react_autodoc.py.
Output goes to docs/source/_react_autodoc/ — gitignore this directory.
Reference the index in your top-level index.rst toctree:

.. toctree::
    _react_autodoc/index
"""
js_source_path = "../../frontend/src"  # relative to this conf.py
react_autodoc_output_dir = "react_autodoc"  # relative to docs/source/
react_autodoc_default_options = {
    "members": True,  # document props table
    "private-members": False,  # skip _PrivateComponent
    "undoc-members": False,  # skip components with no JSDoc description
    "show-source": True,  # annotate each component with its file path
}

# – HTML output ———————————————————––

templates_path = ["_templates"]
exclude_patterns = ["_build"]

html_theme = "furo"
html_static_path = ["_static"]
html_favicon = "_static/favicon.ico"
html_show_sourcelink = False

html_theme_options = {
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/strangeflavoured/health",
            "html": """
<svg stroke="currentColor" fill="currentColor" stroke-width="0" viewBox="0 0 16 16">
<path fill-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z"></path>
</svg>
""",
            "class": "",
        },
    ],
}

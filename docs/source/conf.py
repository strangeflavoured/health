# Configuration file for the Sphinx documentation builder.
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import json
import os
import pathlib
import sys

import django
from django.conf import settings
from sphinx.application import Sphinx
from sphinx.ext.autodoc import Options

# Project source root (two levels above docs/source/)
_ROOT = pathlib.Path(__file__).parents[2]
sys.path.insert(0, str(_ROOT))

# Backend/apps source
sys.path.insert(0, str(_ROOT / "backend"))

# Local Sphinx extensions live in docs/source/_ext/
sys.path.insert(0, str(pathlib.Path(__file__).parent / "_ext"))
with open(_ROOT / "versions.json") as f:
    __version__ = json.load(f)["latest"]

# Exclude dev-only content when building release docs
root_doc = "index_release" if os.environ.get("SPHINX_RELEASE_BUILD") else "index"

# – Project information —————————————————–
project = "HealthAnalyser"
copyright = "2026, Jonathan Grill"  # noqa: A001
author = "Jonathan Grill"
release = __version__

# – Django configuration —————————————————
# Minimal Django setup so models can be imported without a full stack
if not settings.configured:
    settings.configure(
        INSTALLED_APPS=[
            "django.contrib.contenttypes",
            "django.contrib.auth",
            "apps.api",
            "apps.workers",
        ],
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            }
        },
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
    )
    django.setup()
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
    {
        "path": "../../backend/apps",
        "destination": "backend",
        "separate_modules": True,
        "exclude_patterns": ["**/test*"],
    },
]

# – Napoleon ––––––––––––––––––––––––––––––––

napoleon_numpy_docstring = False
napoleon_use_admonition_for_examples = True

# – Intersphinx ———————————————————––
intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "redis": ("https://redis.readthedocs.io/en/stable/", None),
    "pandas": ("https://pandas.pydata.org/docs/", None),
    "django": (
        "https://docs.djangoproject.com/en/stable/",
        "https://docs.djangoproject.com/en/stable/_objects/",
    ),
}

# – React/JSX autodoc —————————————————––
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
html_css_files = ["custom.css"]
html_favicon = "_static/favicon.ico"
html_show_sourcelink = False

html_theme_options = {
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/strangeflavoured/health",
            "html": (
                '<svg stroke="currentColor" fill="currentColor" '
                'stroke-width="0" viewBox="0 0 16 16">'
                '<path fill-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47'  # noqa: E501
                " 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94"  # noqa: E501
                "-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72"  # noqa: E501
                " 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95"  # noqa: E501
                " 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18"  # noqa: E501
                " 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16"  # noqa: E501
                " 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54"  # noqa: E501
                ".73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0"  # noqa: E501
                ' 16 8c0-4.42-3.58-8-8-8z"></path></svg>'
            ),
            "class": "",
        },
    ],
}


def _skip_imported_members(
    _app: Sphinx,
    what: str,
    name: str,
    obj: object,
    skip: bool,  # noqa: FBT001
    _options: Options,
) -> bool:
    """Skip members imported from a different module.

    Prevents dataclasses and other classes imported into a module from
    being documented twice — once in their definition module and again
    in every module that imports them.

    Args:
        _app: Sphinx application instance (unused).
        what: Type of object being documented (e.g. ``"module"``).
        name: Fully qualified name of the member.
        obj: The member object itself.
        skip: Whether autodoc would skip this member by default.
        _options: Autodoc options for the current directive (unused).

    Returns:
        ``True`` if the member should be skipped, ``False`` otherwise.

    """
    if skip:
        return skip
    if what != "module":
        return skip
    obj_module = getattr(obj, "__module__", None)
    if obj_module is None:
        return skip
    qualname = getattr(obj, "__qualname__", "")
    if "." in qualname:
        documented_module = name.rsplit("." + qualname.split(".")[0], 1)[0]
    else:
        documented_module = name.rsplit("." + qualname, 1)[0]
    if obj_module != documented_module:
        return True
    return skip


def setup(app: Sphinx) -> None:
    """Register Sphinx event handlers for this project.

    Args:
        app: Sphinx application instance.

    """
    app.connect("autodoc-skip-member", _skip_imported_members)

"""
react_autodoc — Sphinx extension for React/JSX component documentation
=======================================================================

Mirrors ``sphinx.ext.autosummary`` output conventions for a frontend JSX/TSX
source tree.  autosummary is the closest Sphinx built-in: it also generates
RST files into a dedicated folder inside ``srcdir`` at build time, which are
then gitignored so they are never committed.

Output location
---------------
Generated files are written to ``<srcdir>/_react_autodoc/`` by default
(configurable via ``react_autodoc_output_dir``).  Add this to ``.gitignore``::

    docs/source/_react_autodoc/

The index RST at ``<srcdir>/_react_autodoc/index.rst`` should be added to
your top-level ``index.rst`` toctree::

    .. toctree::

       _react_autodoc/index

Build behaviour
---------------
- Runs at ``builder-inited`` — same phase as autosummary's generator
- Discovers all ``.jsx`` / ``.tsx`` files by walking ``js_source_path``
- Runs ``react-docgen`` on each file via ``npx @react-docgen/cli``
- Writes RST only when content has changed (stat-based, like autosummary)
- On ``make clean``, the output dir is removed along with ``_build``
  if you add it to the Makefile's clean target

Respects ``react_autodoc_default_options`` (mirrors ``autodoc_default_options``):

``members``
    Document the props table. Default ``True``.
``private-members``
    Include components whose name starts with ``_``. Default ``False``.
``undoc-members``
    Include components with no JSDoc description. Default ``False``.
``show-source``
    Annotate each component with its relative source path. Default ``True``.

Configuration keys set in ``conf.py``
--------------------------------------
``js_source_path``
    Path to the frontend ``src/`` directory, relative to ``conf.py``.
    Default: ``"../../frontend/src"``

``react_autodoc_output_dir``
    Output directory for generated RST, relative to the Sphinx source dir.
    Default: ``"_react_autodoc"``
    Add to ``.gitignore``: ``docs/source/_react_autodoc/``

``react_autodoc_default_options``
    Dict of generation options (see above).
"""

from __future__ import annotations

import json
import pathlib
import subprocess
from typing import TYPE_CHECKING

import sphinx.util.logging

if TYPE_CHECKING:
    from sphinx.application import Sphinx

logger = sphinx.util.logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Extension defaults — merged with react_autodoc_default_options from conf.py
# ---------------------------------------------------------------------------

_DEFAULT_OPTIONS: dict[str, bool] = {
    "members": True,
    "private-members": False,
    "undoc-members": False,
    "show-source": True,
}


# ---------------------------------------------------------------------------
# react-docgen subprocess
# ---------------------------------------------------------------------------


def _parse_components(
    fpath: pathlib.Path,
    frontend_root: pathlib.Path,
    verbose: bool = False,
) -> list[dict]:
    """
    Run ``npx @react-docgen/cli`` on *fpath* and return a list of component
    dicts.  Returns ``[]`` on any error so callers can safely skip the file.

    Handles both response shapes:

    - react-docgen v6+: ``{"<filepath>": [component, ...], ...}``
    - react-docgen v5 / CLI fallback: ``[component, ...]``
    """
    try:
        result = subprocess.run(
            ["npx", "--yes", "@react-docgen/cli", str(fpath)],
            capture_output=True,
            text=True,
            cwd=frontend_root,
            timeout=30,
        )
    except FileNotFoundError:
        logger.warning("react-autodoc: npx not found — is Node.js installed?")
        return []
    except subprocess.TimeoutExpired:
        logger.warning(f"react-autodoc: react-docgen timed out on {fpath}")
        return []

    if result.returncode != 0:
        if verbose:
            logger.info(
                f"react-autodoc: react-docgen skipped {fpath.name}"
                + (f" — {result.stderr.strip()}" if result.stderr.strip() else "")
            )
        return []

    if not result.stdout.strip():
        if verbose:
            logger.info(f"react-autodoc: no output for {fpath.name}")
        return []

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        logger.warning(f"react-autodoc: invalid JSON from react-docgen for {fpath}")
        return []

    if isinstance(data, dict):
        components: list[dict] = []
        for v in data.values():
            components.extend(v if isinstance(v, list) else [v])
        return components
    if isinstance(data, list):
        return data
    return [data]


# ---------------------------------------------------------------------------
# Skip logic  (mirrors autodoc-skip-member)
# ---------------------------------------------------------------------------


def _should_skip(name: str, description: str, opts: dict) -> bool:
    """
    Return ``True`` if this component should be excluded.

    - Names starting with ``_`` are skipped unless ``private-members`` is set.
    - Components with no description are skipped unless ``undoc-members`` is set.
    """
    if not opts.get("private-members") and name.startswith("_"):
        return True
    if not opts.get("undoc-members") and not description.strip():
        return True
    return False


# ---------------------------------------------------------------------------
# RST generation
# ---------------------------------------------------------------------------


def _build_prop_table(props: dict) -> list[str]:
    """Return RST ``list-table`` lines for *props*, or ``[]`` if empty."""
    if not props:
        return []

    lines = [
        ".. list-table:: Props",
        "   :header-rows: 1",
        "   :widths: 20 15 10 15 40",
        "   :class: react-props-table",
        "",
        "   * - Name",
        "     - Type",
        "     - Required",
        "     - Default",
        "     - Description",
    ]

    for prop_name, info in sorted(props.items()):
        raw_type = info.get("type") or info.get("tsType")
        typ = ""
        if raw_type:
            typ = raw_type.get("name") or raw_type.get("raw", "")

        required = "✓" if info.get("required") else ""
        default_info = info.get("defaultValue")
        default = f"``{default_info['value']}``" if default_info else ""
        desc = (info.get("description") or "").replace("\n", " ")

        lines += [
            f"   * - ``{prop_name}``",
            f"     - ``{typ}``" if typ else "     - ",
            f"     - {required}",
            f"     - {default}",
            f"     - {desc}",
        ]

    return lines


def _rst_for_component(
    component: dict,
    fpath: pathlib.Path,
    frontend_src: pathlib.Path,
    opts: dict,
) -> list[str]:
    """RST lines for a single component (heading + description + props table)."""
    name = component.get("displayName") or fpath.stem
    description = (component.get("description") or "").strip()
    props = component.get("props", {}) if opts.get("members") else {}
    rel_path = fpath.relative_to(frontend_src.parent)  # e.g. src/components/Foo.jsx

    lines: list[str] = [name, "~" * len(name), ""]

    if opts.get("show-source"):
        lines += [f"*Source:* ``{rel_path}``", ""]

    if description:
        lines += [description, ""]

    prop_lines = _build_prop_table(props)
    if prop_lines:
        lines += prop_lines + [""]

    return lines


def _rst_for_module(
    fpath: pathlib.Path,
    components: list[dict],
    frontend_src: pathlib.Path,
    opts: dict,
) -> str:
    """Full RST document for one JSX/TSX file (heading + one section per component)."""
    rel = fpath.relative_to(frontend_src)  # e.g. components/Foo.jsx
    title = str(rel)
    lines = [title, "=" * len(title), ""]

    for component in components:
        name = component.get("displayName") or fpath.stem
        description = (component.get("description") or "").strip()
        if _should_skip(name, description, opts):
            continue
        lines += _rst_for_component(component, fpath, frontend_src, opts)

    return "\n".join(lines) + "\n"


def _write_if_changed(path: pathlib.Path, content: str) -> bool:
    """
    Write *content* to *path* only if it differs from what is already there.

    Returns ``True`` if the file was written.  This mirrors autosummary's
    behaviour of not touching files that haven't changed, which lets Sphinx's
    incremental build skip unchanged documents.
    """
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.write_text(content, encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# Sphinx event handler
# ---------------------------------------------------------------------------


def _generate_react_docs(app: Sphinx) -> None:
    """
    ``builder-inited`` event handler — the same phase autosummary uses.

    Walks ``js_source_path``, runs react-docgen on every JSX/TSX file, and
    writes RST files into ``<srcdir>/<react_autodoc_output_dir>/``.

    Files are only written when their content changes, so Sphinx's incremental
    build correctly skips unchanged documents.
    """
    conf_dir = pathlib.Path(app.confdir)
    src_dir = pathlib.Path(app.srcdir)

    frontend_src = (conf_dir / app.config.js_source_path).resolve()
    if not frontend_src.exists():
        logger.warning(
            f"react-autodoc: js_source_path does not exist\n"
            f"  conf_dir       = {conf_dir}\n"
            f"  js_source_path = {app.config.js_source_path!r}\n"
            f"  resolved       = {frontend_src}"
        )
        return

    # Output dir is inside srcdir — same convention as autosummary's :toctree:
    out_dir = src_dir / app.config.react_autodoc_output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    opts: dict = {**_DEFAULT_OPTIONS, **app.config.react_autodoc_default_options}

    component_files = sorted(
        [*frontend_src.rglob("*.jsx"), *frontend_src.rglob("*.tsx")]
    )

    if not component_files:
        logger.warning(
            f"react-autodoc: no .jsx/.tsx files found\n"
            f"  conf_dir       = {conf_dir}\n"
            f"  js_source_path = {app.config.js_source_path!r}\n"
            f"  resolved       = {frontend_src}"
        )
        return

    verbose = app.verbosity > 0
    logger.info(
        f"react-autodoc: found {len(component_files)} source file(s) in {frontend_src}"
    )

    toc_entries: list[str] = []
    written = 0

    for fpath in component_files:
        components = _parse_components(fpath, frontend_src.parent, verbose=verbose)
        if not components:
            continue

        visible = [
            c
            for c in components
            if not _should_skip(
                c.get("displayName") or fpath.stem,
                (c.get("description") or "").strip(),
                opts,
            )
        ]
        if not visible:
            if verbose:
                logger.info(
                    f"react-autodoc: all components skipped in {fpath.name} "
                    f"(undoc-members={opts.get('undoc-members')}, "
                    f"private-members={opts.get('private-members')})"
                )
            continue

        # Flatten path separators to dots — mirrors Python module naming
        # e.g. components/Button.jsx -> components.Button.jsx
        rel = fpath.relative_to(frontend_src)
        doc_name = str(rel).replace("/", ".").replace("\\", ".")
        rst_path = out_dir / f"{doc_name}.rst"

        if _write_if_changed(
            rst_path, _rst_for_module(fpath, visible, frontend_src, opts)
        ):
            written += 1

        toc_entries.append(doc_name)

    # Index file — always write so toctree reference resolves even on first build
    index_content = "\n".join(
        [
            "React Components",
            "================",
            "",
            "Auto-generated from JSDoc comments in ``frontend/src``.",
            "Re-generated on every ``make html`` run.",
            "",
            ".. toctree::",
            "   :maxdepth: 1",
            "",
            *[f"   {e}" for e in toc_entries],
            "",
        ]
    )
    _write_if_changed(out_dir / "index.rst", index_content)

    logger.info(
        f"react-autodoc: {len(toc_entries)} component file(s) documented"
        + (f", {written} updated" if written else " (no changes)")
    )


# ---------------------------------------------------------------------------
# Sphinx extension entry point
# ---------------------------------------------------------------------------


def setup(app: Sphinx) -> dict:
    """Register the extension with Sphinx."""
    app.add_config_value("js_source_path", "../../frontend/src", "env")
    app.add_config_value("react_autodoc_output_dir", "_react_autodoc", "env")
    app.add_config_value("react_autodoc_default_options", {}, "env")

    app.connect("builder-inited", _generate_react_docs)

    return {
        "version": "1.0",
        "parallel_read_safe": False,
        "parallel_write_safe": True,
    }

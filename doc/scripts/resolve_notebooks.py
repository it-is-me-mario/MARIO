#!/usr/bin/env python
"""Execute documentation notebooks with local paths kept out of source cells.

The public notebooks keep generic placeholders such as ``/path/to/SUPPLY-USE``.
This script executes an in-memory copy where those placeholders are replaced by
paths from ``doc/notebook_paths.local.yaml``. Only outputs and execution counts
are copied back to the public notebook.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
import getpass
import json
import logging
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any

import nbformat
from nbclient import NotebookClient
import yaml

# run all with python doc/scripts/resolve_notebooks.py doc/source/notebooks/parsers/**/*.ipynb

DOC_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = DOC_ROOT.parent
DEFAULT_CONFIG = DOC_ROOT / "notebook_paths.local.yaml"
DEFAULT_LEAK_PATTERNS = ("/Users/", "/Volumes/")
UNSUPPORTED_NBSPHINX_MIME_TYPES = {"application/vnd.plotly.v1+json"}
OUTPUT_TEST_DIR = REPO_ROOT / "Output" / "path_test"
SUPPORTING_FILES_DIR = REPO_ROOT / "mario/test/supporting_files"
PACKAGED_EXCEL_WORKBOOKS = {
    "test_IOT_standard.xlsx": REPO_ROOT / "mario/test/tables/test_IOT_standard.xlsx",
    "test_IOT_special.xlsx": REPO_ROOT / "mario/test/tables/test_IOT_special.xlsx",
    "test_SUT_standard.xlsx": REPO_ROOT / "mario/test/tables/test_SUT_standard.xlsx",
    "test_SUT_special.xlsx": REPO_ROOT / "mario/test/tables/test_SUT_special.xlsx",
}
PACKAGED_USER_GUIDE_PATHS = {
    "source/user_guide/transformations/add_extensions.ipynb": {
        "/path/to/add_extensions_template.xlsx": OUTPUT_TEST_DIR / "add_extensions_template.xlsx",
        "/path/to/add_extensions_filled.xlsx": SUPPORTING_FILES_DIR / "add_extensions_filled.xlsx",
    },
    "source/user_guide/transformations/add_sectors.ipynb": {
        "/path/to/add_sector_template.xlsx": OUTPUT_TEST_DIR / "add_sector_template.xlsx",
        "/path/to/add_sector_master_filled.xlsx": SUPPORTING_FILES_DIR / "add_sector_iot_master_filled.xlsx",
        "/path/to/add_sector_inventories_filled.xlsx": SUPPORTING_FILES_DIR / "add_sector_iot_inventories_filled.xlsx",
        "/path/to/cvxlab": SUPPORTING_FILES_DIR / "cvxlab",
    },
    "source/user_guide/transformations/aggregate.ipynb": {
        "/path/to/aggregation_iot_template.xlsx": OUTPUT_TEST_DIR / "aggregation_iot_template.xlsx",
        "/path/to/aggregation_iot_filled.xlsx": SUPPORTING_FILES_DIR / "aggregation_iot_filled.xlsx",
    },
    "source/user_guide/transformations/apply_shocks.ipynb": {
        "/path/to/shock_IOT_template.xlsx": OUTPUT_TEST_DIR / "shock_IOT_template.xlsx",
        "/path/to/shock_IOT_filled.xlsx": SUPPORTING_FILES_DIR / "shock_IOT_filled.xlsx",
        "/path/to/shock_SUT_template.xlsx": OUTPUT_TEST_DIR / "shock_SUT_template.xlsx",
        "/path/to/shock_SUT_filled.xlsx": SUPPORTING_FILES_DIR / "shock_SUT_filled.xlsx",
        "/path/to/shock_IOT_template_clusters.xlsx": OUTPUT_TEST_DIR / "shock_IOT_template_clusters.xlsx",
        "/path/to/shock_IOT_filled_clusters.xlsx": SUPPORTING_FILES_DIR / "shock_IOT_filled_clusters.xlsx",
    },
    "source/user_guide/provide_your_database.ipynb": {
        "/path/to/custom_iot_template.xlsx": OUTPUT_TEST_DIR / "custom_iot_template.xlsx",
        "/path/to/custom_iot_filled.xlsx": SUPPORTING_FILES_DIR / "custom_iot_filled.xlsx",
        "/path/to/custom_sut_template.xlsx": OUTPUT_TEST_DIR / "custom_sut_template.xlsx",
        "/path/to/custom_sut_filled.xlsx": SUPPORTING_FILES_DIR / "custom_sut_filled.xlsx",
    },
    "source/user_guide/exporting/export_and_roundtrip.ipynb": {
        "/path/to/iot_export.xlsx": OUTPUT_TEST_DIR / "iot_export.xlsx",
        "/path/to/iot_export_csv": OUTPUT_TEST_DIR / "iot_export_csv",
        "/path/to/iot_export_parquet": OUTPUT_TEST_DIR / "iot_export_parquet",
    },
}

LOGGER = logging.getLogger("resolve_notebooks")

# Default run list used when no notebooks are passed on CLI.
# Comment out entries you do not want to execute in a given run.
DEFAULT_NOTEBOOKS_TO_RUN = [
    # Parsers
    "doc/source/notebooks/parsers/adb/walkthrough.ipynb",
    "doc/source/notebooks/parsers/bea/walkthrough.ipynb",
    "doc/source/notebooks/parsers/ceads/walkthrough.ipynb",
    # "doc/source/notebooks/parsers/cepalstat/walkthrough.ipynb",
    "doc/source/notebooks/parsers/custom_database/from_excel.ipynb",
    "doc/source/notebooks/parsers/custom_database/from_pymrio.ipynb",
    "doc/source/notebooks/parsers/custom_database/from_txt.ipynb",
    "doc/source/notebooks/parsers/emerging/walkthrough.ipynb",
    "doc/source/notebooks/parsers/eora/walkthrough.ipynb",
    "doc/source/notebooks/parsers/eurostat/walkthrough.ipynb",
    "doc/source/notebooks/parsers/exiobase/hybrid.ipynb",
    "doc/source/notebooks/parsers/exiobase/monetary.ipynb",
    "doc/source/notebooks/parsers/figaro/walkthrough.ipynb",
    "doc/source/notebooks/parsers/gloria/walkthrough.ipynb",
    # "doc/source/notebooks/parsers/gtap/tutorial.ipynb",
    # "doc/source/notebooks/parsers/gtap/walkthrough.ipynb",
    "doc/source/notebooks/parsers/istat/walkthrough.ipynb",
    "doc/source/notebooks/parsers/oecd/walkthrough.ipynb",
    "doc/source/notebooks/parsers/statcan/walkthrough.ipynb",
    "doc/source/notebooks/parsers/useeio/walkthrough.ipynb",
    "doc/source/notebooks/parsers/wiod/walkthrough.ipynb",
    # User guide transformations
    "doc/source/user_guide/transformations/add_extensions.ipynb",
    "doc/source/user_guide/transformations/add_sectors.ipynb",
    "doc/source/user_guide/transformations/aggregate.ipynb",
    "doc/source/user_guide/transformations/apply_shocks.ipynb",
    "doc/source/user_guide/transformations/mrio_to_srio.ipynb",
    "doc/source/user_guide/exporting/export_and_roundtrip.ipynb",
    "doc/source/user_guide/provide_your_database.ipynb",
    "doc/source/user_guide/transformations/sut_to_iot.ipynb",
    "doc/source/user_guide/transformations/to_chenery_moses.ipynb",
]

COMMENT_PLACEHOLDER_RE = re.compile(
    r"^(?P<indent>\s*)#\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
    r"(?P<quote>['\"])(?P<placeholder>/path/to/[^'\"]+)(?P=quote)\s*,?\s*$"
)
LOCAL_ASSIGN_RE = re.compile(
    r"^(?P<indent>\s*)(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
    r"(?P<quote>['\"])(?P<local>/(?:Users|Volumes)/[^'\"]+)(?P=quote)\s*,?\s*$"
)
LOCAL_LITERAL_RE = re.compile(r"(?P<quote>['\"])(?P<local>/(?:Users|Volumes)/[^'\"]+)(?P=quote)")


@dataclass(frozen=True)
class Replacement:
    placeholder: str
    local: str
    cells: tuple[int, ...] | None = None


def _configure_logging(level: str) -> None:
    level_name = str(level).upper()
    numeric_level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=numeric_level, format="%(levelname)s %(message)s")


def _active_config_user(config: dict[str, Any], requested_user: str | None) -> str:
    if requested_user:
        return requested_user
    env_user = os.environ.get("NOTEBOOK_PATHS_USER")
    if env_user:
        return env_user

    current_user = getpass.getuser()
    users = config.get("users", {}) or {}
    if isinstance(users, dict) and current_user in users:
        return current_user
    return current_user


def _user_section(config: dict[str, Any], active_user: str | None) -> dict[str, Any]:
    if not active_user:
        return {}
    users = config.get("users", {}) or {}
    if not isinstance(users, dict):
        raise ValueError("'users' should be a mapping.")
    user_cfg = users.get(active_user, {}) or {}
    if not isinstance(user_cfg, dict):
        raise ValueError(f"Config for user {active_user!r} should be a mapping.")
    return user_cfg


def _dataset_label(notebook: Path) -> str:
    parts = notebook.as_posix().split("/")
    if "parsers" in parts:
        idx = parts.index("parsers")
        if idx + 1 < len(parts):
            return f"parser:{parts[idx + 1]}"
    if "user_guide" in parts:
        idx = parts.index("user_guide")
        if idx + 1 < len(parts):
            return f"user_guide:{parts[idx + 1]}"
    return "dataset:unknown"


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r") as stream:
        data = yaml.safe_load(stream) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} should contain a YAML mapping.")
    return data


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as stream:
        yaml.safe_dump(data, stream, sort_keys=False, allow_unicode=False)


def _as_replacements(value: Any) -> list[Replacement]:
    if value is None:
        return []
    if isinstance(value, dict):
        items = [{"placeholder": key, "local": local} for key, local in value.items()]
    elif isinstance(value, list):
        items = value
    else:
        raise ValueError("replacements should be a list or mapping.")

    replacements: list[Replacement] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Each replacement should be a mapping.")
        placeholder = item.get("placeholder")
        local = item.get("local")
        if not placeholder or not local:
            raise ValueError("Each replacement needs 'placeholder' and 'local'.")
        cells = item.get("cells")
        if cells is None:
            cell_tuple = None
        elif isinstance(cells, int):
            cell_tuple = (cells,)
        else:
            cell_tuple = tuple(int(cell) for cell in cells)
        replacements.append(
            Replacement(
                placeholder=str(placeholder),
                local=str(local),
                cells=cell_tuple,
            )
        )
    return replacements


def _notebook_keys(path: Path) -> set[str]:
    resolved = path.resolve()
    keys = {str(path), path.as_posix(), str(resolved), resolved.as_posix()}
    for root in (DOC_ROOT, REPO_ROOT):
        try:
            rel = resolved.relative_to(root.resolve())
        except ValueError:
            continue
        keys.add(str(rel))
        keys.add(rel.as_posix())
    return keys


def _notebook_config(config: dict[str, Any], notebook: Path) -> dict[str, Any]:
    notebooks = config.get("notebooks", {}) or {}
    if not isinstance(notebooks, dict):
        raise ValueError("'notebooks' should be a mapping.")
    keys = _notebook_keys(notebook)
    for key, value in notebooks.items():
        if str(key) in keys or Path(str(key)).as_posix() in keys:
            if value is None:
                return {}
            if isinstance(value, list):
                return {"replacements": value}
            if not isinstance(value, dict):
                raise ValueError(f"Config for notebook {key!r} should be a mapping.")
            return value
    return {}


def _replacements_for(
    config: dict[str, Any],
    notebook: Path,
    *,
    active_user: str | None,
) -> list[Replacement]:
    notebook_cfg = _notebook_config(config, notebook)
    user_cfg = _user_section(config, active_user)
    notebook_user_cfg = _notebook_config(user_cfg, notebook)
    return (
        _default_replacements_for(notebook)
        + _as_replacements(config.get("replacements"))
        + _as_replacements(user_cfg.get("replacements"))
        + _as_replacements(notebook_cfg.get("replacements"))
        + _as_replacements(notebook_user_cfg.get("replacements"))
    )


def _default_replacements_for(notebook: Path) -> list[Replacement]:
    """Return built-in repo-local replacements for packaged docs fixtures."""
    keys = _notebook_keys(notebook)
    replacements: list[Replacement] = []

    if "source/notebooks/parsers/custom_database/from_excel.ipynb" in keys:
        for filename, local_path in PACKAGED_EXCEL_WORKBOOKS.items():
            if not local_path.exists():
                continue
            local = str(local_path)
            replacements.extend(
                [
                    Replacement(f"/path/to/{filename}", local),
                    Replacement(f"../{filename}", local),
                    Replacement(f"../../../../../mario/test/tables/{filename}", local),
                ]
            )

    for notebook_key, placeholder_map in PACKAGED_USER_GUIDE_PATHS.items():
        if notebook_key not in keys:
            continue
        for placeholder, local_path in placeholder_map.items():
            replacements.append(Replacement(placeholder, str(local_path)))

    return replacements


def _skip_cells_for(
    config: dict[str, Any],
    notebook: Path,
    *,
    active_user: str | None,
) -> set[int]:
    notebook_cfg = _notebook_config(config, notebook)
    user_cfg = _user_section(config, active_user)
    notebook_user_cfg = _notebook_config(user_cfg, notebook)

    skip_cells: set[int] = set()
    for value in (notebook_cfg.get("skip_cells", []) or [], notebook_user_cfg.get("skip_cells", []) or []):
        if isinstance(value, int):
            skip_cells.add(value)
        else:
            skip_cells.update(int(cell) for cell in value)
    return skip_cells


def _resolve_notebook_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    for base in (Path.cwd(), DOC_ROOT, REPO_ROOT):
        candidate = (base / path).resolve()
        if candidate.exists():
            return candidate
    return (Path.cwd() / path).resolve()


def _source_as_text(cell: Any) -> str:
    source = cell.get("source", "")
    if isinstance(source, list):
        return "".join(source)
    return str(source)


def _set_source(cell: Any, source: str) -> None:
    cell["source"] = source


def _apply_replacements(nb: Any, replacements: list[Replacement]) -> None:
    for replacement in replacements:
        target_cells = set(replacement.cells) if replacement.cells is not None else None
        for index, cell in enumerate(nb.cells):
            if cell.get("cell_type") != "code":
                continue
            if target_cells is not None and index not in target_cells:
                continue
            source = _source_as_text(cell)
            source = source.replace(replacement.placeholder, replacement.local)
            _set_source(cell, source)


def _placeholder_hits(nb: Any, *, skip_cells: set[int]) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    for index, cell in enumerate(nb.cells):
        if cell.get("cell_type") != "code":
            continue
        if index in skip_cells:
            continue
        for line in _source_as_text(cell).splitlines():
            if "/path/to/" in line:
                hits.append((index, line.strip()))
    return hits


def _prepare_execution_copy(
    original: Any,
    replacements: list[Replacement],
    skip_cells: set[int],
    *,
    allow_placeholder_paths: bool,
) -> Any:
    nb = deepcopy(original)
    _apply_replacements(nb, replacements)
    hits = _placeholder_hits(nb, skip_cells=skip_cells)
    if hits and not allow_placeholder_paths:
        details = "\n".join(f"cell {cell}: {line}" for cell, line in hits[:20])
        raise RuntimeError(
            "Unresolved /path/to/ placeholders remain after applying local replacements:\n"
            f"{details}"
        )

    for index, cell in enumerate(nb.cells):
        if cell.get("cell_type") != "code":
            continue
        cell["outputs"] = []
        cell["execution_count"] = None
        if index in skip_cells:
            tags = list(cell.setdefault("metadata", {}).get("tags", []))
            if "skip-execution" not in tags:
                tags.append("skip-execution")
            cell["metadata"]["tags"] = tags
    return nb


def _output_text(output: Any) -> str:
    payload = output if isinstance(output, dict) else dict(output)
    return json.dumps(payload, default=str, ensure_ascii=True)


def _check_private_output_paths(
    nb: Any,
    notebook: Path,
    *,
    skip_cells: set[int],
    leak_patterns: tuple[str, ...],
) -> None:
    leaks: list[str] = []
    for index, cell in enumerate(nb.cells):
        if cell.get("cell_type") != "code" or index in skip_cells:
            continue
        for output in cell.get("outputs", []):
            text = _output_text(output)
            for pattern in leak_patterns:
                if pattern in text:
                    leaks.append(f"{notebook}: cell {index} output contains {pattern!r}")
                    break
    if leaks:
        detail = "\n".join(leaks[:20])
        raise RuntimeError(f"Private local paths found in executed outputs:\n{detail}")


def _replace_text_paths(text: str, replacements: list[Replacement]) -> str:
    for replacement in sorted(replacements, key=lambda item: len(item.local), reverse=True):
        text = text.replace(replacement.local, replacement.placeholder)
    return text


def _replace_paths_in_value(value: Any, replacements: list[Replacement]) -> Any:
    if isinstance(value, str):
        return _replace_text_paths(value, replacements)
    if isinstance(value, list):
        for index, item in enumerate(value):
            value[index] = _replace_paths_in_value(item, replacements)
        return value
    if isinstance(value, tuple):
        return tuple(_replace_paths_in_value(item, replacements) for item in value)
    if isinstance(value, dict):
        for key, item in list(value.items()):
            value[key] = _replace_paths_in_value(item, replacements)
        return value
    return value


def _sanitize_output_paths(nb: Any, replacements: list[Replacement]) -> int:
    changed = 0
    for cell in nb.cells:
        if cell.get("cell_type") != "code":
            continue
        outputs = cell.get("outputs", [])
        before = json.dumps(outputs, default=str, ensure_ascii=True)
        _replace_paths_in_value(outputs, replacements)
        after = json.dumps(outputs, default=str, ensure_ascii=True)
        if after != before:
            changed += 1
    return changed


def _strip_unsupported_output_mimes(nb: Any) -> int:
    stripped = 0
    for cell in nb.cells:
        if cell.get("cell_type") != "code":
            continue

        sanitized_outputs = []
        for output in cell.get("outputs", []):
            payload = output if isinstance(output, dict) else dict(output)
            data = payload.get("data")
            if not isinstance(data, dict):
                sanitized_outputs.append(output)
                continue

            kept_data = {
                mime: value
                for mime, value in data.items()
                if mime not in UNSUPPORTED_NBSPHINX_MIME_TYPES
            }
            removed = len(data) - len(kept_data)
            if removed:
                stripped += removed
            if not kept_data:
                continue

            payload["data"] = kept_data
            sanitized_outputs.append(payload)

        cell["outputs"] = sanitized_outputs

    return stripped


def _copy_outputs(original: Any, executed: Any, *, skip_cells: set[int]) -> int:
    copied = 0
    for index, (source_cell, executed_cell) in enumerate(zip(original.cells, executed.cells)):
        if source_cell.get("cell_type") != "code" or index in skip_cells:
            continue
        source_cell["outputs"] = executed_cell.get("outputs", [])
        source_cell["execution_count"] = executed_cell.get("execution_count")
        copied += 1
    return copied


def _execute_one(
    notebook: Path,
    config: dict[str, Any],
    *,
    active_user: str | None,
    timeout: int,
    kernel_name: str | None,
    allow_placeholder_paths: bool,
    fail_on_private_output: bool,
    leak_patterns: tuple[str, ...],
    dry_run: bool,
) -> None:
    original = nbformat.read(notebook, as_version=4)
    replacements = _replacements_for(config, notebook, active_user=active_user)
    skip_cells = _skip_cells_for(config, notebook, active_user=active_user)
    LOGGER.info(
        "Running %s (%s): replacements=%d skip_cells=%d user=%s",
        notebook,
        _dataset_label(notebook),
        len(replacements),
        len(skip_cells),
        active_user or "<none>",
    )
    execution_nb = _prepare_execution_copy(
        original,
        replacements,
        skip_cells,
        allow_placeholder_paths=allow_placeholder_paths,
    )
    if dry_run:
        LOGGER.info(
            "Dry-run %s: replacements=%d skipped_cells=%d",
            notebook,
            len(replacements),
            len(skip_cells),
        )
        return

    os.environ["PYTHONPATH"] = (
        f"{REPO_ROOT}{os.pathsep}{os.environ['PYTHONPATH']}"
        if os.environ.get("PYTHONPATH")
        else str(REPO_ROOT)
    )
    resources = {"metadata": {"path": str(notebook.parent)}}
    with tempfile.TemporaryDirectory(prefix="mario-notebook-") as tempdir:
        temp_path = Path(tempdir) / notebook.name
        nbformat.write(execution_nb, temp_path)
        execution_nb = nbformat.read(temp_path, as_version=4)
        client_kwargs = {
            "timeout": timeout,
            "skip_cells_with_tag": "skip-execution",
            "allow_errors": False,
        }
        if kernel_name is not None:
            client_kwargs["kernel_name"] = kernel_name
        client = NotebookClient(execution_nb, **client_kwargs)
        client.resources = resources
        client.execute()

    # Always sanitize the repo root from outputs (covers editable installs where
    # mario.__file__ resolves inside the working tree under /Users/ or /home/).
    builtin_replacements = [Replacement(placeholder="/path/to/MARIO", local=str(REPO_ROOT))]
    _sanitize_output_paths(execution_nb, builtin_replacements + replacements)
    stripped_mimes = _strip_unsupported_output_mimes(execution_nb)
    if fail_on_private_output:
        _check_private_output_paths(
            execution_nb,
            notebook,
            skip_cells=skip_cells,
            leak_patterns=leak_patterns,
        )
    copied = _copy_outputs(original, execution_nb, skip_cells=skip_cells)
    nbformat.write(original, notebook)
    LOGGER.info(
        "Completed %s: copied outputs from %d executed code cells, stripped %d unsupported MIME payloads",
        notebook,
        copied,
        stripped_mimes,
    )


def _relative_notebook_key(notebook: Path) -> str:
    try:
        return notebook.resolve().relative_to(DOC_ROOT.resolve()).as_posix()
    except ValueError:
        return notebook.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def _placeholder_for_local_path(local: str) -> str:
    path = Path(local)
    name = path.name or path.parent.name
    return f"/path/to/{name}"


def _replacement_exists(items: list[dict[str, Any]], item: dict[str, Any]) -> bool:
    return any(
        existing.get("placeholder") == item.get("placeholder")
        and existing.get("local") == item.get("local")
        and existing.get("cells") == item.get("cells")
        for existing in items
    )


def _sanitize_source(source: str, cell_index: int) -> tuple[str, list[dict[str, Any]]]:
    lines = source.splitlines(keepends=True)
    new_lines: list[str] = []
    replacements: list[dict[str, Any]] = []
    pending_comment: dict[str, str] | None = None

    for line in lines:
        newline = "\n" if line.endswith("\n") else ""
        body = line[:-1] if newline else line
        comment_match = COMMENT_PLACEHOLDER_RE.match(body)
        if comment_match is not None:
            pending_comment = {
                "name": comment_match.group("name"),
                "placeholder": comment_match.group("placeholder"),
            }
            continue

        assign_match = LOCAL_ASSIGN_RE.match(body)
        if assign_match is not None:
            name = assign_match.group("name")
            local = assign_match.group("local")
            if pending_comment and pending_comment["name"] == name:
                placeholder = pending_comment["placeholder"]
            else:
                placeholder = _placeholder_for_local_path(local)
            new_lines.append(f'{assign_match.group("indent")}{name}="{placeholder}",{newline}')
            replacements.append(
                {"placeholder": placeholder, "local": local, "cells": [cell_index]}
            )
            pending_comment = None
            continue

        if pending_comment is not None:
            new_lines.append(
                f'{body[: len(body) - len(body.lstrip())]}'
                f'# {pending_comment["name"]}="{pending_comment["placeholder"]}",{newline}'
            )
            pending_comment = None

        def replace_literal(match: re.Match[str]) -> str:
            local = match.group("local")
            placeholder = _placeholder_for_local_path(local)
            replacements.append(
                {"placeholder": placeholder, "local": local, "cells": [cell_index]}
            )
            return f'{match.group("quote")}{placeholder}{match.group("quote")}'

        new_lines.append(LOCAL_LITERAL_RE.sub(replace_literal, body) + newline)

    if pending_comment is not None:
        new_lines.append(f'# {pending_comment["name"]}="{pending_comment["placeholder"]}",')

    return "".join(new_lines), replacements


def _sanitize_notebook_paths(
    notebooks: list[Path],
    config_path: Path,
    *,
    active_user: str,
) -> None:
    config = _load_yaml(config_path)
    users_cfg = config.setdefault("users", {})
    if not isinstance(users_cfg, dict):
        raise ValueError("'users' should be a mapping.")
    user_cfg = users_cfg.setdefault(active_user, {})
    if not isinstance(user_cfg, dict):
        raise ValueError(f"Config for user {active_user!r} should be a mapping.")
    notebooks_cfg = user_cfg.setdefault("notebooks", {})
    if not isinstance(notebooks_cfg, dict):
        raise ValueError("'users.<name>.notebooks' should be a mapping.")

    for notebook in notebooks:
        nb = nbformat.read(notebook, as_version=4)
        notebook_key = _relative_notebook_key(notebook)
        notebook_cfg = notebooks_cfg.setdefault(notebook_key, {})
        if not isinstance(notebook_cfg, dict):
            raise ValueError(f"Config for {notebook_key} should be a mapping.")
        items = notebook_cfg.setdefault("replacements", [])
        if not isinstance(items, list):
            raise ValueError(f"Config replacements for {notebook_key} should be a list.")

        changed = False
        added = 0
        for index, cell in enumerate(nb.cells):
            if cell.get("cell_type") != "code":
                continue
            source = _source_as_text(cell)
            new_source, replacements = _sanitize_source(source, index)
            if new_source != source:
                _set_source(cell, new_source)
                changed = True
            for replacement in replacements:
                if not _replacement_exists(items, replacement):
                    items.append(replacement)
                    added += 1

        replacements_for_notebook = _as_replacements(items)
        output_cells_changed = _sanitize_output_paths(nb, replacements_for_notebook)
        if changed or output_cells_changed:
            nbformat.write(nb, notebook)
        LOGGER.info(
            "Sanitized %s: source_changed=%s output_cells_sanitized=%d added_replacements=%d user=%s",
            notebook,
            changed,
            output_cells_changed,
            added,
            active_user,
        )

    _write_yaml(config_path, config)
    LOGGER.info("Wrote %s", config_path)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "notebooks",
        nargs="*",
        help=(
            "Notebook files to resolve. Paths may be relative to repo root or doc/. "
            "If omitted, DEFAULT_NOTEBOOKS_TO_RUN is used."
        ),
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help=f"Local path config. Default: {DEFAULT_CONFIG}",
    )
    parser.add_argument(
        "--config-user",
        default=None,
        help=(
            "User profile under users.<name> in config. Defaults to "
            "NOTEBOOK_PATHS_USER env var or current OS username."
        ),
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity.",
    )
    parser.add_argument("--timeout", type=int, default=1200)
    parser.add_argument("--kernel-name", default=None)
    parser.add_argument(
        "--allow-placeholder-paths",
        action="store_true",
        help="Execute even if /path/to/ placeholders remain after replacement.",
    )
    parser.add_argument(
        "--allow-private-output",
        action="store_true",
        help="Do not fail when outputs contain /Users/ or /Volumes/.",
    )
    parser.add_argument(
        "--leak-pattern",
        action="append",
        default=[],
        help="Additional private path pattern to reject in outputs.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config and print planned work without executing notebooks.",
    )
    parser.add_argument(
        "--sanitize-local-paths",
        action="store_true",
        help=(
            "Move local /Users or /Volumes path literals from notebook sources into "
            "the local config, replacing them with /path/to placeholders."
        ),
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Log failures and continue instead of stopping at the first failing notebook.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.log_level)
    config_path = _resolve_notebook_path(args.config)
    config = _load_yaml(config_path)
    active_user = _active_config_user(config, args.config_user)

    notebook_args = args.notebooks or DEFAULT_NOTEBOOKS_TO_RUN
    if not args.notebooks:
        LOGGER.info(
            "No notebook arguments provided; using DEFAULT_NOTEBOOKS_TO_RUN "
            f"({len(DEFAULT_NOTEBOOKS_TO_RUN)} notebooks)."
        )
    notebooks = [_resolve_notebook_path(value) for value in notebook_args]

    missing = [path for path in notebooks if not path.exists()]
    if missing:
        for path in missing:
            LOGGER.error("Notebook not found: %s", path)
        return 2

    if args.sanitize_local_paths:
        _sanitize_notebook_paths(notebooks, config_path, active_user=active_user)
        return 0

    LOGGER.info("Using config user profile: %s", active_user)
    leak_patterns = tuple(DEFAULT_LEAK_PATTERNS + tuple(args.leak_pattern))
    total = len(notebooks)
    failures: list[tuple[Path, Exception]] = []
    for index, notebook in enumerate(notebooks, start=1):
        LOGGER.info("[%d/%d] %s (%s)", index, total, notebook, _dataset_label(notebook))
        try:
            _execute_one(
                notebook,
                config,
                active_user=active_user,
                timeout=args.timeout,
                kernel_name=args.kernel_name,
                allow_placeholder_paths=args.allow_placeholder_paths,
                fail_on_private_output=not args.allow_private_output,
                leak_patterns=leak_patterns,
                dry_run=args.dry_run,
            )
        except Exception as exc:
            if args.continue_on_error:
                LOGGER.error("FAILED %s: %s", notebook, exc)
                failures.append((notebook, exc))
            else:
                raise
    if failures:
        LOGGER.error("%d notebook(s) failed:", len(failures))
        for nb, exc in failures:
            LOGGER.error("  %s: %s", nb, exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

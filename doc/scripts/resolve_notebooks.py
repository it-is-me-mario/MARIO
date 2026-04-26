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
import json
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
PACKAGED_EXCEL_WORKBOOKS = {
    "test_IOT_standard.xlsx": REPO_ROOT / "mario/test/new/test_IOT_standard.xlsx",
    "test_IOT_special.xlsx": REPO_ROOT / "mario/test/new/test_IOT_special.xlsx",
    "test_SUT_standard.xlsx": REPO_ROOT / "mario/test/new/test_SUT_standard.xlsx",
    "test_SUT_special.xlsx": REPO_ROOT / "mario/test/new/test_SUT_special.xlsx",
}

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


def _replacements_for(config: dict[str, Any], notebook: Path) -> list[Replacement]:
    notebook_cfg = _notebook_config(config, notebook)
    return (
        _default_replacements_for(notebook)
        + _as_replacements(config.get("replacements"))
        + _as_replacements(notebook_cfg.get("replacements"))
    )


def _default_replacements_for(notebook: Path) -> list[Replacement]:
    """Return built-in repo-local replacements for packaged docs fixtures."""
    keys = _notebook_keys(notebook)
    if "source/notebooks/parsers/custom_database/from_excel.ipynb" not in keys:
        return []

    replacements: list[Replacement] = []
    for filename, local_path in PACKAGED_EXCEL_WORKBOOKS.items():
        if not local_path.exists():
            continue
        local = str(local_path)
        replacements.extend(
            [
                Replacement(f"/path/to/{filename}", local),
                Replacement(f"../{filename}", local),
                Replacement(f"../../../../../mario/test/new/{filename}", local),
            ]
        )
    return replacements


def _skip_cells_for(config: dict[str, Any], notebook: Path) -> set[int]:
    notebook_cfg = _notebook_config(config, notebook)
    skip_cells = notebook_cfg.get("skip_cells", []) or []
    if isinstance(skip_cells, int):
        return {skip_cells}
    return {int(cell) for cell in skip_cells}


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
    timeout: int,
    kernel_name: str | None,
    allow_placeholder_paths: bool,
    fail_on_private_output: bool,
    leak_patterns: tuple[str, ...],
    dry_run: bool,
) -> None:
    original = nbformat.read(notebook, as_version=4)
    replacements = _replacements_for(config, notebook)
    skip_cells = _skip_cells_for(config, notebook)
    execution_nb = _prepare_execution_copy(
        original,
        replacements,
        skip_cells,
        allow_placeholder_paths=allow_placeholder_paths,
    )
    if dry_run:
        print(
            f"{notebook}: {len(replacements)} replacements, "
            f"{len(skip_cells)} skipped cells"
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

    _sanitize_output_paths(execution_nb, replacements)
    if fail_on_private_output:
        _check_private_output_paths(
            execution_nb,
            notebook,
            skip_cells=skip_cells,
            leak_patterns=leak_patterns,
        )
    copied = _copy_outputs(original, execution_nb, skip_cells=skip_cells)
    nbformat.write(original, notebook)
    print(f"{notebook}: copied outputs from {copied} executed code cells")


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


def _sanitize_notebook_paths(notebooks: list[Path], config_path: Path) -> None:
    config = _load_yaml(config_path)
    notebooks_cfg = config.setdefault("notebooks", {})
    if not isinstance(notebooks_cfg, dict):
        raise ValueError("'notebooks' should be a mapping.")

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
        print(
            f"{notebook}: sanitized={changed}, "
            f"output_cells_sanitized={output_cells_changed}, "
            f"added_replacements={added}"
        )

    _write_yaml(config_path, config)
    print(f"Wrote {config_path}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "notebooks",
        nargs="+",
        help="Notebook files to resolve. Paths may be relative to repo root or doc/.",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help=f"Local path config. Default: {DEFAULT_CONFIG}",
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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    config_path = _resolve_notebook_path(args.config)
    notebooks = [_resolve_notebook_path(value) for value in args.notebooks]

    missing = [path for path in notebooks if not path.exists()]
    if missing:
        for path in missing:
            print(f"Notebook not found: {path}", file=sys.stderr)
        return 2

    if args.sanitize_local_paths:
        _sanitize_notebook_paths(notebooks, config_path)
        return 0

    config = _load_yaml(config_path)
    leak_patterns = tuple(DEFAULT_LEAK_PATTERNS + tuple(args.leak_pattern))
    for notebook in notebooks:
        _execute_one(
            notebook,
            config,
            timeout=args.timeout,
            kernel_name=args.kernel_name,
            allow_placeholder_paths=args.allow_placeholder_paths,
            fail_on_private_output=not args.allow_private_output,
            leak_patterns=leak_patterns,
            dry_run=args.dry_run,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

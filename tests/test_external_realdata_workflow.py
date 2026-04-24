import os
import re
from pathlib import Path

import pytest
import yaml

import mario


DEFAULT_ENV_FILE = Path(__file__).with_name("realdata.local.env")
ENV_FILE_KEYS = {
    "MARIO_REALDATA_ROOT",
    "MARIO_REALDATA_CONFIG",
    "MARIO_REALDATA_FILTER",
    "MARIO_REALDATA_RUN_AGGREGATE",
}


def _load_realdata_env_file() -> None:
    """Load optional local test settings without overriding shell env vars."""
    env_file = Path(os.environ.get("MARIO_REALDATA_ENV", DEFAULT_ENV_FILE)).expanduser()
    if not env_file.exists():
        return

    for raw_line in env_file.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in ENV_FILE_KEYS:
            continue
        os.environ.setdefault(key, value.strip().strip("\"'"))


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _resolve_realdata_locations() -> tuple[Path, Path] | None:
    config_env = os.environ.get("MARIO_REALDATA_CONFIG")
    root_env = os.environ.get("MARIO_REALDATA_ROOT")

    config_path = Path(config_env).expanduser() if config_env else None
    root_path = Path(root_env).expanduser() if root_env else None

    if config_path is None and root_path is None:
        return None
    if config_path is None:
        config_path = root_path / "config.yaml"
    if root_path is None:
        root_path = config_path.parent

    if not config_path.exists():
        return None
    return root_path.resolve(), config_path.resolve()


def _discover_cases() -> tuple[list[dict[str, object]], bool]:
    resolved = _resolve_realdata_locations()
    if resolved is None:
        return [], False

    root_path, config_path = resolved
    filter_pattern = os.environ.get("MARIO_REALDATA_FILTER")
    filter_regex = re.compile(filter_pattern) if filter_pattern else None
    aggregate_enabled = _truthy(os.environ.get("MARIO_REALDATA_RUN_AGGREGATE"))

    raw = yaml.safe_load(config_path.read_text())
    cases: list[dict[str, object]] = []

    for database_name, families in raw.items():
        for family_name, cfg in families.items():
            base_path = root_path / cfg["base_path"]
            parser_args = dict(cfg.get("parser_args", {}))
            operations = dict(cfg.get("operations", {}))

            discovered: list[tuple[Path, dict[str, object]]] = []
            if "instances" in cfg:
                for entry in cfg["instances"]:
                    entry = dict(entry)
                    rel_path = entry.pop("path", None)
                    instance_path = base_path / rel_path if rel_path else base_path
                    discovered.append((instance_path, entry))
            elif "glob" in cfg:
                patterns = [pattern.strip() for pattern in cfg["glob"].split(",")]
                regex = re.compile(cfg["path_extract"]) if cfg.get("path_extract") else None
                matched: set[Path] = set()
                for pattern in patterns:
                    matched.update(base_path.glob(pattern))
                for match_path in sorted(matched):
                    if cfg.get("discover") == "file" and not match_path.is_file():
                        continue
                    if cfg.get("discover") == "directory" and not match_path.is_dir():
                        continue
                    if match_path.name.startswith(".") or match_path.name.startswith("._"):
                        continue
                    metadata: dict[str, object] = {}
                    if regex is not None:
                        relative = str(match_path.relative_to(base_path))
                        match = regex.search(relative)
                        if match is not None:
                            for key, value in match.groupdict().items():
                                metadata[key] = int(value) if isinstance(value, str) and value.isdigit() else value
                    discovered.append((match_path, metadata))
            else:
                discovered.append((base_path, {}))

            for path, metadata in discovered:
                kwargs = {**parser_args, **metadata, "path": str(path), "calc_all": False}
                for key, value in list(kwargs.items()):
                    if isinstance(value, str) and value.startswith("database/"):
                        kwargs[key] = str(root_path / value)
                identifier_parts = [database_name, family_name]
                identifier_parts.extend(f"{key}={value}" for key, value in sorted(metadata.items()))
                identifier = "/".join(identifier_parts)
                if filter_regex is not None and filter_regex.search(identifier) is None:
                    continue
                aggregate_path = operations.get("aggregate")
                cases.append(
                    {
                        "id": identifier,
                        "parser": cfg["parser"],
                        "kwargs": kwargs,
                        "aggregate": None if aggregate_path is None else root_path / aggregate_path,
                    }
                )

    return cases, aggregate_enabled


_load_realdata_env_file()
REALDATA_CASES, REALDATA_AGGREGATE = _discover_cases()


@pytest.mark.skipif(
    _resolve_realdata_locations() is None,
    reason="Set MARIO_REALDATA_ROOT or MARIO_REALDATA_CONFIG to run external real-data workflow tests.",
)
@pytest.mark.parametrize("case", REALDATA_CASES, ids=[str(case["id"]) for case in REALDATA_CASES])
def test_external_realdata_parsers(case):
    parser = getattr(mario, str(case["parser"]))
    database = parser(**dict(case["kwargs"]))
    assert database is not None
    assert set(database["baseline"])


@pytest.mark.skipif(
    _resolve_realdata_locations() is None or not REALDATA_AGGREGATE,
    reason="Set MARIO_REALDATA_RUN_AGGREGATE=1 together with MARIO_REALDATA_ROOT/CONFIG to run aggregation workflow tests.",
)
@pytest.mark.parametrize(
    "case",
    [case for case in REALDATA_CASES if case["aggregate"] is not None],
    ids=[str(case["id"]) for case in REALDATA_CASES if case["aggregate"] is not None],
)
def test_external_realdata_aggregation_workflows(case):
    parser = getattr(mario, str(case["parser"]))
    database = parser(**dict(case["kwargs"]))
    aggregated = database.aggregate(
        io=str(case["aggregate"]),
        drop="missing",
        inplace=False,
        calc_all=False,
    )
    assert aggregated is not None

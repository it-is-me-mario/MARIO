"""Exercise regional indexes and compare methods with the previous getter.

Run from the source checkout with ``PYTHONPATH=. python scripts/diagnose_bonsai_methods.py
--path /path/to/20260615.zip --output /tmp/bonsai-methods.json``. Large inverse
matrices, dense exports and plots are exercised only on a small balanced bundle
with unequal regional classifications. Full-size probes use sparse blocks.
This diagnoses API/structural compatibility, not economic validity of results.
"""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import gc
import json
from pathlib import Path
import platform
import signal
import tempfile
import time
import traceback
from types import MethodType
import warnings

import numpy as np
import pandas as pd

import mario
from mario.model.conventions import TABLE_LEVELS, _MASTER_INDEX as MI


class IncorrectResult(AssertionError):
    """A method ran but lost the regional membership semantics."""


def _legacy_get_index(self, index, level="main", *, flat=False):
    """Replay the getter before regional views, without changing source files."""
    # flat=True is a no-op: this historical view always exposes global lists.
    if isinstance(index, str) and index.lower() == "all":
        return {
            key: self._indeces[code].get(level)
            for key, code in TABLE_LEVELS[self.table_type].items()
        }
    index = self._resolve_set_name(index)
    return deepcopy(self._indeces[TABLE_LEVELS[self.table_type][index]][level])


def _small_bundle(root):
    """Write balanced product flows; all three regional sets differ."""
    root.mkdir()
    nodes = [
        ("a1", "A1", "AT", "process", {}),
        ("a2", "A2", "AT", "process", {}),
        ("a3", "A3", "DE", "process", {}),
        ("c1", "C1", "AT", "object", {"object_type": "product"}),
        ("c2", "C2", "DE", "object", {"object_type": "product"}),
        ("c3", "C3", "DE", "object", {"object_type": "product"}),
        ("n1", "HH", "AT", "process", {"activity_type": "final_demand"}),
        ("n2", "HH", "DE", "process", {"activity_type": "final_demand"}),
        ("n3", "GOV", "DE", "process", {"activity_type": "final_demand"}),
    ]
    frame = pd.DataFrame(nodes, columns=["id", "name", "location", "type", "property"])
    frame["property"] = frame["property"].map(repr)
    frame["time"] = 2016
    frame.to_csv(root / "classification.csv", index=False)
    for kind, rows in (
        (
            "supply",
            [("a1", "c1", 10), ("a2", "c1", 5), ("a3", "c2", 10), ("a3", "c3", 5)],
        ),
        (
            "use",
            [
                ("c1", "a3", 3),
                ("c2", "a1", 2),
                ("c3", "a2", 1),
                ("c1", "n1", 12),
                ("c2", "n2", 8),
                ("c3", "n2", 4),
            ],
        ),
    ):
        frame = pd.DataFrame(rows, columns=["from_node", "to_node", "value"])
        frame["unit"] = "tonnes"
        frame.to_csv(root / f"hybrid_{kind}_w_characteristic_unit.csv", index=False)
    pd.DataFrame(
        [
            ("co2", "AT", "A1", "Air", "tonnes", 1.0, "Carbon dioxide"),
            ("co2", "DE", "A3", "Air", "tonnes", 2.0, "Carbon dioxide"),
            ("co2", "DE", "HH", "Air", "tonnes", 0.5, "Carbon dioxide"),
        ],
        columns=[
            "Exio substance",
            "Exio country code",
            "Exio act code",
            "Exio compartment",
            "unit",
            "Value",
            "substance_name",
        ],
    ).to_csv(root / "all_elementary_flows_AB_and_BB.csv", index=False)
    return root


def _first(database, code):
    return database._indeces[code]["main"][0]


def _summary(value):
    if isinstance(value, pd.DataFrame):
        return {"shape": list(value.shape)}
    if hasattr(value, "matrices"):
        return {"type": "Database", "regions": len(value._indeces["r"]["main"])}
    if isinstance(value, dict):
        if "membership_and_values_preserved" in value:
            return value
        return {"type": "dict", "keys": len(value)}
    if isinstance(value, (list, tuple)):
        return {"type": type(value).__name__, "length": len(value)}
    return str(value)[:400]


def _template(database, root):
    target = root / "aggregation.xlsx"
    database.get_aggregation_excel(path=str(target))
    labels = pd.read_excel(target, sheet_name=MI["a"], index_col=0).index
    if _first(database, "a") not in labels:
        raise IncorrectResult(
            "Activity sheet contains region keys instead of activity codes."
        )
    return len(labels)


def _search(database, root):
    code = _first(database, "a")
    result = database.search(MI["a"], code)
    lists = result.values() if isinstance(result, dict) else [result]
    if not any(code in labels for labels in lists):
        raise IncorrectResult(f"search does not find an existing activity: {code}.")
    return result


def _clusters(database, root):
    members = database.default_clusters[MI["a"]]["all"]
    if members != database.get_index(MI["a"]):
        raise IncorrectResult(
            "The Activity 'all' cluster does not preserve its regional membership."
        )
    return (
        sum(map(len, members.values())) if isinstance(members, dict) else len(members)
    )


def _identity_aggregation(database, root):
    values = database._indeces["a"]["main"]
    return database.aggregate(
        io={MI["a"]: pd.DataFrame({"Aggregation": values}, index=values)},
        levels=MI["a"],
        inplace=False,
        calc_all=False,
    )


def _world_aggregation(database, root):
    result = database.aggregate(
        io=None,
        region_aggregation={r: "WORLD" for r in database._indeces["r"]["main"]},
        levels=MI["r"],
        inplace=False,
        calc_all=False,
    )
    if len(result._indeces["r"]["main"]) != 1:
        raise IncorrectResult("Region aggregation did not produce one region.")
    for name in ("S", "U", "Yc", "Ea", "EY"):
        source = database.matrices["baseline"][name].sum().sum()
        target = result.matrices["baseline"][name].sum().sum()
        np.testing.assert_allclose(target, source, rtol=1e-12, atol=1e-7)
    return result


def _roundtrip(database, root, kind):
    target = root / kind
    if kind == "excel":
        database.to_excel(path=str(target.with_suffix(".xlsx")))
        parsed = mario.parse_from_excel(
            path=str(target.with_suffix(".xlsx")),
            table="SUT",
            mode="flows",
            calc_all=False,
        )
    elif kind == "parquet":
        database.to_parquet(path=str(target), flat=False)
        parsed = mario.parse_from_parquet(
            path=str(target / "flows"), table="SUT", mode="flows", calc_all=False
        )
    else:
        database.to_txt(path=str(target), flat=False, _format="csv")
        parsed = mario.parse_from_txt(
            path=str(target / "flows"), table="SUT", mode="flows", calc_all=False
        )
    layout_changes = []
    for name in ("S", "U", "Ya", "Yc", "Ea", "EY"):
        source, restored = (
            database.matrices["baseline"][name],
            parsed.matrices["baseline"][name],
        )
        source, restored = source.copy(), restored.copy()
        for side in ("index", "columns"):
            original, imported = getattr(source, side), getattr(restored, side)
            if not original.equals(imported):
                layout_changes.append(f"{name}.{side}")
            for frame in (source, restored):
                axis = getattr(frame, side)
                if isinstance(axis, pd.MultiIndex) and axis.nlevels == 3:
                    setattr(
                        frame,
                        side,
                        pd.MultiIndex.from_arrays(
                            [axis.get_level_values(0), axis.get_level_values(2)]
                        ),
                    )
            if set(getattr(source, side)) != set(getattr(restored, side)):
                raise IncorrectResult(f"{kind} roundtrip lost {name} regional members.")
        restored = restored.reindex(index=source.index, columns=source.columns)
        np.testing.assert_allclose(source.to_numpy(), restored.to_numpy())
    return {
        "membership_and_values_preserved": True,
        "axis_layout_or_order_changes": layout_changes,
    }


def _shock(database, root):
    use = database.matrices["baseline"]["U"]
    nonzero = use.sparse.to_coo()
    row, column = int(nonzero.row[0]), int(nonzero.col[0])
    c_region, _, c = use.index[row]
    a_region, _, a = use.columns[column]
    before = database.query("u").to_numpy()
    payload = pd.DataFrame(
        {
            "Region_from": [c_region],
            "Commodity_from": [c],
            "Region_to": [a_region],
            "Activity_to": [a],
            "type": ["Percentage"],
            "value": [0.1],
        }
    )
    database.shock_calc({"u": payload}, u=True, scenario="probe")
    result = database.query("u", scenarios="probe")
    expected = before.copy()
    expected[row, column] *= 1.1
    np.testing.assert_allclose(result.to_numpy(), expected)
    return result


def _supply_mix(database, root):
    row = database.matrices["baseline"]["S"].index[0]
    commodity = database.matrices["baseline"]["S"].columns[0][2]
    database.update_supply_mix(
        {row[0]: {row[2]: 1.0}}, level=MI["a"], commodities=[commodity]
    )


def _trade_mix(database, root):
    region = database._indeces["r"]["main"][0]
    database.update_trade_mix(
        {region: {region: 1.0}}, items=[_first(database, "c")], level=MI["c"]
    )


def _add_extension(database, root):
    columns = database.query("E").columns
    extension = pd.DataFrame(1.0, index=["diagnostic extension"], columns=columns)
    units = pd.DataFrame({"unit": ["tonnes"]}, index=extension.index)
    database.add_extensions(extension, "E", units=units, calc_all=False)
    if "diagnostic extension" not in database.get_index(MI["k"]):
        raise IncorrectResult("The added extension is missing from the satellite set.")


def _equal_changed_domain(database, root):
    changed = database.copy()
    a, b = _first(database, "a"), database._indeces["a"]["main"][-1]
    for block in changed.matrices["baseline"].values():
        for side in ("index", "columns"):
            axis = getattr(block, side)
            if isinstance(axis, pd.MultiIndex) and axis.nlevels == 3:
                labels = [
                    (
                        (r, level, b if item == a else a if item == b else item)
                        if level == MI["a"]
                        else (r, level, item)
                    )
                    for r, level, item in axis
                ]
                setattr(
                    block, side, pd.MultiIndex.from_tuples(labels, names=axis.names)
                )
    if database == changed:
        raise IncorrectResult(
            "Database equality ignores different regional activity memberships."
        )
    return False


def _representation(database, root):
    text = str(database)
    for name, members in database.get_index("all").items():
        if isinstance(members, dict):
            counts = [len(values) for values in members.values()]
            expected = (
                f"from {min(counts, default=0)} to {max(counts, default=0)} per region"
            )
        else:
            expected = str(len(members))
        if f"{name} = {expected}\n" not in text:
            raise IncorrectResult(
                f"The database summary has an incorrect count for {name}."
            )
    return text


def _cases(small):
    cases = [
        ("get_index/all", lambda d, p: d.get_index("all")),
        (
            "get_data/native",
            lambda d, p: d.get_data(["S", "U", "Yc"], auto_calc=False, format="dict"),
        ),
        ("repr", _representation),
        ("search", _search),
        ("default_clusters", _clusters),
        (
            "set_clusters",
            lambda d, p: d.set_clusters({MI["a"]: {"selection": [_first(d, "a")]}}),
        ),
        ("get_aggregation_excel", _template),
        ("aggregate/activity_identity", _identity_aggregation),
        ("aggregate/regions_world", _world_aggregation),
        ("calc_all/vectors", lambda d, p: d.calc_all(["Xa", "Xc"])),
        ("is_isard", lambda d, p: d.is_isard()),
        ("is_balanced", lambda d, p: d.is_balanced("flows")),
    ]
    if small:
        cases += [
            ("equality/regional_members", _equal_changed_domain),
            ("calc_all/coefficients", lambda d, p: d.calc_all(["u", "s", "ea", "ec"])),
            ("calc_all/footprints", lambda d, p: d.calc_all(["Fa", "Fc"])),
            ("calc_linkages", lambda d, p: d.calc_linkages()),
            ("calc_trades", lambda d, p: d.calc_trades(item=_first(d, "c"))),
            (
                "calc_trades_content",
                lambda d, p: d.calc_trades_content(_first(d, "k"), item=_first(d, "c")),
            ),
            (
                "get_extensions_excel",
                lambda d, p: d.get_extensions_excel(
                    "E", path=str(p / "extensions.xlsx")
                ),
            ),
            ("add_extensions", _add_extension),
            (
                "get_shock_excel",
                lambda d, p: d.get_shock_excel(path=str(p / "shock.xlsx")),
            ),
            ("shock_calc/u", _shock),
            ("update_supply_mix", _supply_mix),
            ("update_trade_mix", _trade_mix),
            (
                "get_add_sectors_excel",
                lambda d, p: d.get_add_sectors_excel(path=str(p / "add.xlsx")),
            ),
            ("pool_trade", lambda d, p: d.pool_trade(_first(d, "c"), inplace=False)),
            ("to_chenery_moses", lambda d, p: d.to_chenery_moses(inplace=False)),
            ("to_iot", lambda d, p: d.to_iot("B", inplace=False)),
            ("to_iot/to_pymrio", lambda d, p: d.to_iot("B", inplace=False).to_pymrio()),
            (
                "to_region_subset",
                lambda d, p: d.to_region_subset(
                    d._indeces["r"]["main"][0], inplace=False
                ),
            ),
            ("to_pymrio", lambda d, p: d.to_pymrio()),
            ("roundtrip/excel", lambda d, p: _roundtrip(d, p, "excel")),
            ("roundtrip/csv", lambda d, p: _roundtrip(d, p, "csv")),
            ("roundtrip/parquet", lambda d, p: _roundtrip(d, p, "parquet")),
            (
                "plot",
                lambda d, p: d.plot(
                    matrix="Yc", kind="bar", path=str(p / "plot.html"), auto_open=False
                ),
            ),
            ("calc_ghg/auto", lambda d, p: d.calc_ghg(inplace=False)),
            (
                "calc_ghg/explicit",
                lambda d, p: d.calc_ghg(
                    gwp={_first(d, "k"): 1.0},
                    label="diagnostic GHG",
                    unit="tonnes",
                    inplace=False,
                ),
            ),
        ]
    return cases


def _run(base, operation, folder, legacy, timeout):
    database = base.copy()
    if legacy:
        database.get_index = MethodType(_legacy_get_index, database)
    folder.mkdir(parents=True)
    start = time.monotonic()
    alarm = hasattr(signal, "setitimer") and timeout > 0
    previous_handler = None

    def deadline(signum, frame):
        raise TimeoutError(f"Probe exceeded its {timeout:g}-second time budget.")

    if alarm:
        previous_handler = signal.signal(signal.SIGALRM, deadline)
        signal.setitimer(signal.ITIMER_REAL, timeout)
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            value = operation(database, folder)
        return {
            "status": "ok",
            "seconds": round(time.monotonic() - start, 3),
            "result": _summary(value),
            "warnings": list(dict.fromkeys(str(w.message)[:400] for w in caught))[:5],
        }
    except Exception as error:
        frames = traceback.extract_tb(error.__traceback__)
        source_root = Path(mario.__file__).resolve().parent
        source_frames = [
            frame
            for frame in frames
            if Path(frame.filename).is_relative_to(source_root)
        ]
        return {
            "status": (
                "timeout"
                if isinstance(error, TimeoutError)
                else (
                    "incorrect_result"
                    if isinstance(error, IncorrectResult)
                    else "error"
                )
            ),
            "seconds": round(time.monotonic() - start, 3),
            "exception": type(error).__name__,
            "message": str(error)[:1000],
            "site": [
                {"file": Path(f.filename).name, "line": f.lineno, "function": f.name}
                for f in (source_frames[-4:] + frames[-4:])
            ],
        }
    finally:
        if alarm:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous_handler)
        del database
        gc.collect()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--path",
        type=Path,
        help="Optional complete Balanced ZIP for full-size sparse probes.",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--methods", nargs="+", help="Restrict probes to these method names."
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Replace selected probes in an existing report.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=45,
        help="Per-method time budget in seconds (0 disables, POSIX).",
    )
    args = parser.parse_args()
    if args.timeout < 0:
        parser.error("--timeout must be non-negative")
    report = {
        "created": datetime.now(timezone.utc).isoformat(),
        "scope": "API/structural probes; not economic result validation",
        "probes": [],
        "datasets": {},
        "not_exercised": [
            "Full-size inverse matrices, linkages, footprints, dense exports, plots and shocks: tested only on small_balanced.",
            "add_sectors and CVXLab optimization: no filled inventory workbook or optimization model supplied; only template generation is probed.",
            "Economic accuracy of calculated footprints and GHG factors is outside this structural diagnosis.",
        ],
    }
    if args.append and args.output.exists():
        report = json.loads(args.output.read_text())
        report["updated"] = datetime.now(timezone.utc).isoformat()
    report["environment"] = {
        "python": platform.python_version(),
        "mario": mario.__version__,
        "pandas": pd.__version__,
        "numpy": np.__version__,
    }
    with tempfile.TemporaryDirectory(prefix="mario-bonsai-methods-") as directory:
        root = Path(directory)
        scopes = [
            (
                "small_balanced",
                mario.parse_bonsai(_small_bundle(root / "balanced")),
                True,
            )
        ]
        if args.path:
            scopes.append(("full_balanced", mario.parse_bonsai(args.path), False))
        for scope, base, small in scopes:
            views = base.get_index("all")
            report["datasets"][scope] = {
                "reference_year": base.meta.year,
                "shapes": {
                    name: list(frame.shape)
                    for name, frame in base.matrices["baseline"].items()
                },
                "indexes": {
                    name: (
                        {
                            "type": "dict",
                            "counts": {r: len(items) for r, items in view.items()},
                        }
                        if isinstance(view, dict)
                        else {"type": "list", "count": len(view)}
                    )
                    for name, view in views.items()
                },
            }
            for number, (name, operation) in enumerate(_cases(small)):
                if args.methods and name not in args.methods:
                    continue
                results = {
                    mode: _run(
                        base,
                        operation,
                        root / scope / str(number) / mode,
                        legacy=mode == "legacy",
                        timeout=args.timeout,
                    )
                    for mode in ("current", "legacy")
                }
                current_ok = results["current"]["status"] == "ok"
                legacy_ok = results["legacy"]["status"] == "ok"
                if any(result["status"] == "timeout" for result in results.values()):
                    outcome = "resource_limit"
                elif current_ok and legacy_ok:
                    outcome = "ok"
                elif not current_ok and legacy_ok:
                    outcome = "new_regression"
                elif current_ok:
                    outcome = "improved"
                elif any(
                    results["current"].get(key) != results["legacy"].get(key)
                    for key in ("status", "exception", "message")
                ):
                    outcome = "changed_failure"
                else:
                    outcome = "existing_problem"
                report["probes"] = [
                    row
                    for row in report["probes"]
                    if (row["scope"], row["method"]) != (scope, name)
                ]
                report["probes"].append(
                    {"scope": scope, "method": name, "outcome": outcome, **results}
                )
                args.output.parent.mkdir(parents=True, exist_ok=True)
                temporary = args.output.with_name(args.output.name + ".tmp")
                temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False))
                temporary.replace(args.output)
                print(scope, name, outcome, results["current"]["status"], flush=True)
    print(dict(Counter(p["outcome"] for p in report["probes"])))


if __name__ == "__main__":
    main()

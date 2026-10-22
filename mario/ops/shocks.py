# -*- coding: utf-8 -*-
"""
module contains the shock functions
"""

import copy
import logging
import os
from collections.abc import Mapping

import pandas as pd
import numpy as np
from mario.compute.helpers import _is_sparse_backed_dataframe, sparse_frame_from_spmatrix
from mario.log_exc.logger import log_time
from mario.log_exc.exceptions import WrongInput
from mario.model.conventions import _MASTER_INDEX, _ENUM
from mario.ops.workbook_specs import SHOCK_COLUMNS, SHOCK_FLAT_COLUMNS
from mario.clusters.definitions import normalize_cluster_members

logger = logging.getLogger(__name__)
_SHOCK_SHEET_CACHE = {}


def _sheet_candidates(*sheet_names):
    """Return de-duplicated candidate worksheet names preserving order."""
    seen = set()
    ordered = []
    for name in sheet_names:
        if name is None:
            continue
        token = str(name)
        if token not in seen:
            ordered.append(token)
            seen.add(token)
    return ordered


def _available_shock_sheet_names(path):
    """Return cached workbook sheet names for one shock source."""
    if isinstance(path, pd.ExcelFile):
        return tuple(path.sheet_names)

    if isinstance(path, str):
        absolute_path = os.path.abspath(path)
        stat = os.stat(absolute_path)
        signature = (stat.st_mtime_ns, stat.st_size)
        cached = _SHOCK_SHEET_CACHE.get(absolute_path)
        if cached is not None and cached[0] == signature:
            return cached[1]

        with pd.ExcelFile(absolute_path) as workbook:
            sheet_names = tuple(workbook.sheet_names)
        _SHOCK_SHEET_CACHE[absolute_path] = (signature, sheet_names)
        return sheet_names

    if hasattr(path, "keys"):
        return tuple(str(key) for key in path.keys())

    return ()


def has_shock_sheet(path, *sheet_names):
    """Return whether a workbook-like source exposes one of the requested sheets."""
    candidates = _sheet_candidates(*sheet_names)
    available = set(_available_shock_sheet_names(path))
    return any(name in available for name in candidates)


def _read_shock_sheet(path, *sheet_names):
    """Read the first available worksheet among the provided candidate names."""
    candidates = _sheet_candidates(*sheet_names)
    if isinstance(path, str):
        available = set(_available_shock_sheet_names(path))
        for name in candidates:
            if name in available:
                return pd.read_excel(path, name, header=[0])
        return None

    if isinstance(path, pd.ExcelFile):
        available = set(path.sheet_names)
        for name in candidates:
            if name in available:
                return pd.read_excel(path, name, header=[0])
        return None

    if hasattr(path, "keys"):
        for name in candidates:
            if name in path:
                return path[name]
        return None

    raise WrongInput("Shock source should be an Excel path or a workbook-like mapping.")


def _shock_column(info, *candidates, required=True, default=None):
    """Return one shock workbook column trying multiple legacy/new labels."""
    for candidate in candidates:
        if candidate in info.columns:
            return list(info[candidate].values)

    if required:
        raise WrongInput(
            f"Shock file is missing required column. Expected one of: {candidates}"
        )

    return [default] * len(info)


class _RegionalCode(dict):
    """A literal code, distinct from a cluster with an empty regional selection."""

    def __init__(self, code, domain):
        super().__init__(
            (r, [code] if code in members else []) for r, members in domain.items()
        )
        self.code = code


def check_replace_clusters(userValue, dataValues, clusters):
    """Resolve a user value directly or through the optional cluster mapping."""
    if isinstance(dataValues, Mapping):
        if any(userValue in members for members in dataValues.values()):
            return _RegionalCode(userValue, dataValues)
        if clusters is not None and userValue in clusters:
            return normalize_cluster_members(
                clusters[userValue], dataValues, level="regional set", name=userValue
            )
        raise WrongInput(f"{userValue} not in the database neither in clusters.")

    if userValue in dataValues:
        return userValue

    else:
        if clusters is not None and clusters.get(userValue) is not None:
            return clusters.get(userValue)

        else:
            raise WrongInput(f"{userValue} not in the database neither in clusters.")


def get_value(given):
    """Return a scalar/array view for either pandas or plain Python inputs."""
    if isinstance(given, (pd.DataFrame, pd.Series)):
        return given.values
    return given


def _is_supply_mix_type(value):
    """Return whether one shock ``Type`` cell selects a supply-mix redistribution."""
    return str(value).strip().casefold().startswith("supply mix")


def _is_trade_mix_type(value):
    """Return whether one shock ``Type`` cell selects a trade-mix redistribution."""
    return str(value).strip().casefold().startswith("trade mix")


def _is_mix_type(value):
    """Return whether one shock ``Type`` cell selects any mix redistribution.

    Mix rows are collected by the dedicated spec readers and must be skipped
    by the cell-wise shock readers.
    """
    return _is_supply_mix_type(value) or _is_trade_mix_type(value)


def _mix_target_selector(values):
    """Return the distinct target labels, or ``None`` when any is the ``all`` wildcard."""
    selected = []
    for value in values:
        token = "" if pd.isna(value) else str(value).strip()
        if token == "" or token.casefold() in {"all", "global"}:
            return None
        if value not in selected:
            selected.append(value)
    return selected or None


def _collect_supply_mix_groups(info, *, member_column, target_column, legacy_member, legacy_target):
    """Group the supply-mix rows of one shock sheet by ``(Region_from, mix id)``."""
    _type = _shock_column(info, SHOCK_FLAT_COLUMNS["type"], SHOCK_COLUMNS["type"])
    region_from = _shock_column(info, SHOCK_FLAT_COLUMNS["region_from"], SHOCK_COLUMNS["r_reg"])
    member_from = _shock_column(info, member_column, legacy_member)
    region_to = _shock_column(info, SHOCK_FLAT_COLUMNS["region_to"], SHOCK_COLUMNS["c_reg"])
    target_to = (
        _shock_column(info, target_column, legacy_target)
        if target_column is not None
        else None
    )
    value = _shock_column(info, SHOCK_FLAT_COLUMNS["value"], SHOCK_COLUMNS["value"])

    groups = {}
    for row in range(len(info)):
        if not _is_supply_mix_type(_type[row]):
            continue
        groups.setdefault((region_from[row], str(_type[row]).strip()), []).append(row)

    collected = []
    for (region, _mix_id), rows in groups.items():
        collected.append(
            {
                "shares": {region: {member_from[row]: float(value[row]) for row in rows}},
                "column_regions": _mix_target_selector([region_to[row] for row in rows]),
                "targets": (
                    _mix_target_selector([target_to[row] for row in rows])
                    if target_to is not None
                    else None
                ),
            }
        )
    return collected


def _collect_trade_mix_groups(info, *, item_column, target_column, legacy_item, legacy_target):
    """Group the trade-mix rows of one shock sheet by ``(item, Region_to, mix id)``.

    Within one group ``Region_from`` carries the origin regions and ``Value``
    their shares; ``Region_to`` is the destination market and must be one
    explicit region.
    """
    _type = _shock_column(info, SHOCK_FLAT_COLUMNS["type"], SHOCK_COLUMNS["type"])
    region_from = _shock_column(info, SHOCK_FLAT_COLUMNS["region_from"], SHOCK_COLUMNS["r_reg"])
    item_from = _shock_column(info, item_column, legacy_item)
    region_to = _shock_column(info, SHOCK_FLAT_COLUMNS["region_to"], SHOCK_COLUMNS["c_reg"])
    target_to = (
        _shock_column(info, target_column, legacy_target)
        if target_column is not None
        else None
    )
    value = _shock_column(info, SHOCK_FLAT_COLUMNS["value"], SHOCK_COLUMNS["value"])

    groups = {}
    for row in range(len(info)):
        if not _is_trade_mix_type(_type[row]):
            continue
        destination = region_to[row]
        token = "" if pd.isna(destination) else str(destination).strip()
        if token == "" or token.casefold() in {"all", "global"}:
            raise WrongInput(
                "Type='Trade mix N' rows must name one explicit destination region in "
                f"'{SHOCK_FLAT_COLUMNS['region_to']}' ('all' is not allowed)."
            )
        groups.setdefault(
            (item_from[row], token, str(_type[row]).strip()), []
        ).append(row)

    collected = []
    for (item, destination, _mix_id), rows in groups.items():
        collected.append(
            {
                "shares": {destination: {region_from[row]: float(value[row]) for row in rows}},
                "items": [item],
                "targets": (
                    _mix_target_selector([target_to[row] for row in rows])
                    if target_to is not None
                    else None
                ),
            }
        )
    return collected


def _warn_ignored_mix_rows(path, candidates, message):
    """Warn when one sheet contains mix rows that will not be applied."""
    info = _read_shock_sheet(path, *candidates)
    if info is None:
        return
    _type = _shock_column(info, SHOCK_FLAT_COLUMNS["type"], SHOCK_COLUMNS["type"], required=False)
    if any(_is_mix_type(_type[row]) for row in range(len(info))):
        log_time(logger, message, "warning")


def read_supply_mix_specs(instance, path):
    """Collect ``Type='Supply mix N'`` groups from the shock workbook.

    Each ``(Region_from, 'Supply mix N')`` group is one mix: its member rows
    are the labels and ``Value`` their shares, while ``Region_to`` (and the
    sheet's column-label field) select the target columns (``all`` means every
    column). Returns dicts ready for ``update_supply_mix``.

    IOT workbooks read the ``z`` and ``Y`` sheets (members: ``Sector_from``).
    Because the update rewrites both ``z`` and ``Y``, a mix authored in either
    sheet has the same effect and the operation is idempotent.

    SUT workbooks read the split sheets:

    * ``u``/``Yc`` — Commodity mixes (members: ``Commodity_from``) rewriting
      ``u`` and ``Yc``; ``Activity_to`` on the ``u`` sheet restricts the buyer
      activities.
    * ``s`` — Activity market-share mixes (members: ``Activity_from``); each
      row must name the target commodity in ``Commodity_to`` (``all`` is not
      allowed).

    Supply-mix rows found in the legacy unified ``z``/``Y`` sheets or in the
    ``Ya`` sheet of one SUT workbook are ignored with one warning.
    """
    specs = []

    if instance.meta.table == "SUT":
        u_candidates = (_ENUM.u, str(_ENUM.u).lower())
        s_candidates = (_ENUM.s, str(_ENUM.s).lower())

        info = _read_shock_sheet(path, *u_candidates)
        if info is not None:
            for group in _collect_supply_mix_groups(
                info,
                member_column=SHOCK_FLAT_COLUMNS["commodity_from"],
                target_column=SHOCK_FLAT_COLUMNS["activity_to"],
                legacy_member=SHOCK_COLUMNS["r_sec"],
                legacy_target=SHOCK_COLUMNS["c_sec"],
            ):
                specs.append(
                    {
                        "shares": group["shares"],
                        "level": _MASTER_INDEX["c"],
                        "column_regions": group["column_regions"],
                        "column_sectors": group["targets"],
                        "column_categories": None,
                        "commodities": None,
                    }
                )

        info = _read_shock_sheet(path, *s_candidates)
        if info is not None:
            for group in _collect_supply_mix_groups(
                info,
                member_column=SHOCK_FLAT_COLUMNS["activity_from"],
                target_column=SHOCK_FLAT_COLUMNS["commodity_to"],
                legacy_member=SHOCK_COLUMNS["r_sec"],
                legacy_target=SHOCK_COLUMNS["c_sec"],
            ):
                if group["targets"] is None:
                    (mix_region,) = group["shares"]
                    raise WrongInput(
                        "Type='Supply mix N' rows on the 's' sheet rewrite market shares and must "
                        f"name the target commodity in '{SHOCK_FLAT_COLUMNS['commodity_to']}' "
                        f"('all' is not allowed). Offending mix: region {mix_region!r}."
                    )
                specs.append(
                    {
                        "shares": group["shares"],
                        "level": _MASTER_INDEX["a"],
                        "column_regions": group["column_regions"],
                        "column_sectors": None,
                        "column_categories": None,
                        "commodities": group["targets"],
                    }
                )

        info = _read_shock_sheet(path, "Yc")
        if info is not None:
            for group in _collect_supply_mix_groups(
                info,
                member_column=SHOCK_FLAT_COLUMNS["commodity_from"],
                target_column=SHOCK_FLAT_COLUMNS["category_to"],
                legacy_member=SHOCK_COLUMNS["r_sec"],
                legacy_target=SHOCK_COLUMNS["d_cat"],
            ):
                specs.append(
                    {
                        "shares": group["shares"],
                        "level": _MASTER_INDEX["c"],
                        "column_regions": group["column_regions"],
                        "column_sectors": None,
                        "column_categories": group["targets"],
                        "commodities": None,
                    }
                )

        _warn_ignored_mix_rows(
            path,
            (_ENUM.z, _ENUM.Z, str(_ENUM.z).lower(), str(_ENUM.Z).upper()),
            "Shock: 'Supply mix N'/'Trade mix N' rows on the legacy unified 'z' sheet are ignored "
            "for SUT databases. Author commodity mixes on the 'u'/'Yc' sheets and market-share "
            "mixes on the 's' sheet.",
        )
        _warn_ignored_mix_rows(
            path,
            (_ENUM.Y, str(_ENUM.Y).lower(), str(_ENUM.Y).upper()),
            "Shock: 'Supply mix N'/'Trade mix N' rows on the legacy unified 'Y' sheet are ignored "
            "for SUT databases. Author commodity mixes on the 'u'/'Yc' sheets.",
        )
        _warn_ignored_mix_rows(
            path,
            ("Ya",),
            "Shock: 'Supply mix N'/'Trade mix N' rows on the 'Ya' sheet are ignored. Activities "
            "have no final-demand mix; author market-share and trade mixes on the 's' sheet.",
        )

        return specs

    sheets = (
        ((_ENUM.z, _ENUM.Z, str(_ENUM.z).lower(), str(_ENUM.Z).upper()), True),
        ((_ENUM.Y, str(_ENUM.Y).lower(), str(_ENUM.Y).upper()), False),
    )
    for candidates, has_sector_to in sheets:
        info = _read_shock_sheet(path, *candidates)
        if info is None:
            continue
        for group in _collect_supply_mix_groups(
            info,
            member_column=SHOCK_FLAT_COLUMNS["sector_from"],
            target_column=(
                SHOCK_FLAT_COLUMNS["sector_to"]
                if has_sector_to
                else SHOCK_FLAT_COLUMNS["category_to"]
            ),
            legacy_member=SHOCK_COLUMNS["r_sec"],
            legacy_target=SHOCK_COLUMNS["c_sec"] if has_sector_to else SHOCK_COLUMNS["d_cat"],
        ):
            specs.append(
                {
                    "shares": group["shares"],
                    "level": None,
                    "column_regions": group["column_regions"],
                    "column_sectors": group["targets"] if has_sector_to else None,
                    "column_categories": None if has_sector_to else group["targets"],
                    "commodities": None,
                }
            )
    return specs


def read_trade_mix_specs(instance, path):
    """Collect ``Type='Trade mix N'`` groups from the shock workbook.

    Each ``(item, Region_to, 'Trade mix N')`` group is one destination mix:
    its rows carry the origin regions in ``Region_from`` and their shares in
    ``Value``, while ``Region_to`` names the destination market (one explicit
    region; ``all`` is rejected). Returns dicts ready for
    ``update_trade_mix``.

    IOT workbooks read the ``z`` and ``Y`` sheets (traded item:
    ``Sector_from``; ``Sector_to`` on ``z`` optionally restricts the buyer
    columns). SUT workbooks read the split sheets:

    * ``u``/``Yc`` — Commodity-level (Isard) trade mixes; ``Activity_to`` on
      the ``u`` sheet restricts the buyer activities.
    * ``s`` — Activity-level trade mixes for pooled/Chenery-Moses layouts;
      each group must name the destination market commodity in
      ``Commodity_to`` (``all`` is not allowed).

    Mix rows found on the legacy unified sheets or on ``Ya`` are reported by
    ``read_supply_mix_specs``, which runs on the same workbook.
    """
    specs = []

    if instance.meta.table == "SUT":
        info = _read_shock_sheet(path, _ENUM.u, str(_ENUM.u).lower())
        if info is not None:
            for group in _collect_trade_mix_groups(
                info,
                item_column=SHOCK_FLAT_COLUMNS["commodity_from"],
                target_column=SHOCK_FLAT_COLUMNS["activity_to"],
                legacy_item=SHOCK_COLUMNS["r_sec"],
                legacy_target=SHOCK_COLUMNS["c_sec"],
            ):
                specs.append(
                    {
                        "shares": group["shares"],
                        "items": group["items"],
                        "level": _MASTER_INDEX["c"],
                        "column_sectors": group["targets"],
                        "column_categories": None,
                        "commodities": None,
                    }
                )

        info = _read_shock_sheet(path, _ENUM.s, str(_ENUM.s).lower())
        if info is not None:
            for group in _collect_trade_mix_groups(
                info,
                item_column=SHOCK_FLAT_COLUMNS["activity_from"],
                target_column=SHOCK_FLAT_COLUMNS["commodity_to"],
                legacy_item=SHOCK_COLUMNS["r_sec"],
                legacy_target=SHOCK_COLUMNS["c_sec"],
            ):
                if group["targets"] is None:
                    (destination,) = group["shares"]
                    raise WrongInput(
                        "Type='Trade mix N' rows on the 's' sheet rewrite market shares and must "
                        f"name the destination market commodity in '{SHOCK_FLAT_COLUMNS['commodity_to']}' "
                        f"('all' is not allowed). Offending mix: destination {destination!r}."
                    )
                specs.append(
                    {
                        "shares": group["shares"],
                        "items": group["items"],
                        "level": _MASTER_INDEX["a"],
                        "column_sectors": None,
                        "column_categories": None,
                        "commodities": group["targets"],
                    }
                )

        info = _read_shock_sheet(path, "Yc")
        if info is not None:
            for group in _collect_trade_mix_groups(
                info,
                item_column=SHOCK_FLAT_COLUMNS["commodity_from"],
                target_column=SHOCK_FLAT_COLUMNS["category_to"],
                legacy_item=SHOCK_COLUMNS["r_sec"],
                legacy_target=SHOCK_COLUMNS["d_cat"],
            ):
                specs.append(
                    {
                        "shares": group["shares"],
                        "items": group["items"],
                        "level": _MASTER_INDEX["c"],
                        "column_sectors": None,
                        "column_categories": group["targets"],
                        "commodities": None,
                    }
                )

        return specs

    sheets = (
        ((_ENUM.z, _ENUM.Z, str(_ENUM.z).lower(), str(_ENUM.Z).upper()), True),
        ((_ENUM.Y, str(_ENUM.Y).lower(), str(_ENUM.Y).upper()), False),
    )
    for candidates, has_sector_to in sheets:
        info = _read_shock_sheet(path, *candidates)
        if info is None:
            continue
        for group in _collect_trade_mix_groups(
            info,
            item_column=SHOCK_FLAT_COLUMNS["sector_from"],
            target_column=(
                SHOCK_FLAT_COLUMNS["sector_to"]
                if has_sector_to
                else SHOCK_FLAT_COLUMNS["category_to"]
            ),
            legacy_item=SHOCK_COLUMNS["r_sec"],
            legacy_target=SHOCK_COLUMNS["c_sec"] if has_sector_to else SHOCK_COLUMNS["d_cat"],
        ):
            specs.append(
                {
                    "shares": group["shares"],
                    "items": group["items"],
                    "level": None,
                    "column_sectors": group["targets"] if has_sector_to else None,
                    "column_categories": None if has_sector_to else group["targets"],
                    "commodities": None,
                }
            )
    return specs


def _io_axis_key(axis, region, level, item):
    """Build one row/column key matching either legacy or flat IO axes."""
    if isinstance(item, Mapping):
        if not isinstance(axis, pd.MultiIndex):
            raise WrongInput("Regional cluster members require a regional matrix axis.")
        regions = list(region) if pd.api.types.is_list_like(region) else [region]
        allowed = {r: set(item.get(r, ())) for r in regions}
        keys = [
            key
            for key in axis
            if key[0] in allowed
            and (axis.nlevels == 2 or key[1] == level)
            and key[-1] in allowed[key[0]]
        ]
        if not keys and isinstance(item, _RegionalCode):
            raise WrongInput(
                f"{item.code!r} does not exist in the selected regions {regions}."
            )
        return keys
    if isinstance(axis, pd.MultiIndex):
        if axis.nlevels >= 3:
            return (region, level, item)
        if axis.nlevels == 2:
            return (region, item)
    return item


def _fd_axis_key(axis, region, category):
    """Build one final-demand column key for legacy or flat layouts."""
    if isinstance(category, Mapping):
        return _io_axis_key(axis, region, _MASTER_INDEX["n"], category)
    if isinstance(axis, pd.MultiIndex):
        if axis.nlevels >= 3:
            return (region, _MASTER_INDEX["n"], category)
        if axis.nlevels == 2:
            return (region, category)
    return category


def _account_axis_key(axis, level, members):
    """Select regional factor/satellite rows by their own region-item pairs."""
    if isinstance(members, Mapping):
        return _io_axis_key(axis, list(members), level, members)
    return members


def _apply_shock(
    frame, rows, columns, kind, value, *, flow=None, output=None, output_key=None
):
    """Update existing selections, retaining sparse storage and axis membership."""
    row_positions = np.atleast_1d(
        pd.Series(np.arange(len(frame.index)), index=frame.index).loc[rows]
    ).astype(int)
    column_positions = np.atleast_1d(
        pd.Series(np.arange(len(frame.columns)), index=frame.columns).loc[columns]
    ).astype(int)
    if kind not in {"Percentage", "Absolute", "Update"}:
        raise WrongInput(
            "Acceptable values for type are Absolute, Percentage, and Update."
        )
    if not len(row_positions) or not len(column_positions):
        return frame

    sparse = _is_sparse_backed_dataframe(frame)
    if sparse and kind == "Percentage":
        matrix = frame.sparse.to_coo().astype(float)
        selected = np.isin(matrix.row, row_positions) & np.isin(
            matrix.col, column_positions
        )
        matrix.data[selected] *= 1 + value
        matrix.eliminate_zeros()
        return sparse_frame_from_spmatrix(
            matrix, index=frame.index, columns=frame.columns
        )

    if kind == "Update":
        values = value
    elif kind == "Percentage":
        values = get_value(frame.loc[rows, columns]) * (1 + value)
    else:
        source = frame if flow is None else flow
        values = get_value(source.loc[rows, columns]) + value
        if output is not None:
            divisor = output.loc[output_key, "production"]
            if isinstance(divisor, pd.Series):
                # Output and matrix axes can have different orders, or omit
                # the constant Level component on one of the two axes.
                def node(label):
                    return (label[0], label[-1]) if isinstance(label, tuple) else label

                by_node = dict(zip(map(node, divisor.index), get_value(divisor)))
                divisor = np.array(
                    [
                        by_node[node(label)]
                        for label in frame.columns.take(column_positions)
                    ]
                )
            values = values / get_value(divisor)

    if not sparse:
        frame.loc[rows, columns] = values
        return frame

    # Replace selected sparse columns, using at most one dense column vector
    # rather than densifying the full matrix or assigning into SparseArray.
    values = np.asarray(values)
    if (
        values.ndim == 1
        and len(column_positions) == 1
        and len(values) == len(row_positions)
    ):
        values = values[:, None]
    values = np.broadcast_to(values, (len(row_positions), len(column_positions)))
    for j, position in enumerate(column_positions):
        column = (
            frame.iloc[:, position].sparse.to_dense().to_numpy(dtype=float, copy=True)
        )
        column[row_positions] = values[:, j]
        frame[frame.columns[position]] = pd.arrays.SparseArray(column, fill_value=0.0)
    return frame


def _baseline_block(instance, matrix_name):
    """Return one base block through direct storage when already materialized.

    The base scenario defaults to the baseline but is overridden by
    ``instance._shock_base_scenario`` when ``shock_calc`` builds a shock on top
    of another scenario.
    """
    scenario = getattr(instance, "_shock_base_scenario", None) or "baseline"
    if instance.has_matrix(matrix_name, scenario=scenario):
        return instance.get_block_as_pandas(matrix_name, scenario=scenario)
    return instance.query(matrix_name, scenarios=scenario)


def nan_check(dataframe, row, shock_type):
    """Detect whether a shock row is effectively incomplete."""
    dataframe = copy.deepcopy(dataframe)

    if shock_type != "Switch":
        try:
            dataframe = dataframe.drop(SHOCK_COLUMNS["s_sec"], axis=1)
        except:
            pass
    return dataframe.loc[row].isnull().values.any()


def Y_shock(instance, path, boolean, clusters, to_baseline):
    """Apply final-demand shocks and return the updated block plus notes."""
    Y = _baseline_block(instance, _ENUM.Y)
    notes = []

    if not boolean:
        return Y, notes

    info = _read_shock_sheet(path, _ENUM.Y, _ENUM.Y.lower(), _ENUM.Y.upper())
    if info is None:
        return Y, notes

    row_region = _shock_column(
        info,
        SHOCK_FLAT_COLUMNS["region_from"],
        SHOCK_COLUMNS["r_reg"],
    )
    if instance.meta.table == "IOT":
        row_level = [_MASTER_INDEX["s"]] * len(info)
        row_sector = _shock_column(
            info,
            SHOCK_FLAT_COLUMNS["sector_from"],
            SHOCK_COLUMNS["r_sec"],
        )
    else:
        row_level = _shock_column(info, SHOCK_COLUMNS["r_lev"])
        row_sector = _shock_column(info, SHOCK_COLUMNS["r_sec"])

    column_region = _shock_column(
        info,
        SHOCK_FLAT_COLUMNS["region_to"],
        SHOCK_COLUMNS["c_reg"],
    )
    demand_category = _shock_column(
        info,
        SHOCK_FLAT_COLUMNS["category_to"],
        SHOCK_COLUMNS["d_cat"],
    )
    _type = _shock_column(info, SHOCK_FLAT_COLUMNS["type"], SHOCK_COLUMNS["type"])
    value = _shock_column(info, SHOCK_FLAT_COLUMNS["value"], SHOCK_COLUMNS["value"])

    if info.isnull().values.any():
        raise WrongInput(f"nans(empty cells) found in the shock file for '{_ENUM.Y}'.")

    for shock in range(len(info)):
        if _is_mix_type(_type[shock]):
            # Mix rows are collected and applied by the dedicated spec readers.
            continue
        if nan_check(info, shock, _type[shock]):
            log_time(
                logger,
                "nan values found on row {} of {} shock sheet. No more shock is imported after row {}".format(
                    shock, _ENUM.Y, shock
                ),
                "warning",
            )
            break

        # Performing a full shock on the inputs
        row_region_ = check_replace_clusters(
            userValue=row_region[shock],
            dataValues=instance.get_index(_MASTER_INDEX["r"]),
            clusters=clusters.get(_MASTER_INDEX["r"]),
        )

        row_level_ = check_replace_clusters(
            userValue=row_level[shock],
            dataValues=(
                [_MASTER_INDEX["s"]]
                if instance.meta.table == "IOT"
                else [_MASTER_INDEX["a"], _MASTER_INDEX["c"]]
            ),
            clusters=None,
        )

        row_sector_ = check_replace_clusters(
            userValue=row_sector[shock],
            dataValues=instance.get_index(row_level_),
            clusters=clusters.get(row_level_),
        )

        column_region_ = check_replace_clusters(
            userValue=column_region[shock],
            dataValues=instance.get_index(_MASTER_INDEX["r"]),
            clusters=clusters.get(_MASTER_INDEX["r"]),
        )

        demand_category_ = check_replace_clusters(
            userValue=demand_category[shock],
            dataValues=instance.get_index(_MASTER_INDEX["n"]),
            clusters=clusters.get(_MASTER_INDEX["n"]),
        )

        row_key = _io_axis_key(Y.index, row_region_, row_level_, row_sector_)
        col_key = _fd_axis_key(Y.columns, column_region_, demand_category_)

        Y = _apply_shock(Y, row_key, col_key, _type[shock], value[shock])

        notes.append(
            "Shock on Y implemented: row_region:{}, row_level:{}, "
            "row_sector:{}, column_region:{}, demand_category: {}, "
            "type: {}, value: {}.".format(
                row_region_,
                row_level_,
                row_sector_,
                column_region_,
                demand_category_,
                _type[shock],
                value[shock],
            )
        )

    return Y, notes


def V_shock(instance, path, matrix, boolean, clusters, to_baseline):
    """Apply value-added or extension shocks in coefficient space."""
    notes = []
    matrix_name = str(matrix).upper()

    if matrix_name == "V":
        coeff = _baseline_block(instance, _ENUM.v)
        flow_matrix = _ENUM.V
        _id = "f"

    else:
        coeff = _baseline_block(instance, _ENUM.e)
        flow_matrix = _ENUM.E
        _id = "k"

    matrix = _ENUM[matrix]

    if not boolean:
        return coeff, notes

    flow = _baseline_block(instance, flow_matrix)
    X = _baseline_block(instance, _ENUM.X)
    info = _read_shock_sheet(path, matrix, matrix.lower(), matrix.upper())
    if info is None:
        return coeff, notes

    if info.isnull().values.any():
        raise WrongInput(f"nans(empty cells) found in the shock file for '{matrix}'.")

    from_column = (
        SHOCK_FLAT_COLUMNS["factor_from"]
        if matrix_name == "V"
        else SHOCK_FLAT_COLUMNS["satellite_from"]
    )
    row_sector = _shock_column(info, from_column, SHOCK_COLUMNS["r_sec"])
    column_region = _shock_column(
        info,
        SHOCK_FLAT_COLUMNS["region_to"],
        SHOCK_COLUMNS["c_reg"],
    )
    if instance.meta.table == "IOT":
        column_level = [_MASTER_INDEX["s"]] * len(info)
        column_sector = _shock_column(
            info,
            SHOCK_FLAT_COLUMNS["sector_to"],
            SHOCK_COLUMNS["c_sec"],
        )
    else:
        column_level = _shock_column(info, SHOCK_COLUMNS["c_lev"])
        column_sector = _shock_column(info, SHOCK_COLUMNS["c_sec"])
    _type = _shock_column(info, SHOCK_FLAT_COLUMNS["type"], SHOCK_COLUMNS["type"])
    value = _shock_column(info, SHOCK_FLAT_COLUMNS["value"], SHOCK_COLUMNS["value"])

    for shock in range(len(info)):
        if nan_check(info, shock, _type[shock]):
            log_time(
                logger,
                "nan values found on row {} of {} shock sheet. No more shock is imported after row {}".format(
                    shock, matrix, shock
                ),
                "warning",
            )
            break

        row_sector_ = check_replace_clusters(
            userValue=row_sector[shock],
            dataValues=instance.get_index(_MASTER_INDEX[_id]),
            clusters=clusters.get(_MASTER_INDEX[_id]),
        )

        column_region_ = check_replace_clusters(
            userValue=column_region[shock],
            dataValues=instance.get_index(_MASTER_INDEX["r"]),
            clusters=clusters.get(_MASTER_INDEX["r"]),
        )

        column_level_ = check_replace_clusters(
            userValue=column_level[shock],
            dataValues=(
                [_MASTER_INDEX["s"]]
                if instance.meta.table == "IOT"
                else [_MASTER_INDEX["a"], _MASTER_INDEX["c"]]
            ),
            clusters=None,
        )

        column_sector_ = check_replace_clusters(
            userValue=column_sector[shock],
            dataValues=instance.get_index(column_level_),
            clusters=clusters.get(column_level_),
        )

        column_key = _io_axis_key(
            coeff.columns,
            column_region_,
            column_level_,
            column_sector_,
        )
        output_key = _io_axis_key(
            X.index,
            column_region_,
            column_level_,
            column_sector_,
        )

        row_key = _account_axis_key(coeff.index, _MASTER_INDEX[_id], row_sector_)
        coeff = _apply_shock(
            coeff,
            row_key,
            column_key,
            _type[shock],
            value[shock],
            flow=flow,
            output=X,
            output_key=output_key,
        )

        notes.append(
            "Shock on {} implemented: row_sector:{}, column_region:{}, "
            "column_level:{}, column_sector:{}, "
            "type: {}, value: {}.".format(
                matrix.lower(),
                row_sector_,
                column_region_,
                column_level_,
                column_sector_,
                _type[shock],
                value[shock],
            )
        )

    return coeff, notes


def _split_intermediate_shock(
    instance,
    path,
    *,
    boolean,
    clusters,
    coefficient_matrix,
    flow_matrix,
    output_matrix,
    row_level,
    column_level,
    sheet_name,
    note_label,
):
    """Apply shocks to one split SUT coefficient block such as ``u`` or ``s``."""
    notes = []
    coeff = _baseline_block(instance, coefficient_matrix)

    if not boolean:
        return coeff, notes

    info = _read_shock_sheet(
        path, sheet_name, coefficient_matrix, str(coefficient_matrix).lower()
    )
    if info is None:
        return coeff, notes

    flow = _baseline_block(instance, flow_matrix)
    output = _baseline_block(instance, output_matrix)

    if info.isnull().values.any():
        raise WrongInput(
            f"nans(empty cells) found in the shock file for '{sheet_name}'."
        )

    row_from = (
        SHOCK_FLAT_COLUMNS["commodity_from"]
        if row_level == _MASTER_INDEX["c"]
        else SHOCK_FLAT_COLUMNS["activity_from"]
    )
    column_to = (
        SHOCK_FLAT_COLUMNS["activity_to"]
        if column_level == _MASTER_INDEX["a"]
        else SHOCK_FLAT_COLUMNS["commodity_to"]
    )
    row_region = _shock_column(
        info,
        SHOCK_FLAT_COLUMNS["region_from"],
        SHOCK_COLUMNS["r_reg"],
    )
    row_sector = _shock_column(info, row_from, SHOCK_COLUMNS["r_sec"])
    column_region = _shock_column(
        info,
        SHOCK_FLAT_COLUMNS["region_to"],
        SHOCK_COLUMNS["c_reg"],
    )
    column_sector = _shock_column(info, column_to, SHOCK_COLUMNS["c_sec"])
    _type = _shock_column(info, SHOCK_FLAT_COLUMNS["type"], SHOCK_COLUMNS["type"])
    value = _shock_column(info, SHOCK_FLAT_COLUMNS["value"], SHOCK_COLUMNS["value"])

    for shock in range(len(info)):
        if _is_mix_type(_type[shock]):
            # Mix rows are collected and applied by the dedicated spec readers.
            continue
        if nan_check(info, shock, _type[shock]):
            log_time(
                logger,
                "nan values found on row {} of {} shock sheet. No more shock is imported after row {}".format(
                    shock, sheet_name, shock
                ),
                "warning",
            )
            break

        row_region_ = check_replace_clusters(
            userValue=row_region[shock],
            dataValues=instance.get_index(_MASTER_INDEX["r"]),
            clusters=clusters.get(_MASTER_INDEX["r"]),
        )
        row_sector_ = check_replace_clusters(
            userValue=row_sector[shock],
            dataValues=instance.get_index(row_level),
            clusters=clusters.get(row_level),
        )
        column_region_ = check_replace_clusters(
            userValue=column_region[shock],
            dataValues=instance.get_index(_MASTER_INDEX["r"]),
            clusters=clusters.get(_MASTER_INDEX["r"]),
        )
        column_sector_ = check_replace_clusters(
            userValue=column_sector[shock],
            dataValues=instance.get_index(column_level),
            clusters=clusters.get(column_level),
        )

        row_key = _io_axis_key(coeff.index, row_region_, row_level, row_sector_)
        col_key = _io_axis_key(
            coeff.columns, column_region_, column_level, column_sector_
        )
        output_key = _io_axis_key(
            output.index, column_region_, column_level, column_sector_
        )

        coeff = _apply_shock(
            coeff,
            row_key,
            col_key,
            _type[shock],
            value[shock],
            flow=flow,
            output=output,
            output_key=output_key,
        )

        notes.append(
            "Shock on {} implemented: row_region:{}, row_level:{}, "
            "row_sector:{}, column_region:{}, column_level:{}, "
            "column_sector:{}, type: {}, value: {}.".format(
                note_label,
                row_region_,
                row_level,
                row_sector_,
                column_region_,
                column_level,
                column_sector_,
                _type[shock],
                value[shock],
            )
        )

    return coeff, notes


def U_shock(instance, path, boolean, clusters, to_baseline):
    """Apply shocks to the split SUT use coefficients ``u``."""
    return _split_intermediate_shock(
        instance,
        path,
        boolean=boolean,
        clusters=clusters,
        coefficient_matrix=_ENUM.u,
        flow_matrix=_ENUM.U,
        output_matrix="Xa",
        row_level=_MASTER_INDEX["c"],
        column_level=_MASTER_INDEX["a"],
        sheet_name=_ENUM.u,
        note_label="u",
    )


def S_shock(instance, path, boolean, clusters, to_baseline):
    """Apply shocks to the split SUT supply coefficients ``s``."""
    return _split_intermediate_shock(
        instance,
        path,
        boolean=boolean,
        clusters=clusters,
        coefficient_matrix=_ENUM.s,
        flow_matrix=_ENUM.S,
        output_matrix="Xc",
        row_level=_MASTER_INDEX["a"],
        column_level=_MASTER_INDEX["c"],
        sheet_name=_ENUM.s,
        note_label="s",
    )


def _split_final_demand_shock(
    instance,
    path,
    *,
    boolean,
    clusters,
    flow_matrix,
    row_level,
    sheet_name,
    note_label,
):
    """Apply shocks to one split SUT final-demand block such as ``Ya`` or ``Yc``."""
    notes = []
    flow = _baseline_block(instance, flow_matrix)

    if not boolean:
        return flow, notes

    info = _read_shock_sheet(path, sheet_name, flow_matrix, str(flow_matrix))
    if info is None:
        return flow, notes

    if info.isnull().values.any():
        raise WrongInput(
            f"nans(empty cells) found in the shock file for '{sheet_name}'."
        )

    row_from = (
        SHOCK_FLAT_COLUMNS["activity_from"]
        if row_level == _MASTER_INDEX["a"]
        else SHOCK_FLAT_COLUMNS["commodity_from"]
    )
    row_region = _shock_column(info, SHOCK_FLAT_COLUMNS["region_from"])
    row_sector = _shock_column(info, row_from)
    column_region = _shock_column(info, SHOCK_FLAT_COLUMNS["region_to"])
    demand_category = _shock_column(info, SHOCK_FLAT_COLUMNS["category_to"])
    _type = _shock_column(info, SHOCK_FLAT_COLUMNS["type"], SHOCK_COLUMNS["type"])
    value = _shock_column(info, SHOCK_FLAT_COLUMNS["value"], SHOCK_COLUMNS["value"])

    for shock in range(len(info)):
        if _is_mix_type(_type[shock]):
            # Mix rows are collected and applied by the dedicated spec readers.
            continue
        row_region_ = check_replace_clusters(
            userValue=row_region[shock],
            dataValues=instance.get_index(_MASTER_INDEX["r"]),
            clusters=clusters.get(_MASTER_INDEX["r"]),
        )
        row_sector_ = check_replace_clusters(
            userValue=row_sector[shock],
            dataValues=instance.get_index(row_level),
            clusters=clusters.get(row_level),
        )
        column_region_ = check_replace_clusters(
            userValue=column_region[shock],
            dataValues=instance.get_index(_MASTER_INDEX["r"]),
            clusters=clusters.get(_MASTER_INDEX["r"]),
        )
        demand_category_ = check_replace_clusters(
            userValue=demand_category[shock],
            dataValues=instance.get_index(_MASTER_INDEX["n"]),
            clusters=clusters.get(_MASTER_INDEX["n"]),
        )

        row_key = _io_axis_key(flow.index, row_region_, row_level, row_sector_)
        col_key = _fd_axis_key(flow.columns, column_region_, demand_category_)

        flow = _apply_shock(flow, row_key, col_key, _type[shock], value[shock])

        notes.append(
            "Shock on {} implemented: row_region:{}, row_level:{}, row_sector:{}, "
            "column_region:{}, demand_category:{}, type:{}, value:{}.".format(
                note_label,
                row_region_,
                row_level,
                row_sector_,
                column_region_,
                demand_category_,
                _type[shock],
                value[shock],
            )
        )

    return flow, notes


def Ya_shock(instance, path, boolean, clusters, to_baseline):
    """Apply shocks to the split SUT final-demand block ``Ya``."""
    return _split_final_demand_shock(
        instance,
        path,
        boolean=boolean,
        clusters=clusters,
        flow_matrix="Ya",
        row_level=_MASTER_INDEX["a"],
        sheet_name="Ya",
        note_label="Ya",
    )


def Yc_shock(instance, path, boolean, clusters, to_baseline):
    """Apply shocks to the split SUT final-demand block ``Yc``."""
    return _split_final_demand_shock(
        instance,
        path,
        boolean=boolean,
        clusters=clusters,
        flow_matrix="Yc",
        row_level=_MASTER_INDEX["c"],
        sheet_name="Yc",
        note_label="Yc",
    )


def _split_factor_extension_shock(
    instance,
    path,
    *,
    boolean,
    clusters,
    coefficient_matrix,
    flow_matrix,
    output_matrix,
    row_code,
    column_level,
    sheet_name,
    note_label,
):
    """Apply shocks to one split SUT coefficient block such as ``va`` or ``ec``."""
    notes = []
    coeff = _baseline_block(instance, coefficient_matrix)

    if not boolean:
        return coeff, notes

    info = _read_shock_sheet(
        path, sheet_name, coefficient_matrix, str(coefficient_matrix)
    )
    if info is None:
        return coeff, notes

    flow = _baseline_block(instance, flow_matrix)
    output = _baseline_block(instance, output_matrix)

    if info.isnull().values.any():
        raise WrongInput(
            f"nans(empty cells) found in the shock file for '{sheet_name}'."
        )

    row_column = (
        SHOCK_FLAT_COLUMNS["factor_from"]
        if row_code == _MASTER_INDEX["f"]
        else SHOCK_FLAT_COLUMNS["satellite_from"]
    )
    column_to = (
        SHOCK_FLAT_COLUMNS["activity_to"]
        if column_level == _MASTER_INDEX["a"]
        else SHOCK_FLAT_COLUMNS["commodity_to"]
    )
    row_sector = _shock_column(info, row_column, SHOCK_COLUMNS["r_sec"])
    column_region = _shock_column(
        info, SHOCK_FLAT_COLUMNS["region_to"], SHOCK_COLUMNS["c_reg"]
    )
    column_sector = _shock_column(info, column_to, SHOCK_COLUMNS["c_sec"])
    _type = _shock_column(info, SHOCK_FLAT_COLUMNS["type"], SHOCK_COLUMNS["type"])
    value = _shock_column(info, SHOCK_FLAT_COLUMNS["value"], SHOCK_COLUMNS["value"])

    for shock in range(len(info)):
        row_sector_ = check_replace_clusters(
            userValue=row_sector[shock],
            dataValues=instance.get_index(row_code),
            clusters=clusters.get(row_code),
        )
        column_region_ = check_replace_clusters(
            userValue=column_region[shock],
            dataValues=instance.get_index(_MASTER_INDEX["r"]),
            clusters=clusters.get(_MASTER_INDEX["r"]),
        )
        column_sector_ = check_replace_clusters(
            userValue=column_sector[shock],
            dataValues=instance.get_index(column_level),
            clusters=clusters.get(column_level),
        )

        row_key = _account_axis_key(coeff.index, row_code, row_sector_)
        col_key = _io_axis_key(
            coeff.columns, column_region_, column_level, column_sector_
        )
        output_key = _io_axis_key(
            output.index, column_region_, column_level, column_sector_
        )

        coeff = _apply_shock(
            coeff,
            row_key,
            col_key,
            _type[shock],
            value[shock],
            flow=flow,
            output=output,
            output_key=output_key,
        )

        notes.append(
            "Shock on {} implemented: row_sector:{}, column_region:{}, "
            "column_level:{}, column_sector:{}, type:{}, value:{}.".format(
                note_label,
                row_sector_,
                column_region_,
                column_level,
                column_sector_,
                _type[shock],
                value[shock],
            )
        )

    return coeff, notes


def va_shock(instance, path, boolean, clusters, to_baseline):
    """Apply shocks to the split SUT value-added coefficients ``va``."""
    return _split_factor_extension_shock(
        instance,
        path,
        boolean=boolean,
        clusters=clusters,
        coefficient_matrix="va",
        flow_matrix="Va",
        output_matrix="Xa",
        row_code=_MASTER_INDEX["f"],
        column_level=_MASTER_INDEX["a"],
        sheet_name="va",
        note_label="va",
    )


def vc_shock(instance, path, boolean, clusters, to_baseline):
    """Apply shocks to the split SUT value-added coefficients ``vc``."""
    return _split_factor_extension_shock(
        instance,
        path,
        boolean=boolean,
        clusters=clusters,
        coefficient_matrix="vc",
        flow_matrix="Vc",
        output_matrix="Xc",
        row_code=_MASTER_INDEX["f"],
        column_level=_MASTER_INDEX["c"],
        sheet_name="vc",
        note_label="vc",
    )


def ea_shock(instance, path, boolean, clusters, to_baseline):
    """Apply shocks to the split SUT extension coefficients ``ea``."""
    return _split_factor_extension_shock(
        instance,
        path,
        boolean=boolean,
        clusters=clusters,
        coefficient_matrix="ea",
        flow_matrix="Ea",
        output_matrix="Xa",
        row_code=_MASTER_INDEX["k"],
        column_level=_MASTER_INDEX["a"],
        sheet_name="ea",
        note_label="ea",
    )


def ec_shock(instance, path, boolean, clusters, to_baseline):
    """Apply shocks to the split SUT extension coefficients ``ec``."""
    return _split_factor_extension_shock(
        instance,
        path,
        boolean=boolean,
        clusters=clusters,
        coefficient_matrix="ec",
        flow_matrix="Ec",
        output_matrix="Xc",
        row_code=_MASTER_INDEX["k"],
        column_level=_MASTER_INDEX["c"],
        sheet_name="ec",
        note_label="ec",
    )


def Z_shock(instance, path, boolean, clusters, to_baseline):
    """Apply shocks to the inter-industry coefficient matrix ``z``."""
    z = _baseline_block(instance, _ENUM.z)

    notes = []
    if not boolean:
        return z, notes

    Z = _baseline_block(instance, _ENUM.Z)
    X = _baseline_block(instance, _ENUM.X)
    info = _read_shock_sheet(
        path, _ENUM.z, _ENUM.Z, str(_ENUM.z).lower(), str(_ENUM.Z).upper()
    )
    if info is None:
        return z, notes

    row_region = _shock_column(
        info, SHOCK_FLAT_COLUMNS["region_from"], SHOCK_COLUMNS["r_reg"]
    )
    if instance.meta.table == "IOT":
        row_level = [_MASTER_INDEX["s"]] * len(info)
        row_sector = _shock_column(
            info, SHOCK_FLAT_COLUMNS["sector_from"], SHOCK_COLUMNS["r_sec"]
        )
        column_level = [_MASTER_INDEX["s"]] * len(info)
        column_sector = _shock_column(
            info, SHOCK_FLAT_COLUMNS["sector_to"], SHOCK_COLUMNS["c_sec"]
        )
    else:
        row_level = _shock_column(info, SHOCK_COLUMNS["r_lev"])
        row_sector = _shock_column(info, SHOCK_COLUMNS["r_sec"])
        column_level = _shock_column(info, SHOCK_COLUMNS["c_lev"])
        column_sector = _shock_column(info, SHOCK_COLUMNS["c_sec"])
    column_region = _shock_column(
        info, SHOCK_FLAT_COLUMNS["region_to"], SHOCK_COLUMNS["c_reg"]
    )
    _type = _shock_column(info, SHOCK_FLAT_COLUMNS["type"], SHOCK_COLUMNS["type"])
    value = _shock_column(info, SHOCK_FLAT_COLUMNS["value"], SHOCK_COLUMNS["value"])

    if info.isnull().values.any():
        raise WrongInput(f"nans(empty cells) found in the shock file for '{_ENUM.Z}'.")

    for shock in range(len(info)):
        if _is_mix_type(_type[shock]):
            # Mix rows are collected and applied by the dedicated spec readers.
            continue
        if nan_check(info, shock, _type[shock]):
            log_time(
                logger,
                "nan values found on row {} of {} shock sheet. No more shock is imported after row {}".format(
                    shock, _ENUM.Z, shock
                ),
                "warning",
            )
            break

        # Performing a full shock on the inputs
        row_region_ = check_replace_clusters(
            userValue=row_region[shock],
            dataValues=instance.get_index(_MASTER_INDEX["r"]),
            clusters=clusters.get(_MASTER_INDEX["r"]),
        )

        row_level_ = check_replace_clusters(
            userValue=row_level[shock],
            dataValues=(
                [_MASTER_INDEX["s"]]
                if instance.meta.table == "IOT"
                else [_MASTER_INDEX["a"], _MASTER_INDEX["c"]]
            ),
            clusters=None,
        )

        row_sector_ = check_replace_clusters(
            userValue=row_sector[shock],
            dataValues=instance.get_index(row_level_),
            clusters=clusters.get(row_level_),
        )

        column_region_ = check_replace_clusters(
            userValue=column_region[shock],
            dataValues=instance.get_index(_MASTER_INDEX["r"]),
            clusters=clusters.get(_MASTER_INDEX["r"]),
        )

        column_level_ = check_replace_clusters(
            userValue=column_level[shock],
            dataValues=(
                [_MASTER_INDEX["s"]]
                if instance.meta.table == "IOT"
                else [_MASTER_INDEX["a"], _MASTER_INDEX["c"]]
            ),
            clusters=None,
        )

        column_sector_ = check_replace_clusters(
            userValue=column_sector[shock],
            dataValues=instance.get_index(column_level_),
            clusters=clusters.get(column_level_),
        )

        row_key = _io_axis_key(Z.index, row_region_, row_level_, row_sector_)
        column_key = _io_axis_key(
            Z.columns, column_region_, column_level_, column_sector_
        )
        output_key = _io_axis_key(
            X.index, column_region_, column_level_, column_sector_
        )

        z = _apply_shock(
            z,
            row_key,
            column_key,
            _type[shock],
            value[shock],
            flow=Z,
            output=X,
            output_key=output_key,
        )

        notes.append(
            "Shock on z implemented: row_region_:{}, row_level_:{}, "
            "row_sector_:{}, column_region_:{}, column_level_:{} "
            "column_sector_:{}, type: {}, value: {}.".format(
                row_region_,
                row_level_,
                row_sector_,
                column_region_,
                column_level_,
                column_sector_,
                _type[shock],
                value[shock],
            )
        )

    return z, notes

"""Nonmutating national projections of the supported FIGARO-NAM ledger.

Source-specific routing belongs here, not in the general NAM account schema.
No balancing, trade allocation or change of valuation is performed.
"""

from copy import deepcopy

import numpy as np
import pandas as pd

from mario.internal.nam import _coo
from mario.log_exc.exceptions import DataMissing, NotImplementable, WrongInput
from mario.model.conventions import _MASTER_INDEX as MI
from mario.model.nam import NAM_BLOCKS


_IMPORT_ROWS = {"P7": "Imports P7", "P33": "Purchases abroad P33"}
_SETTLEMENT_ROWS = {"P7": "External settlement P7", "P33": "External settlement P33"}
_ASSET_DEMAND = {"fixed_asset": "P51G", "inventories": "P5M", "valuables": "P5M"}


class _NationalFlows:
    def __init__(self, nam, region, scenario):
        self.nam, self.region, self.scenario = nam, region, scenario
        self.schema = nam.nam_schema
        self.records = {}

    def read(self, name, *, imports=False):
        definition = NAM_BLOCKS[name]
        axes = {side: self.schema.accounts(definition[side]) for side in ("rows", "columns")}
        axes = {side: axis[axis.get_level_values("Region") == self.region] for side, axis in axes.items()}
        if not len(axes["rows"]) or not len(axes["columns"]):
            frame = pd.DataFrame(0., index=axes["rows"], columns=axes["columns"])
        else:
            try:
                frame = self.nam.get_block(name, self.scenario)
                self.records[name] = deepcopy(self.nam._state._resolve_block_record(name, self.scenario).metadata)
            except (KeyError, DataMissing) as exc:
                raise DataMissing(f"NAM-to-SUT requires {name} in scenario {self.scenario!r}.") from exc
            row_layout = ["Region", "origin_region", "imported_commodity", "Set", "Item"] if imports else ["Region", "Set", "Item"]
            if list(frame.index.names) != row_layout or list(frame.columns.names) != ["Region", "Set", "Item"]:
                raise NotImplementable(f"NAM-to-SUT does not support this native layout for {name}.")
            rows = np.asarray(frame.index.get_level_values("Region") == self.region)
            cols = np.asarray(frame.columns.get_level_values("Region") == self.region)
            values = _coo(frame)
            crossing = (rows[values.row] != cols[values.col]) & (values.data != 0)
            if crossing.any():
                raise NotImplementable(f"NAM-to-SUT cannot externalize cross-economy flows in {name}; select independent national ledgers.")
            frame = pd.DataFrame(_coo(frame).tocsr()[rows][:, cols].toarray(),
                                 index=frame.index[rows], columns=frame.columns[cols])
        if imports:
            frame = frame.groupby(level="Item", sort=False).sum()
            unknown = frame.index.difference(_IMPORT_ROWS)
            if len(unknown):
                raise NotImplementable(f"Unknown FIGARO import accounts in {name}: {unknown.tolist()}.")
            frame.index = frame.index.map(_IMPORT_ROWS)
        else:
            frame.index = frame.index.get_level_values("Item")
        frame.columns = frame.columns.get_level_values("Item")
        return frame

    def require_zero(self, name):
        if np.any(self.read(name).to_numpy() != 0):
            raise NotImplementable(f"NAM-to-SUT has no FIGARO projection for nonzero {name}; no flow was discarded.")

    def route(self, name, target, column_map, *, imports=False):
        frame = self.read(name, imports=imports)
        for column in frame.columns:
            destination = column_map.get(column)
            if destination is None:
                if np.any(frame[column].to_numpy() != 0):
                    raise NotImplementable(f"NAM-to-SUT cannot classify nonzero {name} column {column!r}.")
                continue
            target.loc[frame.index, destination] += frame[column]


def _axis(region, items, level):
    return pd.MultiIndex.from_tuples([(region, level, item) for item in items],
                                     names=[MI["r"], "Level", "Item"])


def _project_scenario(nam, region, scenario):
    read = _NationalFlows(nam, region, scenario)
    def items(key):
        return nam.get_index(key, region=region)
    activities, products, consumption = items("a"), items("c"), items("n")
    fd = [*consumption, "P51G", "P5M", "P6"]
    factors = [*items("f"), *items("t"), *_IMPORT_ROWS.values(), *_SETTLEMENT_ROWS.values()]
    if len(fd) != len(set(fd)) or len(factors) != len(set(factors)):
        raise WrongInput("NAM-to-SUT output labels collide with reserved FIGARO demand/import labels.")
    S = read.read("S").reindex(index=activities, columns=products)
    U = read.read("U").reindex(index=products, columns=activities)
    Yc, Ya = (pd.DataFrame(0., index=i, columns=fd) for i in (products, activities))
    Va, Vc, VY = (pd.DataFrame(0., index=factors, columns=i) for i in (activities, products, fd))
    for target, name, imports in ((Va, "Va_f", False), (Va, "TA", False),
                                  (Va, "MU", True), (Vc, "Vc_f", False), (Vc, "Vc_t", False)):
        frame = read.read(name, imports=imports)
        target.loc[frame.index, frame.columns] += frame
    for target, name, imports in ((Yc, "Yc_c", False), (Ya, "Ya_c", False),
                                  (VY, "VY_f", False), (VY, "TC", False), (VY, "MY", True)):
        read.route(name, target, dict(zip(consumption, consumption)), imports=imports)

    metadata = nam.nam_schema.item_metadata.get(region, {})
    assets = {item: _ASSET_DEMAND.get(metadata.get("nonfinancial_asset", {}).get(item, {}).get("kind"))
              for item in items("nf")}
    pools = {item: "P51G" if metadata.get("other", {}).get(item, {}).get("kind") == "investment_demand" else None
             for item in items("o")}
    for target, names in ((Yc, ("Yc_inv",)), (Ya, ("Ya_inv",)), (VY, ("Vinv_f", "Tinv"))):
        for name in names:
            read.route(name, target, assets)
    read.route("Minv", VY, assets, imports=True)
    for suffix in ("d", "f"):
        capital = dict.fromkeys(items("sc_" + suffix), "P5M")
        for target, name in ((Yc, "Yc_cap_"), (Ya, "Ya_cap_"), (VY, "Tcap_")):
            read.route(name + suffix, target, capital)
        read.route("Mcap_" + suffix, VY, capital, imports=True)
    for target, name in ((Yc, "C_o"), (Ya, "A_o"), (VY, "F_o"), (VY, "T_o")):
        read.route(name, target, pools)
    read.route("M_o", VY, pools, imports=True)
    for target, prefix in ((Yc, "Yc_"), (Ya, "Ya_")):
        read.route(prefix + "exp", target, dict.fromkeys(items("si_f"), "P6"))
        read.route(prefix + "exp_tr", target, dict.fromkeys(items("tr"), "P6"))
    settlement = read.read("TP_trade")
    for item in settlement.index:
        if item not in _SETTLEMENT_ROWS:
            raise NotImplementable(f"Unknown FIGARO external settlement account {item!r}.")
        VY.loc[_SETTLEMENT_ROWS[item], "P6"] += settlement.loc[item].sum()
    for name in ("O_c", "O_a"):
        read.require_zero(name)

    a, c, n = _axis(region, activities, MI["a"]), _axis(region, products, MI["c"]), _axis(region, fd, MI["n"])
    blocks = {"S": S.set_axis(a).set_axis(c, axis=1), "U": U.set_axis(c).set_axis(a, axis=1),
              "Ya": Ya.set_axis(a).set_axis(n, axis=1), "Yc": Yc.set_axis(c).set_axis(n, axis=1),
              "Va": Va.set_axis(a, axis=1), "Vc": Vc.set_axis(c, axis=1), "VY": VY.set_axis(n, axis=1)}
    for name, columns in (("Ea", a), ("Ec", c), ("EY", n)):
        blocks[name] = pd.DataFrame(0., index=["-"], columns=columns)
    activity_error = S.sum(axis=1) + Ya.sum(axis=1) - U.sum(axis=0) - Va.sum(axis=0)
    product_error = S.sum(axis=0) + Vc.sum(axis=0) - U.sum(axis=1) - Yc.sum(axis=1)
    checks = {"max_activity_imbalance": float(activity_error.abs().max()),
              "max_commodity_imbalance": float(product_error.abs().max())}
    # Financial and income-distribution blocks are outside a SUT. Only inputs
    # needed for this projection are read; unrelated missing accounts may remain.
    return blocks, factors, fd, checks, read.records


def convert(nam, *, region=None, tech_assumption=None):
    """Return one open national SUT, preserving every stored NAM scenario."""
    from mario.api.database import Database

    if "figaro_nam" not in nam.info or nam.nam_schema.representation != "use_imports":
        raise NotImplementable("NAM-to-SUT currently supports FIGARO-NAM with use_imports only; other sources need an explicit projection recipe.")
    regions = nam.get_index("Region")
    if region is None:
        if len(regions) != 1:
            raise WrongInput("NAM-to-SUT requires region= for a NAM containing several reference economies.")
        region = regions[0]
    if region not in regions:
        raise WrongInput(f"Unknown NAM reference economy: {region!r}.")
    if not nam.get_index("a", region=region) or not nam.get_index("c", region=region):
        raise NotImplementable("NAM-to-SUT requires declared activities and commodities.")
    matrices, checks, records = {}, {}, {}
    for scenario in nam.scenarios:
        matrices[scenario], factors, fd, checks[scenario], records[scenario] = _project_scenario(nam, region, scenario)
    activities, products = (nam.get_index(k, region=region) for k in ("a", "c"))
    indices = {key: {"main": values} for key, values in {
        "r": [region], "a": activities, "c": products, "s": [*activities, *products],
        "f": factors, "n": fd, "k": ["-"]}.items()}
    unit = f"{nam.nam_schema.currency} x {nam.nam_schema.scale:g}"
    units = {MI[key]: pd.DataFrame({"unit": [unit] * len(indices[key]["main"])}, index=indices[key]["main"])
             for key in ("a", "c", "f")}
    units[MI["k"]] = pd.DataFrame({"unit": ["None"]}, index=["-"])
    result = Database(table="SUT", name=f"{nam.meta.name} (SUT)", calc_all=False,
                      source=nam.meta.source, year=nam.meta.year, price=nam.meta.price,
                      license=nam.meta.license, version=nam.meta.version, tech_assumption=tech_assumption,
                      init_by_parsers={"matrices": matrices, "_indeces": indices, "units": units})
    audit = deepcopy(nam.info["figaro_nam"])
    if "sources" in audit:
        audit = next((entry for entry in audit["sources"] if region in entry.get("reference_economies", [])), {})
    result.info["nam_to_sut"] = {
        "recipe": "figaro_use_imports_v1", "reference_economy": region,
        "source_metadata": {key: getattr(nam.meta, key, None) for key in ("name", "source", "year", "price", "license", "version")},
        "units": deepcopy(nam.units), "source_audit": audit, "input_blocks": records,
        "checks": checks, "imports": "Aggregated by P7/P33; origin/product descriptors remain in the source NAM.",
        "external_settlements": "Separate VY rows at P6; no product or partner allocation inferred.",
        "valuation": "Source values retained; no balancing, revision or valuation bridge applied.",
    }
    for note in nam._state.metadata.history:
        result.meta._add_history(note)
    result.meta._add_history(f"Projected FIGARO-NAM {region} to an open national SUT; retained all scenarios and source values.")
    return result


def to_iot(sut, method):
    """Compose with the existing public SUT-to-IOT route for each scenario."""
    from mario.api.database import Database

    matrices = {}
    result = None
    for scenario in sut.scenarios:
        # Stage only this scenario, rather than copying every scenario N times.
        current = Database(table="SUT", name=sut.meta.name, source=sut.meta.source,
                           year=sut.meta.year, price=sut.meta.price, license=sut.meta.license,
                           version=sut.meta.version, tech_assumption=sut.meta.tech_assumption,
                           calc_all=False, notes=list(sut.meta._history),
                           init_by_parsers={
                               "matrices": {"baseline": {name: value.copy(deep=True) for name, value in sut.matrices[scenario].items()}},
                               "_indeces": deepcopy(sut._indeces), "units": deepcopy(sut.units),
                           })
        if scenario == "baseline":
            current.info = deepcopy(sut.info)
        current.to_iot(method, inplace=True)
        matrices[scenario] = dict(current.matrices["baseline"])
        if scenario == "baseline":
            result = current
    result.matrices = matrices
    result.meta.name = sut.meta.name.removesuffix(" (SUT)") + " (IOT)"
    result.info["nam_to_iot"] = {"method": method, "via": "NAM.to_sut -> SUT.to_iot", "scenarios": list(matrices)}
    result.meta._add_history(f"Converted every projected NAM scenario to IOT using Eurostat method {method}.")
    return result

"""Read native BONSAI b2 HIOT matrices without rerunning the system model."""

from contextlib import ExitStack
import pickle
import warnings

import numpy as np
import pandas as pd
from scipy import sparse

from mario.log_exc.exceptions import WrongInput
from mario.model.conventions import _MASTER_INDEX as MI
from mario.parsers.bonsai import (
    BonsaiLayout,
    _Bundle,
    _SparseEntries,
    _elementary_flows,
    _frame,
    _read_csv,
    _values,
)
from mario.utils import rename_index


TECHNOSPHERE = "extended_size_hiot.b2.pkl"
DEMAND = "final_demand.b2.csv"
EXTENSIONS = "total_elementary_flow_w_iLUC.csv"
REQUIRED = (TECHNOSPHERE, DEMAND)
ORIGIN = "Exio origin country code"
DESTINATION = "Exio destin. country code"
PRODUCT = "Exio prod code"
ACTIVITY = "Exio act code"
FLOW_COLUMNS = [ORIGIN, PRODUCT, DESTINATION, ACTIVITY, "unit", "Value"]
SOURCE = "BONSAI b2 HIOT; https://gitlab.com/bonsamurais/bonsai/build/hybrid_sut"


def _labels(index, count, filename):
    if isinstance(index, pd.MultiIndex) or not index.is_unique:
        raise WrongInput(f"BONSAI HIOT {filename} requires unique native flat labels.")
    parts = [label.split(";") if isinstance(label, str) else [] for label in index]
    if any(len(part) != count or not all(part) for part in parts):
        raise WrongInput(f"Invalid BONSAI HIOT labels in {filename}.")
    return parts


def _technosphere(bundle):
    # Native BONSAI publishes this sparse dataframe as a pickle. Read only this
    # named file; precomputed inverses/footprints and unrelated pickles are unused.
    with bundle.open(TECHNOSPHERE) as handle:
        try:
            frame = pd.read_pickle(handle)
        except (EOFError, pickle.UnpicklingError, ValueError, TypeError) as exc:
            raise WrongInput(
                f"Invalid native BONSAI HIOT file: {TECHNOSPHERE}."
            ) from exc
    if (
        not isinstance(frame, pd.DataFrame)
        or frame.empty
        or frame.shape[0] != frame.shape[1]
    ):
        raise WrongInput(
            "BONSAI HIOT technosphere must be a nonempty square DataFrame."
        )
    products = pd.DataFrame(
        _labels(frame.index, 3, TECHNOSPHERE), columns=["location", "name", "unit"]
    )
    activities = pd.DataFrame(
        _labels(frame.columns, 2, TECHNOSPHERE), columns=["location", "name"]
    )
    if products.duplicated(["location", "name"]).any() or activities.duplicated().any():
        raise WrongInput("BONSAI HIOT requires unique regional activity/product pairs.")
    if products.location.ne(activities.location).any():
        raise WrongInput(
            "BONSAI HIOT reference activity and product must share a region."
        )
    unit_table = products[["name", "unit"]].drop_duplicates()
    if unit_table.name.duplicated().any():
        raise WrongInput("Conflicting BONSAI HIOT sector units between regions.")
    sparse_columns = [isinstance(dtype, pd.SparseDtype) for dtype in frame.dtypes]
    if all(sparse_columns):
        if any(dtype.fill_value != 0 for dtype in frame.dtypes):
            raise WrongInput("BONSAI HIOT sparse matrix must use zero fill values.")
        matrix = frame.sparse.to_coo().tocsr().astype(float)
    elif any(sparse_columns):
        raise WrongInput("BONSAI HIOT matrix cannot mix sparse and dense columns.")
    else:
        try:
            matrix = sparse.csr_matrix(frame.to_numpy(dtype=float))
        except (TypeError, ValueError) as exc:
            raise WrongInput(
                "BONSAI HIOT technosphere must contain numeric values."
            ) from exc
    if not np.isfinite(matrix.data).all():
        raise WrongInput("Non-finite values in BONSAI HIOT technosphere.")
    output = matrix.diagonal()
    if np.any(output <= 0):
        raise WrongInput("BONSAI HIOT reference diagonal must be strictly positive.")
    return matrix, output, products, activities, unit_table.set_index("name")


def _final_demand(bundle, products, *, chunksize, unmatched):
    raw = pd.concat(
        list(_read_csv(bundle, DEMAND, None, chunksize=chunksize)),
        ignore_index=True,
    )
    missing_columns = set(FLOW_COLUMNS) - set(raw.columns)
    if missing_columns:
        raise WrongInput(
            f"Invalid BONSAI HIOT {DEMAND}: missing columns {sorted(missing_columns)}."
        )
    if raw.empty or raw[FLOW_COLUMNS[:-1]].eq("").any().any():
        raise WrongInput("Incomplete BONSAI HIOT final-demand identities or units.")
    values = _values(raw, "Value", DEMAND)
    nodes = raw[[DESTINATION, ACTIVITY]].drop_duplicates().reset_index(drop=True)
    nodes.columns = ["location", "name"]
    product_index = pd.MultiIndex.from_frame(products[["location", "name"]])
    rows = product_index.get_indexer(pd.MultiIndex.from_frame(raw[[ORIGIN, PRODUCT]]))
    cols = pd.MultiIndex.from_frame(nodes).get_indexer(
        pd.MultiIndex.from_frame(raw[[DESTINATION, ACTIVITY]])
    )
    missing = rows < 0
    omitted = raw.loc[missing].to_dict("records")
    if missing.any():
        message = (
            f"BONSAI HIOT: {int(missing.sum())} final-demand rows refer to products absent "
            "from the native HIOT and are omitted. Full rows are in the bonsai import report."
        )
        if unmatched == "raise":
            raise WrongInput(message)
        warnings.warn(message, UserWarning, stacklevel=3)
    keep = ~missing
    if (raw.loc[keep, "unit"].to_numpy() != products.unit.to_numpy()[rows[keep]]).any():
        raise WrongInput("Conflicting BONSAI HIOT product unit in final demand.")
    entries = _SparseEntries((len(products), len(nodes)))
    entries.add(rows[keep], cols[keep], values[keep])
    return entries.matrix(), nodes, omitted, len(raw)


def _reference_year(bundle, supplied, *, chunksize):
    if supplied is not None and (
        isinstance(supplied, bool)
        or not isinstance(supplied, (int, np.integer))
        or not 1 <= supplied <= 9999
    ):
        raise WrongInput("BONSAI HIOT year must be an integer reference year.")
    years = set()
    if EXTENSIONS in bundle.files:
        for chunk in _read_csv(bundle, EXTENSIONS, None, chunksize=chunksize):
            if "time" not in chunk:
                break
            values = pd.to_numeric(
                chunk.loc[chunk.time.ne(""), "time"], errors="coerce"
            )
            if (
                not np.isfinite(values).all()
                or (values % 1 != 0).any()
                or not values.between(1, 9999).all()
            ):
                raise WrongInput(
                    "Invalid BONSAI HIOT reference year in elementary flows."
                )
            years.update(values.astype(int))
    if len(years) > 1:
        raise WrongInput("BONSAI HIOT requires exactly one reference year.")
    if years and supplied is not None and supplied not in years:
        raise WrongInput("BONSAI HIOT year disagrees with elementary-flow time values.")
    if supplied is not None:
        return int(supplied)
    if years:
        return years.pop()
    raise WrongInput(
        "BONSAI HIOT reference year is unavailable; pass year= explicitly. "
        "The release directory date is not the reference year."
    )


def parse_bonsai_hiot(
    path,
    *,
    year=None,
    extensions=True,
    unmatched_extensions="warn",
    unmatched_final_demand="warn",
    chunksize=100_000,
):
    """Read native b2 exports, retaining the exact net-supply system.

    Only load trusted BONSAI pickle exports. All other input tables are CSVs.
    The diagonal defines net reference production; self consumption already
    netted into it cannot be recovered from the native technosphere alone.
    """
    if not isinstance(chunksize, int) or isinstance(chunksize, bool) or chunksize < 1:
        raise WrongInput("BONSAI chunksize must be a positive integer.")
    if not isinstance(extensions, bool):
        raise WrongInput("BONSAI extensions must be True or False.")
    for option, value in (
        ("unmatched_extensions", unmatched_extensions),
        ("unmatched_final_demand", unmatched_final_demand),
    ):
        if value not in ("warn", "raise"):
            raise WrongInput(f"BONSAI {option} must be 'warn' or 'raise'.")
    with ExitStack() as stack:
        bundle = _Bundle(path, stack, required=REQUIRED, label="HIOT b2")
        reference_year = _reference_year(bundle, year, chunksize=chunksize)
        t, q, products, activities, sector_units = _technosphere(bundle)
        y, final_nodes, omitted, demand_rows = _final_demand(
            bundle,
            products,
            chunksize=chunksize,
            unmatched=unmatched_final_demand,
        )
        k, satellite_units, e, ey, report = _elementary_flows(
            bundle,
            {"a": activities, "n": final_nodes},
            enabled=extensions,
            unmatched=unmatched_extensions,
            filename=EXTENSIONS,
        )

    sectors = pd.MultiIndex.from_arrays(
        [products.location, [MI["s"]] * len(products), products["name"]]
    )
    demand_axis = pd.MultiIndex.from_arrays(
        [final_nodes.location, [MI["n"]] * len(final_nodes), final_nodes["name"]]
    )
    # For any positive reference scaling Q, T = (I-z) Q. Choosing its native
    # diagonal yields Z = Q-T, e = E/Q and exactly f = e (I-z)^-1 = E T^-1.
    z = (sparse.diags(q) - t).tocsr()
    z.eliminate_zeros()
    residual = np.asarray(t.sum(axis=1) - y.sum(axis=1)).ravel()
    blocks = {
        "Z": _frame(z, sectors, sectors),
        "Y": _frame(y, sectors, demand_axis),
        "E": _frame(
            e if e is not None else sparse.csr_matrix((len(k), len(products))),
            k,
            sectors,
        ),
        "EY": _frame(
            ey if ey is not None else sparse.csr_matrix((len(k), len(final_nodes))),
            k,
            demand_axis,
        ),
        "V": _frame(sparse.csr_matrix((1, len(products))), pd.Index(["-"]), sectors),
        "VY": _frame(
            sparse.csr_matrix((1, len(final_nodes))), pd.Index(["-"]), demand_axis
        ),
        "X": pd.DataFrame(q, index=sectors, columns=["production"]),
    }
    rename_index(blocks)
    sector_codes = list(dict.fromkeys(products["name"]))
    indexes = {
        "r": {"main": list(dict.fromkeys([*products.location, *final_nodes.location]))},
        "s": {"main": sector_codes},
        "n": {"main": list(dict.fromkeys(final_nodes["name"]))},
        "k": {"main": list(k)},
        "f": {"main": ["-"]},
    }
    units = {
        MI["s"]: sector_units.reindex(sector_codes),
        MI["k"]: satellite_units,
        MI["f"]: pd.DataFrame({"unit": ["None"]}, index=["-"]),
    }
    references = products.rename(columns={"name": "product"}).assign(
        activity=activities["name"], production=q
    )
    report.update(
        {
            "path": str(bundle.path),
            "reference_year": reference_year,
            "table": "IOT",
            "variant": "b2",
            "files": list(REQUIRED) + ([EXTENSIONS] if extensions else []),
            "economic_flows": {
                TECHNOSPHERE: {"shape": t.shape, "nonzero_entries": t.nnz},
                DEMAND: {"rows": demand_rows},
            },
            "reference_products": references.to_dict("records"),
            "unmatched_final_demand": omitted,
            "output_convention": "native technosphere diagonal (net reference production); Z = diag(X) - T",
            "product_balance": {
                "max_absolute_residual": float(np.abs(residual).max()),
                "nonzero_residuals": int(np.count_nonzero(residual)),
            },
        }
    )
    notes = (
        "BONSAI b2 HIOT: native final technosphere imported with Stone substitution, iLUC and capital; no HSUT conversion is performed.",
        "BONSAI HIOT: native product sectors, regional memberships, hybrid units and signed substitution credits retained.",
        "BONSAI HIOT: X is the native technosphere diagonal (net reference production), not Z/Y row sums. Z = diag(X)-T preserves the original system exactly; source imbalance is reported without balancing.",
        "BONSAI HIOT: value added is unavailable; V/VY are zero placeholders. Gross reference supply and self consumption cannot be recovered separately from the native matrix.",
        f"BONSAI HIOT: {len(omitted)} unmatched final-demand rows omitted; full diagnostics retained in the import report.",
        f"BONSAI HIOT: elementary flows {'loaded from ' + EXTENSIONS if extensions else 'not loaded; E/EY are zero placeholders'}.",
    )
    return (
        {"baseline": blocks},
        indexes,
        units,
        BonsaiLayout(bundle.path, reference_year, notes, report, SOURCE),
    )

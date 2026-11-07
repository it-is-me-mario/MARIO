"""Impute recipes for producers activated by a supply-mix update.

All weights and sourcing patterns refer to the scenario before the update.
Only individual recipe vectors are dense; full sparse blocks stay sparse.
"""

from collections.abc import Mapping

import numpy as np
import pandas as pd
from scipy import sparse

from mario.compute.helpers import dense_values, sum_rows, _is_sparse_backed_dataframe
from mario.log_exc.exceptions import WrongInput
from mario.model.conventions import _MASTER_INDEX


def stored_outputs(database, scenario):
    """Keep flow-based production weights before resetting to coefficients."""
    result = {}
    plans = (
        {"Xa": ("S", "Ya"), "Xc": ("U", "Yc")}
        if database.table_type == "SUT"
        else {"X": ("Z", "Y")}
    )
    for name, (flow, demand) in plans.items():
        if database.has_matrix(name, scenario=scenario):
            result[name] = database.get_block_as_pandas(name, scenario).iloc[:, 0].copy()
        elif database.has_matrix(flow, scenario=scenario):
            total = sum_rows(database.get_block_as_pandas(flow, scenario))
            if database.has_matrix(demand, scenario=scenario):
                total = total + sum_rows(database.get_block_as_pandas(demand, scenario))
            result[name] = total
    return result


class SupplyRecipeFiller:
    """Prepare missing columns without mutating the source scenario."""

    def __init__(self, database, scenario, recipe_regions, outputs):
        self.database = database
        self.scenario = scenario
        self.selection = recipe_regions
        self.outputs = outputs
        self.frames = {}
        self.arrays = {}
        self.changes = {}
        self.sourcing = {}
        self.records = []
        self.producer_choices = {}
        self.regions = set(database.get_index(_MASTER_INDEX["r"]))
        if isinstance(recipe_regions, Mapping):
            for key, value in recipe_regions.items():
                if not isinstance(key, tuple) or len(key) != 2 or key[0] not in self.regions:
                    raise WrongInput("recipe_regions keys must be (region, item) pairs.")
                self._validate_selection(value)
        else:
            self._validate_selection(recipe_regions)

    def _validate_selection(self, value):
        if value is None or isinstance(value, str) and value in {"global", "prompt"}:
            return
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, (list, tuple)) or not value:
            raise WrongInput("recipe_regions must select a region, a non-empty list, 'global', or 'prompt'.")
        if any(not isinstance(region, str) or region not in self.regions for region in value):
            raise WrongInput(f"recipe_regions references unknown regions: {value!r}")

    def frame(self, name):
        if name not in self.frames:
            self.frames[name] = self.database.get_block_as_pandas(name, self.scenario)
        return self.frames[name]

    def array(self, name):
        if name not in self.arrays:
            frame = self.frame(name)
            self.arrays[name] = (
                frame.sparse.to_coo().tocsc()
                if _is_sparse_backed_dataframe(frame)
                else sparse.csc_matrix(frame.to_numpy(dtype=float))
            )
            self.arrays[name].eliminate_zeros()
        return self.arrays[name]

    def output(self, name):
        if name not in self.outputs:
            # Resolving output can materialize derived blocks. Restore the
            # coefficient-only source afterwards, including on failed solves.
            stored = dict(self.database.matrices[self.scenario])
            try:
                self.outputs[name] = self.database.query(name, scenarios=self.scenario).iloc[:, 0].copy()
            finally:
                self.database.matrices[self.scenario] = stored
        return self.outputs[name]

    def empty_column(self, name, key):
        frame = self.frame(name)
        position = frame.columns.get_loc(key)
        if not _is_sparse_backed_dataframe(frame):
            return not np.any(frame.iloc[:, position].to_numpy())
        return self.array(name).indptr[position] == self.array(name).indptr[position + 1]

    def selection_for(self, key, selection_key=None):
        selected = self.selection
        if isinstance(selected, Mapping):
            selected = selected.get((key[0], key[-1]), selected.get(selection_key))
        return selected

    def donors(self, name, key, *, selection_key=None):
        region, _, item = key
        frame = self.frame(name)
        production = self.output("X" if name == "z" else "Xa" if name == "u" else "Xc")
        available = [
            column for column in frame.columns
            if column[-1] == item and column[0] != region
            and np.isfinite(production.loc[column]) and production.loc[column] > 0
        ]
        if name == "s":
            available = [column for column in available if not self.empty_column(name, column)]
        available_regions = [column[0] for column in available]
        selected = self.selection_for(key, selection_key)
        if isinstance(selected, str) and selected == "prompt":
            try:
                answer = input(
                    f"Recipe for {region!r}, {item!r}. Available donors: "
                    f"{', '.join(available_regions)}. Enter regions separated by commas "
                    "or press Enter for global: "
                ).strip()
            except (EOFError, OSError) as exc:
                raise WrongInput(
                    "Recipe selection needs interactive input; pass explicit recipe_regions instead."
                ) from exc
            selected = answer.split(",") if answer and answer != "global" else None
            if selected is not None:
                selected = [value.strip() for value in selected]
        if selected is not None and not (isinstance(selected, str) and selected == "global"):
            requested = [selected] if isinstance(selected, str) else list(selected)
            unavailable = set(requested) - set(available_regions)
            if unavailable:
                raise WrongInput(f"No active recipe donors for {key!r} in regions {sorted(unavailable)}.")
            available = [column for column in available if column[0] in requested]
        if not available:
            raise WrongInput(
                f"No active recipe donors for {key!r}. Supply a recipe manually or "
                "pass fill_missing_recipes=False to retain empty columns."
            )
        weights = np.array([production.loc[column] for column in available], dtype=float)
        weights /= weights.sum()
        self.records.append((key, [column[0] for column in available]))
        return frame.columns.get_indexer(available), weights

    def average(self, name, positions, weights):
        return np.asarray(self.array(name)[:, positions] @ weights).reshape(-1)

    def put(self, name, key, values):
        self.changes.setdefault(name, {})[self.frame(name).columns.get_loc(key)] = values

    def extensions(self, names, key, positions, weights):
        for name in names:
            if self.empty_column(name, key):
                self.put(name, key, self.average(name, positions, weights))

    def regionalize(self, name, region, recipe):
        frame = self.frame(name)
        groups, labels = pd.factorize(frame.index.droplevel(0), sort=False)
        totals = np.bincount(groups, weights=recipe, minlength=len(labels))
        if (name, region) not in self.sourcing:
            columns = frame.columns.get_level_values(0) == region
            output = self.output("X" if name == "z" else "Xa")
            purchases = np.asarray(
                self.array(name)[:, columns] @ dense_values(output.reindex(frame.columns[columns]))
            ).reshape(-1)
            demand = self.frame("Y" if name == "z" else "Yc")
            demand_columns = demand.columns.get_level_values(0) == region
            if demand_columns.any():
                purchases += dense_values(sum_rows(demand.loc[:, demand_columns]))
            self.sourcing[name, region] = np.maximum(purchases, 0.0)
        purchases = self.sourcing[name, region]
        purchases_total = np.bincount(groups, weights=purchases, minlength=len(labels))
        # With no purchases of an input, use the selected donors' origin split.
        fallback = np.abs(recipe)
        fallback_total = np.bincount(groups, weights=fallback, minlength=len(labels))
        shares = np.divide(
            purchases, purchases_total[groups], out=np.zeros_like(recipe),
            where=purchases_total[groups] > 0,
        )
        missing = purchases_total[groups] == 0
        shares[missing] = np.divide(
            fallback[missing], fallback_total[groups[missing]],
            out=np.zeros(np.count_nonzero(missing)), where=fallback_total[groups[missing]] > 0,
        )
        return totals[groups] * shares

    def producer(self, name, key, *, selection_key=None):
        selected = self.selection_for(key, selection_key)
        if selected is None or isinstance(selected, str) and selected == "global":
            choice = None
        elif isinstance(selected, str) and selected == "prompt":
            choice = "prompt"
        else:
            choice = tuple(sorted(set([selected] if isinstance(selected, str) else selected)))
        if key in self._repaired_producers:
            if choice != self.producer_choices[key]:
                raise WrongInput(
                    f"Conflicting commodity donor selections for activity {key!r}; "
                    "pass an explicit activity override in recipe_regions."
                )
            return
        if not self.empty_column(name, key):
            return
        output = self.output("X" if name == "z" else "Xa")
        if output.loc[key] > 0:
            return
        positions, weights = self.donors(name, key, selection_key=selection_key)
        recipe = self.average(name, positions, weights)
        self.put(name, key, self.regionalize(name, key[0], recipe))
        self.extensions(("e", "v") if name == "z" else ("ea", "va"), key, positions, weights)
        self._repaired_producers.add(key)
        self.producer_choices[key] = choice

    def commodity(self, key):
        if self.output("Xc").loc[key] > 0:
            return
        s = self.frame("s")
        column = self.array("s")[:, s.columns.get_loc(key)].toarray().ravel()
        positions, weights = self.donors("s", key)
        if self.empty_column("s", key):
            recipe = self.average("s", positions, weights)
            totals = pd.Series(recipe, index=s.index.get_level_values(-1)).groupby(level=0).sum()
            column = np.zeros(len(s))
            for item, value in totals.items():
                if value == 0:
                    continue
                target = (key[0], s.index.get_level_values(1)[0], item)
                if target not in s.index:
                    raise WrongInput(
                        f"Cannot regionalize supply recipe for {key!r}: activity {target!r} is absent."
                    )
                column[s.index.get_loc(target)] = value
            self.put("s", key, column)
        self.extensions(("ec", "vc"), key, positions, weights)
        for position in np.flatnonzero(column):
            self.producer("u", s.index[position], selection_key=(key[0], key[-1]))

    def fill(self, row_level, shares, blocks):
        self._repaired_producers = set()
        for region, weights in shares.items():
            for item, weight in weights.items():
                if weight <= 0:
                    continue
                key = (region, row_level, item)
                if self.database.table_type == "IOT":
                    producer_block = "z"
                elif row_level == _MASTER_INDEX["a"]:
                    producer_block = "u"
                else:
                    producer_block = None
                if producer_block and not self.empty_column(producer_block, key):
                    continue
                # A nonzero coefficient pointing to a zero-output buyer does
                # not yet activate production. Final demand can do so alone.
                demand = 0.0
                for name, frame in blocks.items():
                    row = dense_values(frame.loc[[key], :]).ravel()
                    if not np.any(row):
                        continue
                    if name in {"Y", "Yc"}:
                        demand += row.sum()
                    else:
                        output_name = "X" if name == "z" else "Xa" if name == "u" else "Xc"
                        demand += row @ dense_values(self.output(output_name).reindex(frame.columns))
                if demand <= 0:
                    continue
                if self.database.table_type == "IOT":
                    self.producer("z", key)
                elif row_level == _MASTER_INDEX["a"]:
                    self.producer("u", key)
                else:
                    self.commodity(key)
        return self.changes

    def apply(self, blocks):
        """Rebuild changed columns while retaining storage, precision and axes."""
        for name, replacements in self.changes.items():
            frame = blocks.get(name, self.frame(name))
            if _is_sparse_backed_dataframe(frame):
                original = frame.sparse.to_coo()
                keep = ~np.isin(original.col, list(replacements))
                rows, cols, data = [original.row[keep]], [original.col[keep]], [original.data[keep]]
                for position, values in replacements.items():
                    nonzero = np.flatnonzero(values)
                    rows.append(nonzero)
                    cols.append(np.full(len(nonzero), position))
                    data.append(values[nonzero])
                updated = sparse.coo_matrix(
                    (np.concatenate(data), (np.concatenate(rows), np.concatenate(cols))),
                    shape=frame.shape,
                )
                result = pd.DataFrame.sparse.from_spmatrix(
                    updated, index=frame.index, columns=frame.columns
                ).fillna(0.0)
                blocks[name] = result.astype(frame.dtypes.to_dict())
            else:
                result = frame.copy()
                for position, values in replacements.items():
                    result.iloc[:, position] = values
                blocks[name] = result
        return blocks

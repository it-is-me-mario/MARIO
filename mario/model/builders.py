"""Helpers for building empty canonical MARIO matrices and templates."""

from __future__ import annotations

from pathlib import Path
import re
import warnings

import pandas as pd

from mario.log_exc.exceptions import WrongInput
from mario.model.conventions import TABLE_LEVELS, TABLE_UNIT_LEVELS
from mario.model.conventions import _MASTER_INDEX
from mario.settings.settings import IndexAliases


class MatrixBuilder:
    """Create empty canonical matrices from a table kind and level values."""

    def __init__(self, table, levels, sort=False):
        """Store table metadata used to generate empty block skeletons."""
        self.table = table
        self.levels = levels

    @property
    def Z(self):
        """Return an empty transaction matrix with canonical MARIO axes."""
        region = _MASTER_INDEX.r
        if self.table == "IOT":
            sector = _MASTER_INDEX.s
            index = pd.MultiIndex.from_product(
                [self.levels[region], [sector], self.levels[sector]]
            )

        elif self.table == "SUT":
            activity = _MASTER_INDEX.a
            commodity = _MASTER_INDEX.c

            idx_0 = pd.MultiIndex.from_product(
                [self.levels[region], [activity], self.levels[activity]]
            )

            idx_1 = pd.MultiIndex.from_product(
                [self.levels[region], [commodity], self.levels[commodity]]
            )

            index = idx_0.append(idx_1)

        df = pd.DataFrame(0, index=index, columns=index)

        return df

    @property
    def Y(self):
        """Return an empty final-demand matrix aligned with the current table."""
        region = _MASTER_INDEX.r
        consumption = _MASTER_INDEX.n

        index = self.Z.index
        columns = pd.MultiIndex.from_product(
            [self.levels[region], [consumption], self.levels[consumption]]
        )

        df = pd.DataFrame(0, index=index, columns=columns)

        return df

    @property
    def E(self):
        """Return an empty satellite extension matrix."""
        region = _MASTER_INDEX.r
        satellite = _MASTER_INDEX.k

        columns = self.Z.index
        index = pd.Index(self.levels[satellite])

        df = pd.DataFrame(0, index=index, columns=columns)

        return df

    @property
    def V(self):
        """Return an empty value-added matrix."""
        region = _MASTER_INDEX.r
        factor = _MASTER_INDEX.f

        columns = self.Z.index
        index = pd.Index(self.levels[factor])

        df = pd.DataFrame(0, index=index, columns=columns)

        return df

    @property
    def EY(self):
        """Return an empty final-demand extension matrix."""
        index = self.E.index
        columns = self.Y.columns

        df = pd.DataFrame(0, index=index, columns=columns)

        return df

    @property
    def VY(self):
        """Return an empty final-demand factor matrix."""
        index = self.V.index
        columns = self.Y.columns

        df = pd.DataFrame(0, index=index, columns=columns)

        return df

    @property
    def X(self):
        """Return an empty production vector."""
        index = self.Z.index
        columns = ["production"]

        df = pd.DataFrame(0, index=index, columns=columns)

        return df


class DataTemplate:
    """Build an IO or SUT table from tabular data inputs."""

    def __init__(self, table) -> None:
        """Initialize a tabular template builder for one table kind."""
        warnings.warn(
            "DataTemplate is deprecated and will be removed in a future MARIO release. "
            "Use mario.write_parse_template(...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        if table not in TABLE_LEVELS:
            raise WrongInput("Only SUT and IOT are acceptable table types.")

        self._table = table.upper()

        # Setting attributes of the table as a nested dict
        self._levels = {}
        self._units = {}

    def get_template_excel(self, path: str):
        """Generates an excel templated for the table type to be filled

        Parameters
        ----------
        path : path
            path to the excel file
        """
        write_template_definition(path, table=self._table)

    def read_template(self, io):
        """reads the tabluar data and generates the IO, SUT tables

        Parameters
        ----------
        io : str, pd.DataFrame
            the path to the excel file or pd.DataFrame

        """
        self._levels, self._units = _read_template_definition(io, self._table)

    def _get_data_format(self):
        """Build the empty tabular format expected by ``read_template``."""
        return _definition_template_frame(self._table)

    @property
    def levels(self):
        """Return the logical levels required by the current table kind."""
        return [*TABLE_LEVELS[self._table]]

    @property
    def unit_levels(self):
        """Return the levels that must carry unit metadata."""
        return [*TABLE_UNIT_LEVELS[self._table]]

    @property
    def non_unit_levels(self):
        """Return the levels that only require value lists."""
        non_unit_levels = []

        for i in self.levels:
            if i not in self.unit_levels:
                non_unit_levels.append(i)

        return non_unit_levels

    def to_Database(self):
        """Generates the mario.Database object

        Returns
        -------
        mario.Database
            the generated Database object based on the tabular data
        """
        from mario.api.database import Database

        matrix_builder = MatrixBuilder(self._table, self._levels)

        return Database(
            table=self._table,
            Z=matrix_builder.Z,
            E=matrix_builder.E,
            V=matrix_builder.V,
            Y=matrix_builder.Y,
            EY=matrix_builder.EY,
            VY=matrix_builder.VY,
            units=self._units,
        )

    def to_excel(self, path, flows=True, coefficients=False):
        """Writes the data into emtpy database through mario.Database object

        Parameters
        ----------
        path : str
            path to save the excel of the Database
        flows : bool, optional
            if True, generates flow table, by default True
        coefficients : bool, optional
            if True, generates the coefficients table, by default False
        """

        self.to_Database().to_excel(path, flows=flows, coefficients=coefficients)


def _normalize_set_token(value) -> str:
    """Collapse one user-facing set token to a comparison-friendly key."""
    return re.sub(r"[^0-9a-z]+", "", str(value).strip().lower())


def _display_set_name(set_name: str) -> str:
    """Return the user-facing label used in definition workbooks."""
    if set_name == "Consumption category":
        return "Final demand"
    return set_name


def _definition_template_frame(table: str) -> pd.DataFrame:
    """Return the empty workbook frame used to define sets and units."""
    idx_0 = pd.MultiIndex.from_product(
        [
            [
                _display_set_name(set_name)
                for set_name in TABLE_LEVELS[table]
                if set_name not in TABLE_UNIT_LEVELS[table]
            ],
            ["value"],
        ]
    )
    idx_1 = pd.MultiIndex.from_product(
        [[_display_set_name(set_name) for set_name in TABLE_UNIT_LEVELS[table]], ["value", "unit"]]
    )
    return pd.DataFrame(columns=idx_0.append(idx_1))


def _definition_column_lookup(frame: pd.DataFrame, table: str) -> dict[str, object]:
    """Return one canonical-level lookup for workbook definition columns."""
    lookup: dict[str, object] = {}
    for label in frame.columns.unique(0):
        try:
            lookup[_resolve_set_name(table, label)] = label
        except WrongInput:
            continue
    return lookup


def _definition_value_rows(
    frame: pd.DataFrame,
    *,
    level: str,
    table: str,
    column_lookup: dict[str, object],
) -> pd.DataFrame:
    """Return cleaned rows for one level in a definition workbook."""
    if level not in column_lookup:
        raise WrongInput(f"{level} info not found in the template.")

    values = frame[column_lookup[level]].copy()
    if "value" not in values.columns:
        raise WrongInput(f"{level} info not found in the template.")

    values = values.loc[values["value"].notna()].copy()
    if values.empty:
        raise WrongInput(f"No value given for {level}.")

    values["value"] = values["value"].map(lambda item: str(item).strip())
    values = values.loc[values["value"] != ""]
    values = values.drop_duplicates(subset=["value"], keep="first")
    if values.empty:
        raise WrongInput(f"No value given for {level}.")
    return values


def _read_template_definition(io, table: str) -> tuple[dict[str, list[str]], dict[str, pd.DataFrame]]:
    """Read a definition workbook or frame into normalized sets and units."""
    if isinstance(io, (str, Path)):
        template = pd.read_excel(io, sheet_name="definition", header=[0, 1])
    elif isinstance(io, pd.DataFrame):
        template = io
    else:
        raise ValueError("Only an excel file path or pd.DataFrame are acceptable.")

    if isinstance(template.columns, pd.MultiIndex):
        mask = ~template.columns.get_level_values(0).map(str).str.startswith("Unnamed:")
        template = template.loc[:, mask]

    column_lookup = _definition_column_lookup(template, table)
    levels: dict[str, list[str]] = {}
    units: dict[str, pd.DataFrame] = {}
    for level in TABLE_LEVELS[table]:
        rows = _definition_value_rows(
            template,
            level=level,
            table=table,
            column_lookup=column_lookup,
        )
        levels[level] = rows["value"].tolist()
        if level in TABLE_UNIT_LEVELS[table]:
            if "unit" not in rows.columns or rows["unit"].isna().any():
                raise WrongInput(
                    f"Possible issues with NaN values found for level {level}. Each item for this level should have a unit of measure."
                )
            units[level] = pd.DataFrame(
                {"unit": rows["unit"].tolist()},
                index=pd.Index(rows["value"].tolist(), name="Item"),
            )
    return levels, units


def write_template_definition(path: str, *, table: str):
    """Write the workbook used to define sets and units before data entry."""
    normalized_table = str(table).upper()
    if normalized_table not in TABLE_LEVELS:
        raise WrongInput("Only SUT and IOT are acceptable table types.")

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    instructions = pd.DataFrame(
        [
            [
                "Fill sheet 'definition' with your sets and, where required, the corresponding units."
            ],
            [
                "Then generate the data-entry workbook with "
                f"mario.write_parse_template(path='custom_{normalized_table.lower()}.xlsx', table='{normalized_table}', definition='{output.name}')."
            ],
        ]
    )
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        _definition_template_frame(normalized_table).to_excel(
            writer,
            sheet_name="definition",
        )
        instructions.to_excel(writer, sheet_name="instructions", header=False, index=False)
    return str(output)


def _resolve_set_name(table: str, value) -> str:
    """Resolve one set label from an exact label, alias or short code."""
    if value in TABLE_LEVELS[table]:
        return value

    aliases = {}
    alias_settings = IndexAliases()
    for set_name, code in TABLE_LEVELS[table].items():
        aliases[_normalize_set_token(set_name)] = set_name
        aliases[_normalize_set_token(code)] = set_name
        for alias in alias_settings[code]:
            aliases[_normalize_set_token(alias)] = set_name

    resolved = aliases.get(_normalize_set_token(value))
    if resolved is None:
        raise WrongInput(f"{value!r} is not a valid set for {table}. Accepted sets are {list(TABLE_LEVELS[table])}.")
    return resolved


def _normalize_items(values, *, set_name: str) -> list[str]:
    """Normalize one user-provided set payload to a non-empty string list."""
    if isinstance(values, pd.Index):
        items = values.tolist()
    elif isinstance(values, pd.Series):
        items = values.tolist()
    elif isinstance(values, (list, tuple, set)):
        items = list(values)
    else:
        raise WrongInput(f"{set_name} should be provided as a list-like payload.")

    normalized: list[str] = []
    seen = set()
    for item in items:
        token = str(item).strip()
        if not token:
            continue
        marker = token.casefold()
        if marker not in seen:
            seen.add(marker)
            normalized.append(token)
    if not normalized:
        raise WrongInput(f"{set_name} should contain at least one item.")
    return normalized


def _normalize_units_payload(table: str, levels: dict[str, list[str]], units) -> dict[str, pd.DataFrame]:
    """Normalize the user-provided unit payload to MARIO unit dataframes."""
    if not isinstance(units, dict):
        raise WrongInput("units should be a dictionary keyed by set names.")

    normalized_units: dict[str, pd.DataFrame] = {}
    raw_lookup = {_resolve_set_name(table, key): value for key, value in units.items()}
    for set_name in TABLE_UNIT_LEVELS[table]:
        if set_name not in raw_lookup:
            raise WrongInput(f"Missing units for {set_name!r}.")

        payload = raw_lookup[set_name]
        items = levels[set_name]
        if isinstance(payload, str):
            frame = pd.DataFrame({"unit": [payload] * len(items)}, index=pd.Index(items, name="Item"))
        elif isinstance(payload, pd.Series):
            series = payload.copy()
            series.index = series.index.map(str)
            missing = [item for item in items if item not in series.index]
            if missing:
                raise WrongInput(f"Units for {set_name!r} are missing items {missing}.")
            frame = pd.DataFrame({"unit": [series.loc[item] for item in items]}, index=pd.Index(items, name="Item"))
        elif isinstance(payload, pd.DataFrame):
            if payload.empty or payload.shape[1] == 0:
                raise WrongInput(f"The units dataframe for {set_name!r} is empty.")
            series = payload.iloc[:, 0].copy()
            series.index = series.index.map(str)
            missing = [item for item in items if item not in series.index]
            if missing:
                raise WrongInput(f"Units for {set_name!r} are missing items {missing}.")
            frame = pd.DataFrame({"unit": [series.loc[item] for item in items]}, index=pd.Index(items, name="Item"))
        elif isinstance(payload, dict):
            missing = [item for item in items if item not in payload]
            if missing:
                raise WrongInput(f"Units for {set_name!r} are missing items {missing}.")
            frame = pd.DataFrame({"unit": [payload[item] for item in items]}, index=pd.Index(items, name="Item"))
        else:
            raise WrongInput(
                f"Units for {set_name!r} should be given as one string, dict, Series, or DataFrame."
            )
        normalized_units[set_name] = frame
    return normalized_units


def _normalize_template_levels(table: str, sets) -> dict[str, list[str]]:
    """Normalize user-provided sets to canonical MARIO level names."""
    if not isinstance(sets, dict):
        raise WrongInput("sets should be a dictionary keyed by set names.")

    levels = {_resolve_set_name(table, key): _normalize_items(value, set_name=_resolve_set_name(table, key)) for key, value in sets.items()}
    required = list(TABLE_LEVELS[table])
    missing = [set_name for set_name in required if set_name not in levels]
    if missing:
        raise WrongInput(f"Missing required sets for {table}: {missing}.")
    return {set_name: levels[set_name] for set_name in required}


def _build_empty_database(table: str, levels: dict[str, list[str]], units: dict[str, pd.DataFrame]):
    """Build one empty MARIO database used only to export templates."""
    from mario.api.database import Database

    matrix_builder = MatrixBuilder(table, levels)
    return Database(
        table=table,
        Z=matrix_builder.Z,
        E=matrix_builder.E,
        V=matrix_builder.V,
        Y=matrix_builder.Y,
        EY=matrix_builder.EY,
        VY=matrix_builder.VY,
        units=units,
    )


def _template_iot_rows(database) -> list[list[object]]:
    """Return the explicit flat workbook rows for one empty IOT template."""
    Z = database.Z
    Y = database.Y
    V = database.V
    E = database.E
    EY = database.EY
    VY = database.VY

    productive_columns = list(Z.columns)
    final_demand_columns = list(Y.columns)
    rows = [
        [None, None] + [column[0] for column in productive_columns] + [column[0] for column in final_demand_columns],
        [None, None] + [column[-1] for column in productive_columns] + [column[-1] for column in final_demand_columns],
    ]

    for row in Z.index:
        rows.append(
            [row[0], row[-1]]
            + Z.loc[row, productive_columns].tolist()
            + Y.loc[row, final_demand_columns].tolist()
        )
    for row in V.index:
        rows.append(
            [None, row]
            + V.loc[row, productive_columns].tolist()
            + VY.loc[row, final_demand_columns].tolist()
        )
    for row in E.index:
        rows.append(
            [None, row]
            + E.loc[row, productive_columns].tolist()
            + EY.loc[row, final_demand_columns].tolist()
        )
    return rows


def _template_sut_rows(database) -> list[list[object]]:
    """Return the explicit flat workbook rows for one empty SUT template."""
    Z = database.Z
    Y = database.Y
    V = database.V
    E = database.E
    EY = database.EY
    VY = database.VY

    productive_columns = list(Z.columns)
    final_demand_columns = list(Y.columns)
    rows = [
        [None, None, None]
        + [column[0] for column in productive_columns]
        + [column[0] for column in final_demand_columns],
        [None, None, None]
        + [column[-1] for column in productive_columns]
        + [column[-1] for column in final_demand_columns],
    ]

    for row in Z.index:
        rows.append(
            [row[0], row[-1], None]
            + Z.loc[row, productive_columns].tolist()
            + Y.loc[row, final_demand_columns].tolist()
        )
    for row in V.index:
        rows.append(
            [None, None, row]
            + V.loc[row, productive_columns].tolist()
            + VY.loc[row, final_demand_columns].tolist()
        )
    for row in E.index:
        rows.append(
            [None, None, row]
            + E.loc[row, productive_columns].tolist()
            + EY.loc[row, final_demand_columns].tolist()
        )
    return rows


def _template_units_rows(table: str, units: dict[str, pd.DataFrame]) -> list[list[object]]:
    """Return the explicit units sheet rows for one template workbook."""
    rows = [[None, None, "unit"]]
    for set_name in TABLE_UNIT_LEVELS[table]:
        for item, unit in units[set_name].iloc[:, 0].items():
            rows.append([set_name, item, unit])
    return rows


def write_parse_template(
    path: str,
    *,
    table: str,
    sets: dict[str, object] | None = None,
    units: dict[str, object] | None = None,
    definition: str | Path | pd.DataFrame | None = None,
    format: str = "flat",
):
    """Write one MARIO-ready Excel template from user-defined sets and units.

    Parameters
    ----------
    path : str
        Output workbook path.
    table : str
        Either ``"IOT"`` or ``"SUT"``.
    sets : dict, optional
        Dictionary containing the items for each required set. Set names accept
        the same aliases MARIO already recognizes, for example ``regions``,
        ``sectors``, ``activities``, ``commodities``, ``factors of
        production``, and ``final demand``.
    units : dict, optional
        Dictionary containing the units for unit-bearing sets. Each payload can
        be one shared string for the whole set or one mapping/Series/DataFrame
        indexed by item.
    definition : str or pandas.DataFrame, optional
        Definition workbook generated by :func:`write_template_definition`.
        When provided, ``sets`` and ``units`` are read from that workbook and
        should not be passed separately.
    format : str, optional
        ``"flat"`` writes the explicit workbook layout meant to be filled and
        parsed back with :func:`mario.parse_from_excel`. ``"matrix"`` writes the
        historical matrix workbook layout. ``"flat"`` is the default.
    """
    normalized_table = str(table).upper()
    if normalized_table not in TABLE_LEVELS:
        raise WrongInput("Only SUT and IOT are acceptable table types.")

    normalized_format = str(format).strip().lower()
    if normalized_format not in {"flat", "matrix"}:
        raise WrongInput("format should be either 'flat' or 'matrix'.")

    if definition is not None:
        if sets is not None or units is not None:
            raise WrongInput("Pass either definition=... or sets=... with units=..., not both.")
        levels, normalized_units = _read_template_definition(definition, normalized_table)
    else:
        if sets is None or units is None:
            raise WrongInput("sets and units are required unless definition=... is provided.")
        levels = _normalize_template_levels(normalized_table, sets)
        normalized_units = _normalize_units_payload(normalized_table, levels, units)
    database = _build_empty_database(normalized_table, levels, normalized_units)

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)

    if normalized_format == "matrix":
        database.to_excel(path=str(output), flows=True, coefficients=False)
        return str(output)

    rows = _template_iot_rows(database) if normalized_table == "IOT" else _template_sut_rows(database)
    units_rows = _template_units_rows(normalized_table, normalized_units)
    instructions = pd.DataFrame(
        [
            [
                "Fill the numeric values in sheet 'data' and then parse the workbook with "
                f"mario.parse_from_excel(path={output.name!r}, table={normalized_table!r}, mode='flows')."
            ],
            ["This workbook uses the explicit flat Excel layout generated by mario.write_parse_template(...)."],
        ]
    )

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(rows).to_excel(writer, sheet_name="data", header=False, index=False)
        pd.DataFrame(units_rows).to_excel(writer, sheet_name="units", header=False, index=False)
        instructions.to_excel(writer, sheet_name="instructions", header=False, index=False)
    return str(output)

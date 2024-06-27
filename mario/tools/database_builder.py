import pandas as pd
from mario.tools.constants import _LEVELS, _UNITS, _MASTER_INDEX
from mario.log_exc.exceptions import WrongInput
from mario.core import AttrData


class MatrixBuilder:
    def __init__(self, table, levels, sort=False):
        self.table = table
        self.levels = levels

    @property
    def Z(self):
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
        region = _MASTER_INDEX.r
        satellite = _MASTER_INDEX.k

        columns = self.Z.index
        index = pd.Index(self.levels[satellite])

        df = pd.DataFrame(0, index=index, columns=columns)

        return df

    @property
    def V(self):
        region = _MASTER_INDEX.r
        factor = _MASTER_INDEX.f

        columns = self.Z.index
        index = pd.Index(self.levels[factor])

        df = pd.DataFrame(0, index=index, columns=columns)

        return df

    @property
    def EY(self):
        index = self.E.index
        columns = self.Y.columns

        df = pd.DataFrame(0, index=index, columns=columns)

        return df

    @property
    def X(self):
        index = self.Z.index
        columns = ["production"]

        df = pd.DataFrame(0, index=index, columns=columns)

        return df


class DataTemplate:
    """Builds an IO or SUT table from tabular data inputs"""

    def __init__(self, table) -> None:
        if table not in _LEVELS:
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

        with pd.ExcelWriter(path) as file:
            template = self._get_data_format()
            template.to_excel(file)

    def read_template(self, io):
        """reads the tabluar data and generates the IO, SUT tables

        Parameters
        ----------
        io : str, pd.DataFrame
            the path to the excel file or pd.DataFrame

        """

        if isinstance(io, str):
            template = pd.read_excel(io, header=[0, 1])
        elif isinstance(io, pd.DataFrame):
            template = io
        else:
            raise ValueError("Only an excel file or pd.DataFrame are acceptable.")

        for level in self.levels:
            if level not in template.columns.unique(0):
                raise WrongInput(f"{level} info not found in the template")
            df = template[level]

            if level in self.unit_levels:
                df = df.set_index("value")
                df = df.loc[df.index.dropna()]

                if df.unit.isna().any():
                    raise WrongInput(
                        f"pssoible issues with NaN Values found for level {level}. Each item for this level should have a unit of measure identified for."
                    )

                if df.empty:
                    raise WrongInput(f"No value given for {level}")
                self._units[level] = df
                self._levels[level] = df.index.tolist()

            else:
                df = df["value"].dropna()
                if df.empty:
                    raise WrongInput(f"No value given for {level}")
                self._levels[level] = df.values.tolist()

    def _get_data_format(self):
        idx_0 = pd.MultiIndex.from_product([self.non_unit_levels, ["value"]])
        idx_1 = pd.MultiIndex.from_product([self.unit_levels, ["value", "unit"]])

        idx = idx_0.append(idx_1)
        return pd.DataFrame(columns=idx)

    @property
    def levels(self):
        return [*_LEVELS[self._table]]

    @property
    def unit_levels(self):
        return [*_UNITS[self._table]]

    @property
    def non_unit_levels(self):
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
        matrix_builder = MatrixBuilder(self._table, self._levels)

        return AttrData.Database(
            table=self._table,
            Z=matrix_builder.Z,
            E=matrix_builder.E,
            V=matrix_builder.V,
            Y=matrix_builder.Y,
            EY=matrix_builder.EY,
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

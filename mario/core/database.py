#%%
import pandas as pd
class DotDict(dict):
    """Lightweight dot-access dictionary with nested support."""
    
    def __init__(self, value=None, **kwargs):
        super().__init__()
        value = value or {}
        value.update(kwargs)
        for k, v in value.items():
            self[k] = self._wrap(v)

    def _wrap(self, v):
        if isinstance(v, dict):
            return DotDict(v)
        return v

    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            raise AttributeError(item)

    def __setattr__(self, key, value):
        self[key] = self._wrap(value)

    def __delattr__(self, key):
        try:
            del self[key]
        except KeyError:
            raise AttributeError(key)
        

# %%

class Table:

    def __init__(self,table,matrices,dims):
        """
        dims:
        Region
        Sector
        Commodity
        ....

        matrices:
        {
            "X": {"row": [Region,Sector],"col":[Region,Sector]}
        }
        """
        if not isinstance(matrices,dict):
            raise ValueError("matrices should be a dict with keys as the name of the matrices, and values as a dict including row/column Index Levels")
        
        self.table = table
        self.matrices = list(matrices.keys())
        self.dims = dims

        # add the checks later
        self.mapping = matrices
        self.equations = DotDict()

    def add_equation(self,output,inputs,equation):
        if output in self.equations:
            self.equations[output].append(DotDict({"inputs":inputs,"equation":equation}))
        else:
            self.equations[output] = []
            self.add_equation(output,inputs,equation)

class DataContainer:

    def __init__(self,table:Table,base_scenario="baseline",scenario_type=str):

        self._table = table
        self.matrices = DotDict({base_scenario:{}})
        self.scenario_type = scenario_type

    @property
    def table(self):
        return self._table.table
    
    def add(self,scenario,matrix,df):
        self.isin_matrix(matrix)        
        dims_row = self._table.mapping[matrix]["row"]
        dims_col = self._table.mapping[matrix]["col"]


        
        if isinstance(df.index,pd.MultiIndex):
            if set(df.index.names) != set(dims_row):
                raise ValueError("wrong row dim")
        else:
            if {df.index.name} != set(dims_row):
                raise ValueError("wrong row dims")


        if isinstance(df.columns,pd.MultiIndex):
            if set(df.columns.names) != set(dims_col):
                raise ValueError("wrong col dim")
        else:
            if {df.columns.name} != set(dims_col):
                raise ValueError("wrong col dims")
            
        self.add_scenario(scenario)
        self.matrices[scenario][matrix] = df
            
    def add_scenario(self,scenario):
        if scenario not in self.matrices.keys():
            self.matrices[scenario] = {}

    def calc(self,scenario,matrix,**kwargs):

        self.isin_matrix(matrix)

        matrices = self.matrices[scenario]

        # find the matrix in equations. maybe multiple
        eqs = self._table.equations[matrix]

        for eq in eqs:
            ins = eq.inputs
            equation = eq.equation
            missed = [m for m in ins if m not in matrices]
            avaiable = [m for m in ins if m in matrices]
            if not missed:

                df = equation(**{m:matrices[m] for m in avaiable})
                df = self.setup_indexing(matrix,df)
                self.add(
                    scenario=scenario,
                    matrix=matrix,
                    df = df
                )

                break
            
            else:
                try:
                    kwargs["attempt"] = kwargs.get("attempt",0)+1

                    if kwargs["attempt"]:
                        for m in missed:
                            self.calc(scenario,m,**kwargs)
                    
                except KeyError as e:
                    raise ValueError("failed")


            # _try = kwargs.get("try", 0)
            # kwargs["try"] = _try
            # try:
            #     if item != _ENUM.X:
            #         eq = _CALC[item][0]

            #         kw = _CALC[item][1]

            #         data = eval(eq.format(scenario=scenario, **kw))
            #     else:
            #         if _ENUM.z in self.matrices[scenario]:
            #             data = calc_X_from_z(
            #                 z=self.matrices[scenario][_ENUM.z],
            #                 Y=self.matrices[scenario][_ENUM.Y],
            #             )

            #         elif _ENUM.Z in self.matrices[scenario]:
            #             data = calc_X(
            #                 Z=self.matrices[scenario][_ENUM.Z],
            #                 Y=self.matrices[scenario][_ENUM.Y],
            #             )

            #         else:
            #             raise DataMissing(
            #                 f"MARIO is not able to calculate the {item} becuase of missing data."
            #                 " Presence of Y and of the [z,Z] is necessary."
            #             )

            #     self.matrices[scenario].update({item: data})

            #     log_time(logger, f"Database: {item} calculated for {scenario}")

            # except KeyError as error:
            #     # calculate automatically all the dependecies if possible in an recursive process
            #     if kwargs.get("try", 0) < 5:
            #         kwargs["try"] += 1

            #         log_time(
            #             logger,
            #             f"Database: to calculate {item} following matrices are need.\n{list(error.args)}."
            #             f"Trying to calculate dependencies.",
            #             "warning",
            #         )
            #         self.calc_all(list(error.args), scenario, **kwargs)
            #         self.calc_all([item], scenario, **kwargs)

            #     else:
            #         raise DataMissing(
            #             f"MARIO is not able to calculate the {item} after 5 tries becuase of missing data."
                    # )

    
    def isin_matrix(self,matrix):

        if matrix not in self._table.matrices:
            raise ValueError("Not a valid matrix")
    
    def isin_scenario(self,scenario):
        if scenario not in self.matrices:
            raise ValueError("Not a value scenario")

    def setup_indexing(self,matrix,df):
        dims_row = self._table.mapping[matrix]["row"]
        dims_col = self._table.mapping[matrix]["col"]

        if isinstance(df.index,pd.MultiIndex):
            df.index.names = tuple(dims_row)
        else:
            df.index.name = dims_row[0]

        if isinstance(df.columns,pd.MultiIndex):
            df.columns.names = tuple(dims_col)
        else:
            df.columns.name = dims_col[0]

        return df

# prototype:

IOT = Table(
    "IOT",
    matrices = dict(
        X= dict(row= ["Region","Sector"],col=["Production"])
    ),
    dims = ["Region","Sector","Production"]
    )

def calc_X(Y,Z):

    return Y+Z

IOT.add_equation(
    "X",["Y","Z"], calc_X
)
#%%
from mario.tools import iomath

# build the IOT table

IOT = Table(
    "IOT",
    matrices= 
    {
        "X":{"row":["Region","Sector"],"col":["Production"]},
        "Z":{"row":["Region","Sector"],"col":["Region","Sector"]},
        "Y":{"row":["Region","Sector"],"col":["Region","Final Demand"]},
        "IMP":{"row":["Foreign Region"],"col":["Region","Sector"]},
        "w": {"row":["Region","Sector"],"col":["Region","Sector"]},
    },
    dims=["Region","Sector","Final Demand","Final Demand"]
)
#%%
IOT.add_equation(
    "X",["w","Y"],iomath.calc_X_from_w
)

IOT.add_equation(
    "X",["Y","Z"],iomath.calc_X
)
#%%

def calc_IMP(Z,F):

    

IOT.add_equation(
    "GWP",["Z","F"],calc_IMP
)

#%%
import mario

test= mario.load_test("IOT")
#%%
Y = test.Y.droplevel("Level").droplevel("Level",axis=1)
Y.index.names = ("Region","Sector")
Y.columns.names = ("Region","Final Demand")
Database = DataContainer(IOT,"base")
#%%
Z = test.Z.droplevel("Level").droplevel("Level",axis=1)
Z.index.names = ("Region","Sector")
Z.columns.names = ("Region","Sector")
#%%
Database.add("base","Y",Y)
Database.add("base","Z",Z)
#%%
Database.calc("base","X")






# #%%
# #%%
# _CALC = {
#     _ENUM.F: (
#         "calc_F(self.matrices['{scenario}']['{enum0}'],self.matrices['{scenario}']['{enum1}'].sum(1))",
#         dict(enum0=_ENUM.f, enum1=_ENUM.Y),
#     ),
#     _ENUM.f_dis: (
#         "calc_f_dis(self.matrices['{scenario}']['{enum0}'],self.matrices['{scenario}']['{enum1}'])",
#         dict(enum0=_ENUM.e, enum1=_ENUM.w),
#     ),
#     _ENUM.p_dis: (
#         "calc_p_dis(self.matrices['{scenario}']['{enum0}'],self.matrices['{scenario}']['{enum1}'])",
#         dict(enum0=_ENUM.v, enum1=_ENUM.w),
#     ),
#     _ENUM.M: (
#         "calc_F(self.matrices['{scenario}']['{enum0}'],self.matrices['{scenario}']['{enum1}'].sum(1))",
#         dict(enum0=_ENUM.m, enum1=_ENUM.Y),
#     ),
#     _ENUM.m: (
#         "calc_f(self.matrices['{scenario}']['{enum0}'],self.matrices['{scenario}']['{enum1}'])",
#         dict(enum0=_ENUM.v, enum1=_ENUM.w),
#     ),
#     _ENUM.V: (
#         "calc_E(self.matrices['{scenario}']['{enum0}'],self.matrices['{scenario}']['{enum1}'])",
#         dict(enum0=_ENUM.v, enum1=_ENUM.X),
#     ),
#     _ENUM.v: (
#         "calc_e(self.matrices['{scenario}']['{enum0}'],self.matrices['{scenario}']['{enum1}'])",
#         dict(enum0=_ENUM.V, enum1=_ENUM.X),
#     ),
#     _ENUM.f: (
#         "calc_f(self.matrices['{scenario}']['{enum0}'],self.matrices['{scenario}']['{enum1}'])",
#         dict(enum0=_ENUM.e, enum1=_ENUM.w),
#     ),
#     _ENUM.e: (
#         "calc_e(self.matrices['{scenario}']['{enum0}'],self.matrices['{scenario}']['{enum1}'])",
#         dict(enum0=_ENUM.E, enum1=_ENUM.X),
#     ),
#     _ENUM.E: (
#         "calc_E(self.matrices['{scenario}']['{enum0}'],self.matrices['{scenario}']['{enum1}'])",
#         dict(enum0=_ENUM.e, enum1=_ENUM.X),
#     ),
#     _ENUM.z: (
#         "calc_z(self.matrices['{scenario}']['{enum0}'],self.matrices['{scenario}']['{enum1}'])",
#         dict(enum0=_ENUM.Z, enum1=_ENUM.X),
#     ),
#     _ENUM.Z: (
#         "calc_Z(self.matrices['{scenario}']['{enum0}'],self.matrices['{scenario}']['{enum1}'])",
#         dict(enum0=_ENUM.z, enum1=_ENUM.X),
#     ),
#     _ENUM.b: (
#         "calc_b(self.matrices['{scenario}']['{enum0}'],self.matrices['{scenario}']['{enum1}'])",
#         dict(enum0=_ENUM.X, enum1=_ENUM.Z),
#     ),
#     _ENUM.w: ("calc_w(self.matrices['{scenario}']['{enum0}'])", dict(enum0=_ENUM.z)),
#     _ENUM.g: ("calc_w(self.matrices['{scenario}']['{enum0}'])", dict(enum0=_ENUM.b)),
#     _ENUM.y: ("calc_y(self.matrices['{scenario}']['{enum0}'])", dict(enum0=_ENUM.Y)),
#     _ENUM.s: (
#         "self.matrices['{scenario}']['{enum0}'].loc[(slice(None),_MASTER_INDEX['a'],slice(None)),(slice(None),_MASTER_INDEX['c'],slice(None))]",
#         dict(enum0=_ENUM.z),
#     ),
#     _ENUM.S: (
#         "self.matrices['{scenario}']['{enum0}'].loc[(slice(None),_MASTER_INDEX['a'],slice(None)),(slice(None),_MASTER_INDEX['c'],slice(None))]",
#         dict(enum0=_ENUM.Z),
#     ),
#     _ENUM.u: (
#         "self.matrices['{scenario}']['{enum0}'].loc[(slice(None),_MASTER_INDEX['c'],slice(None)),(slice(None),_MASTER_INDEX['a'],slice(None))]",
#         dict(enum0=_ENUM.z),
#     ),
#     _ENUM.U: (
#         "self.matrices['{scenario}']['{enum0}'].loc[(slice(None),_MASTER_INDEX['c'],slice(None)),(slice(None),_MASTER_INDEX['a'],slice(None))]",
#         dict(enum0=_ENUM.Z),
#     ),
#     _ENUM.p: (
#         "calc_p(self.matrices['{scenario}']['{enum0}'],self.matrices['{scenario}']['{enum1}'])",
#         dict(enum0=_ENUM.v, enum1=_ENUM.w),
#     ),
#     "X_Z": (
#         "calc_X(self.matrices['{scenario}']['{enum0}'],self.matrices['{scenario}']['{enum1}'])",
#         dict(enum0=_ENUM.Z, enum1=_ENUM.Y),
#     ),
#     "X_z": (
#         "calc_X_from_z(self.matrices['{}']['{enum0}'],self.matrices['{}']['{enum1}'])",
#         dict(enum0=_ENUM.z, enum1=_ENUM.Y),
#     ),
# }
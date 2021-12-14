from collections import UserDict

class Matrices(UserDict):
    """
    A costumized dict for having a better control on matrices property
    in mario.Core

    Properties
    -----------
    _bs_name : str
        This represents the name of the baseline scenario
    _dynamic : boolean
        Shows if the database is dynamic or not
    """
    def __init__(self,baseline_name,dynamic=False,vals={}):
        self._bs_name = baseline_name
        self._dynamic = dynamic

        super().__init__(vals)

    def __setitem__(self, key, item):

        if self._dynamic and not isinstance(key,int):
            raise ValueError('For a dynamic database, only integer keys are accepted.')

        super().__setitem__(key, item)

    def __getitem__(self, key):

        if key == 'baseline':
            key = self._bs_name

        return super().__getitem__(key)
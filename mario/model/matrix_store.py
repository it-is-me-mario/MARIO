"""Canonical matrix storage with alias translation at mapping boundaries."""

from mario.settings.settings import canonical_matrix_name


class CanonicalMatrixDict(dict):
    """Store canonical keys while accepting current public aliases for access.

    Iteration, serialization and the compute engine always see canonical IDs.
    Settings changes therefore never require migrating or copying matrix data.
    """

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.update(*args, **kwargs)

    def __getitem__(self, key):
        return super().__getitem__(canonical_matrix_name(key))

    def __setitem__(self, key, value):
        super().__setitem__(canonical_matrix_name(key), value)

    def __delitem__(self, key):
        super().__delitem__(canonical_matrix_name(key))

    def __contains__(self, key):
        return super().__contains__(canonical_matrix_name(key))

    def get(self, key, default=None):
        return super().get(canonical_matrix_name(key), default)

    def pop(self, key, *default):
        return super().pop(canonical_matrix_name(key), *default)

    def setdefault(self, key, default=None):
        return super().setdefault(canonical_matrix_name(key), default)

    def update(self, *args, **kwargs):
        for key, value in dict(*args, **kwargs).items():
            self[key] = value

    def __ior__(self, other):
        self.update(other)
        return self

    def copy(self):
        return type(self)(self)


class ScenarioMatrices(dict):
    """Keep canonical matrix mappings on whole-scenario replacement as well."""

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.update(*args, **kwargs)

    def __setitem__(self, key, value):
        if not isinstance(value, CanonicalMatrixDict):
            value = CanonicalMatrixDict(value)
        super().__setitem__(key, value)

    def update(self, *args, **kwargs):
        for key, value in dict(*args, **kwargs).items():
            self[key] = value

    def setdefault(self, key, default=None):
        if key not in self:
            self[key] = {} if default is None else default
        return self[key]

    def __ior__(self, other):
        self.update(other)
        return self

    def copy(self):
        return type(self)(self)

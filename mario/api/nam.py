"""Flow-oriented Database facade for national accounting matrices.

The native state remains the authority. IO operations are guarded until they
have a NAM implementation, rather than falling through an IOT/SUT branch.
"""

from __future__ import annotations

import copy
from types import MappingProxyType

from mario.api.database import Database
from mario.api.metadata import MARIOMetaData
from mario.compute.types import ResolutionContext
from mario.log_exc.exceptions import NotImplementable, WrongInput
from mario.model.nam import NAM_BLOCKS, NAM_DERIVED, NAM_SETS, nam_set_id


class NAMDatabase(Database):
    """NAM-specific Database interface returned by public parsers.

    Obtain it with ``mario.parse_figaro(..., table="NAM")`` or
    ``mario.parse_from_excel(..., table="NAM", mode="flows")``. Account
    identities, memberships and native layouts are shared by all scenarios.
    Only the operations documented on this interface are implemented; the
    remaining inherited IOT/SUT operations raise ``NotImplementable``.
    """

    def __init__(self, state, **overrides):
        for key, value in overrides.items():
            if value is not None:
                setattr(state.metadata, key, value)
        self._state = state
        self._dir = ""
        self._custom_operator_registry = None
        self._custom_block_specs = {}
        self.info = state.metadata.extra
        self.meta = MARIOMetaData(name=overrides.get("name") or state.metadata.name)
        self.meta._add_attribute(table="NAM", **{
            key: overrides.get(key) if overrides.get(key) is not None else getattr(state.metadata, key)
            for key in ("source", "license", "version", "year", "price", "tech_assumption")
        })
        for note in state.metadata.history:
            self.meta._add_history(note)

    def __getattribute__(self, name):
        # Only methods implemented here (and plain instance data) are available.
        # Checking before descriptor evaluation also guards inherited properties.
        if not name.startswith("_") and name not in type(self).__dict__:
            if any(name in base.__dict__ for base in (Database, Database.__bases__[0])):
                raise NotImplementable(f"{name} is not implemented for NAM; use native flow inspection/export.")
        return object.__getattribute__(self, name)

    @property
    def table_type(self):
        return "NAM"

    @property
    def nam_schema(self):
        return self._state.nam_schema

    @property
    def scenarios(self):
        return list(self._state.list_scenarios())

    @property
    def baseline_scenario_name(self):
        return "baseline"

    @property
    def sets(self):
        """Return Region and the registered NAM display labels, including empty sets."""
        return ["Region", *[definition["label"] for definition in NAM_SETS.values()]]

    @property
    def matrices(self):
        """Return read-only scenario mappings of available blocks as independent copies."""
        return MappingProxyType({scenario: MappingProxyType({
            name: self.get_block(name, scenario) for name in self.list_matrices(scenario)
        }) for scenario in self.scenarios})

    @property
    def units(self):
        """Return currency, numerical scale and reference period as a dictionary."""
        return {"currency": self.nam_schema.currency, "scale": self.nam_schema.scale,
                "period": self.nam_schema.period}

    @property
    def is_hybrid(self):
        return False

    @property
    def is_multi_region(self):
        """Return whether several reporting economies are stored, without implying consolidation."""
        return len(self.nam_schema.memberships) > 1

    def get_index(self, index, level="main", *, region=None, flat=False):
        """Return the declared members of a NAM set.

        ``index`` accepts a short name, set ID, display label, ``Region`` or
        ``all``. Only ``level="main"`` is supported. Common memberships
        return a list; different national memberships return a dictionary of
        lists. Use ``region=...`` for one economy or ``flat=True`` for the
        union. These two selectors cannot be combined. Zero-valued members
        remain present; import origins are descriptors, not Region members.
        """
        if level != "main":
            raise NotImplementable("NAM aggregation indexes are not implemented yet.")
        if region is not None and flat:
            raise WrongInput("region and flat=True cannot be combined.")
        if region is not None and region not in self.nam_schema.memberships:
            raise WrongInput(f"Unknown reference economy: {region}.")
        if index == "all":
            return {name: self.get_index(name, region=region, flat=flat) for name in self.sets}
        if index in {"Region", "region", "r"}:
            return [region] if region is not None else list(self.nam_schema.memberships)
        try:
            key = nam_set_id(index)
        except ValueError as exc:
            raise WrongInput(str(exc)) from exc
        members = {r: list(groups.get(key, ())) for r, groups in self.nam_schema.memberships.items()}
        if region is not None:
            return members[region]
        if flat:
            return list(dict.fromkeys(item for items in members.values() for item in items))
        first = next(iter(members.values()), [])
        return first if all(items == first for items in members.values()) else members

    def list_matrices(self, scenario="baseline"):
        """List available stored/declared-zero blocks, excluding unavailable records.

        This does not compute derived targets. Use ``available_matrices``
        for the complete catalogue of accepted names.
        """
        return self._state.list_matrices(scenario)

    def available_matrices(self):
        """List registered NAM names, independently of source coverage or computation.

        A registered name need not be stored or resolvable from this source.
        The selected import authority determines which native flows are inputs.
        """
        return tuple(NAM_BLOCKS)

    def available_blocks(self):
        """Alias for :meth:`available_matrices`."""
        return self.available_matrices()

    def has_matrix(self, name, scenario="baseline"):
        """Test availability of a stored or declared-zero block without computing it."""
        return self._state.has_matrix(name, scenario)

    def has_block(self, name, scenario="baseline"):
        """Alias for :meth:`has_matrix`."""
        return self.has_matrix(name, scenario)

    def get_block(self, name, scenario="baseline"):
        """Read an available block as a copied DataFrame without calculating it.

        Declared-zero flows materialize as zeros. Unavailable or uncomputed
        blocks raise an error. Use ``resolve`` to calculate registered targets.
        """
        return self._state.get_block(name, scenario)

    def set_block(self, name, value, scenario="baseline", *, metadata=None):
        """Replace one complete native flow and invalidate affected derived caches.

        ``value`` must retain the block's declared accounts and native index
        levels. Without ``metadata``, the existing metadata are copied and
        presence becomes ``observed``. Explicit metadata can declare an
        entirely known zero block (``presence="declared_zero"``) or missing
        data (``presence="unavailable"``). ``value=None`` works for missing
        data and default-layout zeros; rich-layout zeros require an explicit
        zero frame with their descriptors. Calculated
        views, totals and coefficients cannot be supplied as native inputs.
        A payment edit does not balance accounts or propagate a model shock.
        """
        if metadata is None:
            try:
                metadata = self._state._resolve_block_record(name, scenario).metadata.copy()
            except KeyError:
                metadata = {"valuation": "unspecified"}
            metadata["presence"] = "observed"
            metadata["provenance"] = "Manual native-flow update through Database.set_block"
        self._state.set_block(name, value, scenario, metadata)

    def get_block_as_pandas(self, name, scenario="baseline"):
        """Read an available block as a copied pandas DataFrame."""
        return self._state.get_block_as_pandas(name, scenario)

    def get_block_as_table(self, name, scenario="baseline", *, backend="auto"):
        """Read an available block through the shared table-backend adapter."""
        return self._state.get_block_as_table(name, scenario, backend=backend)

    def get_block_as_matrix(self, name, scenario="baseline", *, backend="numpy", prefer_sparse=False):
        """Read numerical values through the shared matrix-backend adapter."""
        return self._state.get_block_as_matrix(name, scenario, backend=backend, prefer_sparse=prefer_sparse)

    def get_block_spec(self, name):
        """Return the block's semantic axes, including its native descriptors."""
        return self.nam_schema.block_spec(name)

    def resolve(self, matrix, *, scenario="baseline", force_rewrite=False, compute_options=None):
        """Return one flow or calculate a registered NAM result and its dependencies.

        Available targets are reused unless ``force_rewrite=True``. Native
        flows remain authoritative; missing payments are not inferred.
        ``compute_options`` accepts shared runtime options, but NAM registers
        no solve/inverse route or behavioural closure. Totals and coefficients
        follow the NAM calculation reference, including signed-zero errors.
        """
        if force_rewrite and matrix in NAM_DERIVED:
            self._state.scenarios[scenario].blocks.pop(matrix, None)
        return self._state.compute(matrix, scenario, ResolutionContext(compute=compute_options))

    def resolve_many(self, matrices, **kwargs):
        """Return a name-to-DataFrame dictionary for one or several NAM targets.

        Keyword arguments are forwarded to :meth:`resolve`, including
        ``scenario``, ``force_rewrite`` and ``compute_options``.
        """
        names = [matrices] if isinstance(matrices, str) else matrices
        return {name: self.resolve(name, **kwargs) for name in names}

    def calc_all(self, matrices=None, scenario="baseline", force_rewrite=False, compute_options=None):
        """Materialize requested targets; with no targets, assemble T only.

        Request account totals and coefficients explicitly. This method
        returns ``None``; ``resolve_many`` returns the calculated frames.
        """
        names = ["T"] if matrices is None else ([matrices] if isinstance(matrices, str) else matrices)
        self.resolve_many(names, scenario=scenario, force_rewrite=force_rewrite, compute_options=compute_options)

    def explain(self, matrix, scenario="baseline", compute_options=None):
        """Describe the current NAM dependency plan without calculating the target.

        A cached target is reported as available; this is not a historical
        account of its original calculation.
        """
        return self._state.explain(matrix, scenario, ResolutionContext(compute=compute_options))

    def clone_scenario(self, scenario, name):
        """Copy the source scenario's native flows and presence states to a new scenario.

        Derived caches are not copied. The new name must be nonempty and
        unused. All scenarios share the same schema and memberships.
        """
        if scenario not in self.scenarios or not isinstance(name, str) or not name.strip():
            raise WrongInput("NAM clone requires an existing source scenario and a nonempty new name.")
        self._state.create_scenario(name, parent=None)
        for matrix, definition in NAM_BLOCKS.items():
            if definition["role"] != "flow":
                continue
            try:
                record = self._state._resolve_block_record(matrix, scenario)
            except KeyError:
                continue
            value = None if record.metadata["presence"] == "unavailable" else self.get_block(matrix, scenario)
            self._state.set_block(matrix, value, name, record.metadata)

    def copy(self):
        """Return an independent database copy, retaining all scenarios and metadata."""
        return type(self)(copy.deepcopy(self._state))

    def to_excel(self, path, flows=True, coefficients=False, **kwargs):
        """Write all scenarios in the versioned MARIO native NAM workbook layout.

        Only ``flows=True, coefficients=False`` is supported; additional
        keyword options are rejected. Memberships, item metadata, layouts,
        units, audit information and flow-presence states are preserved.
        Derived caches are omitted and can be recalculated after loading
        with ``mario.parse_from_excel(path, table="NAM", mode="flows")``.
        Return the output path as a string.
        """
        if coefficients or not flows:
            raise NotImplementable("NAM Excel export currently supports native flows only.")
        if kwargs:
            raise WrongInput(f"Unsupported NAM Excel export options: {sorted(kwargs)}.")
        from mario.parsers.nam_workbook import write_nam_workbook

        return write_nam_workbook(self._state, path)

    def __getitem__(self, scenario):
        if isinstance(scenario, str):
            return MappingProxyType({name: self.get_block(name, scenario) for name in self.list_matrices(scenario)})
        raise WrongInput("NAM indexing expects a scenario name.")

    def __getattr__(self, name):
        if name in NAM_BLOCKS:
            return self.resolve(name)
        raise AttributeError(name)

    def __str__(self):
        """Render metadata and set counts with the IOT/SUT summary conventions."""
        lines = [f"name = {self.meta.name}", "table = NAM", f"scenarios = {self.scenarios}"]
        for label in self.sets:
            members = self.get_index(label)
            if isinstance(members, dict):
                counts = [len(values) for values in members.values()]
                count = f"from {min(counts, default=0)} to {max(counts, default=0)} per region"
            else:
                count = len(members)
            lines.append(f"{label} = {count}")
        return "\n".join(lines) + "\n"

    def __repr__(self):
        """Return the same structural summary used by ``__str__``."""
        return self.__str__()

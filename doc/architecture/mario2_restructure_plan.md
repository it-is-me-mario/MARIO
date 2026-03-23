# MARIO 2 restructure plan

This document translates the current legacy codebase, the compute brief, and the
catalog attachment into a concrete restructuring proposal that preserves the
domain identity of MARIO while changing the technical architecture.

## 1. Cosa mantenere del MARIO attuale

- The core domain grammar should remain rooted in the existing conventions from
  `mario/settings/settings.py` and `mario/tools/constants.py`. The labels for
  Region, Sector, Activity, Commodity, Factor of production, Satellite account,
  and Consumption category are already stable and should remain authoritative.
- The uppercase/lowercase distinction for flows vs coefficients is correct and
  should survive the migration. This is one of the clearest conceptual assets in
  the project, and it is already encoded across `mario/tools/constants.py`,
  `mario/tools/iomath.py`, and the public API.
- The idea that one database contains multiple scenarios is good and should be
  preserved. The current `CoreModel.matrices[scenario][matrix]` layout is not a
  good storage backend, but the scenario semantics in `mario/core/CoreIO.py` are
  worth keeping.
- The legacy parser layer contains valuable normalization knowledge. The code in
  `mario/tools/tableparser.py` knows how to validate shape, rebuild indexes, and
  map source-specific structures into MARIO semantics. That logic should be
  decomposed, not discarded.
- The pure algebra in `mario/tools/iomath.py` is a good base for IOT formulas.
  The functions are already close to the target style. They should be split,
  renamed, and typed, but most of the math should be migrated rather than
  reinvented.
- The transformation logic in `mario/tools/tabletransform.py` is worth
  preserving. `SUT_to_IOT` and `ISARD_TO_CHENERY_MOSES` are domain operations,
  not parser accidents.
- The legacy public surface that users already rely on should survive through a
  compatibility adapter, especially `calc_all`, `query`, `get_data`,
  `aggregate`, `to_excel`, `to_txt`, `to_iot`, `to_pymrio`, and the main parse
  functions exposed in `mario/__init__.py`.

## 2. Cosa cambiare

- `mario/core/AttrData.py` and `mario/core/CoreIO.py` are too large and mix too
  many responsibilities: storage, metadata, compute orchestration, query logic,
  export, plotting hooks, and transformations all live in the same objects.
- `mario/tools/constants.py` currently contains three different concerns in one
  place: domain labels, matrix metadata, and executable compute logic. `_CALC`
  plus `eval` in `CoreModel.calc_all` must disappear.
- Pandas `DataFrame` with `MultiIndex` should stop being the ground truth. It is
  still useful for compatibility, export, and some numerical operations, but it
  should become a view layer rather than the core storage model.
- The current parser flow often collapses SUT input into unified `Z/V/E/Y`
  blocks too early. The compute brief is right here: for SUT, the native split
  blocks should be first-class and the unified blocks should mostly be views.
- The project needs a real separation between:
  parser input normalization,
  canonical data model,
  storage backend,
  block materialization,
  formula execution,
  user-facing compatibility methods.
- Packaging also needs cleanup. `setup.py` currently hardcodes package names in a
  fragile way. New modules should be packaged automatically.

## 3. Nuova architettura proposta

The target tree should stay pragmatic and small enough to maintain:

```text
mario/
  __init__.py
  api.py

  model/
    __init__.py
    enums.py
    labels.py
    metadata.py
    block.py
    scenario.py
    dataset.py

  storage/
    __init__.py
    base.py
    parquet.py
    duckdb.py
    repository.py

  compute/
    __init__.py
    types.py
    catalog.py
    ordering.py
    views.py
    helpers.py
    iot_formulas.py
    sut_formulas.py
    ghosh_formulas.py
    planner.py
    graph.py
    resolver.py

  parsers/
    __init__.py
    base.py
    registry.py
    result.py
    helpers.py
    excel.py
    txt.py
    exiobase.py
    eora.py
    eurostat_sut.py
    figaro.py
    pymrio.py

  ops/
    __init__.py
    aggregate.py
    query.py
    transform.py
    export.py

  views/
    __init__.py
    pandas.py
    excel.py
    legacy.py

  compat/
    __init__.py
    database.py
    parsers.py
    converters.py
```

Concrete module mapping from legacy:

- `mario/tools/constants.py` -> `mario/model/labels.py` plus
  `mario/compute/catalog.py`
- `mario/tools/iomath.py` -> `mario/compute/iot_formulas.py`,
  `mario/compute/sut_formulas.py`, `mario/compute/ghosh_formulas.py`
- `mario/tools/tableparser.py` + `mario/tools/parsersclass.py` ->
  `mario/parsers/*` plus `mario/compat/parsers.py`
- `mario/core/CoreIO.py` + `mario/core/AttrData.py` ->
  `mario/model/dataset.py`, `mario/ops/*`, `mario/compat/database.py`
- `mario/tools/aggregation.py` -> `mario/ops/aggregate.py`
- `mario/tools/excelhandler.py` -> `mario/views/excel.py`
- `mario/tools/tabletransform.py` -> `mario/ops/transform.py`

The important constraint is that the new tree runs in parallel with the legacy
tree during the migration. The first sprint should not move or delete the
existing implementation.

## 4. Nuovo modello dati

The new ground truth should be:

- `Dataset`: owns metadata, dimension registry, scenario registry, storage
  backend, and block-level access.
- `Scenario`: represents baseline or derived scenarios with provenance and
  block overrides.
- `Block`: stores block identity, axes, semantic role, storage reference, and
  units metadata.

Recommended storage model:

- Persist block values in Arrow/Parquet long tables.
- Use DuckDB for scan, joins, aggregation, and lazy materialization.
- Use Polars for typed tabular transforms.
- Use NumPy and SciPy sparse for dense/sparse algebra.
- Use pandas only for:
  compatibility adapters,
  export to Excel/txt,
  direct user inspection,
  interop with existing downstream notebooks.

The legacy conventions that must be carried into the new model:

- `Index()` and `Nomenclature()` remain authoritative sources for human labels
  and canonical matrix names.
- The current `_LEVELS`, `_UNITS`, `_INDECES`, and `_ALL_MATRICES` definitions
  should not be copied verbatim into one more global constants file. They should
  be split into:
  `model/labels.py` for label semantics,
  `compute/catalog.py` for block specs and dependencies,
  `views/legacy.py` for pandas `MultiIndex` projections.
- The compute catalog can keep planner-only metadata such as derivation
  strategies while the resolver is being built, but that metadata must remain an
  internal concern. It should not become part of the long-term public semantics
  of `Dataset`, `Scenario`, or `Block`.
- The legacy `Level` slot used in pandas `MultiIndex` should become a
  compatibility view concern. In the new core, the logical dimension is
  `Sector`, `Activity`, or `Commodity`, not a generic `Level` string.

SUT-specific rule:

- The canonical user-facing semantics remain unified across IOT and SUT.
- The physical storage and compute ground truth for SUT should be split around
  `U`, `S`, `Xa`, `Xc`, `Ya`, `Yc`, `Va`, `Vc`, `Ea`, `Ec`, and the four
  Leontief quadrants.

## 5. Nuovo motore di calcolo

The new compute engine should replace `_CALC` + `eval` with:

- a typed Python catalog;
- a planner;
- a dependency graph;
- a resolver with memoization;
- pure formula functions.

Resolution priority should be:

1. already materialized
2. parsed
3. extract from already materialized source
4. concat from already materialized sources
5. formula

That priority is stricter than the legacy recursion in `CoreModel.calc_all`.
This matters especially for SUT. If `wcc` is requested and `w` is not already
materialized, the resolver should compute `wcc` directly from `u` and `s`
instead of building a larger unified block and slicing it.

Concrete design choices:

- IOT stays unified in compute space.
- SUT becomes split-first in compute space.
- Unified SUT blocks like `Z`, `z`, `w`, `X`, `V`, `E`, `Y`, `m`, `f`, and `p`
  are built in `compute/views.py` through centralized ordering rules.
- `b` and `g` stay isolated in `ghosh_formulas.py` because both the attachment
  and the legacy code leave room for future correction.

Conflicts resolved conservatively:

- The compute attachment is correct to reject `eval`, but the legacy
  `calc_p(v, w)` should be preserved as the semantic basis for price computation.
  The spreadsheet expression `transpose(m.sum(0))` is compatible with that.
- The attachment treats unified SUT blocks as mostly views. That conflicts with
  parts of the current SUT pipeline that compute through unified `Z`. The safe
  migration path is:
  keep unified blocks available through views,
  migrate new compute to split blocks,
  let the compat adapter request unified materializations only when an old API
  still needs them.
- `M/F` for SUT and the unified `w` concatenation remain explicit TODOs. The new
  catalog should keep those ambiguities visible instead of hiding them.

## 6. Nuova struttura parser

The parser layer should become two-stage:

- source-native parse
- canonical block mapping

Recommended parser API:

- `BaseParser.detect(source)`
- `BaseParser.read(source)`
- `BaseParser.map_to_native(raw)`
- `BaseParser.map_to_canonical(native)`
- `BaseParser.validate(result)`

Recommended result objects:

- `RawParseResult`
- `NativeParseResult`
- `CanonicalParseResult`

Pragmatic migration of legacy parser logic:

- Reuse validation and index reconstruction knowledge from
  `mario/tools/tableparser.py`.
- Keep current source-specific knowledge from EXIOBASE, EORA, EUROSTAT, FIGARO,
  and pymrio parsers.
- Stop forcing all SUT parsers to emit only unified `Z/V/E/Y/EY`.

Parser rules:

- IOT parsers may continue to emit `Z`, `Y`, `V`, `E`, `EY`, optionally `X`.
- SUT parsers should prefer `U`, `S`, `Yc`, `Ya`, `Va`, `Vc`, `Ea`, `Ec`, `EY`,
  and any provided `Xa/Xc`.
- Third-party extension should happen through registry entry points so new
  parsers do not require edits in core modules.

## 7. Strategia di retrocompatibilita

Do not preserve the old architecture inside the new core. Preserve the user
experience through adapters.

Methods worth keeping in the compatibility layer:

- `Database` construction and the main parse functions exposed in `mario.__init__`
- `calc_all`
- `query`
- `get_data`
- `aggregate`
- `to_excel`
- `to_txt`
- `to_iot`
- `to_pymrio`
- `clone_scenario`
- `reset_to_flows`
- `reset_to_coefficients`
- `get_index`

Methods that can remain legacy for longer:

- plotting helpers
- some Excel-template utilities
- add-sector and add-extension workflows

Realistic transition strategy:

1. Introduce `compat/database.py` with `LegacyDatabaseAdapter`.
2. Make `calc_all` call `resolver.resolve_many`.
3. Make `query/get_data` read through the new dataset/block APIs but still return
   pandas outputs in the old shapes.
4. Keep parse function names unchanged while routing new parser implementations
   behind the same entry points.
5. Deprecate direct mutation of `self.matrices[scenario][matrix]`.

Compatibility should be strong for the read/query/calc path, weaker for
internals. Full backward compatibility for every hidden attribute is not a
reasonable goal.

## 8. Piano di implementazione in fasi

### Phase 1: parallel core bootstrap

- Create `model/` and `compute/` in parallel with legacy.
- Move label semantics into `model/labels.py`.
- Create typed `compute/types.py`.
- Create Python `compute/catalog.py` covering IOT plus split-first SUT blocks.

### Phase 2: SUT ordering and views

- Implement `compute/ordering.py`.
- Implement `compute/views.py`.
- Make unified SUT blocks deterministic views over split blocks.

### Phase 3: formula migration

- Split `mario/tools/iomath.py` into pure IOT, SUT, and Ghosh formula modules.
- Add tests that compare old IOT outputs with new pure functions.

### Phase 4: resolver

- Implement `planner.py`, `graph.py`, and `resolver.py`.
- Add explainability for unresolved blocks and dependency cycles.

### Phase 5: dataset/storage

- Introduce `Dataset`, `Scenario`, `Block`, and Parquet-backed storage.
- Start with a pandas-backed adapter if needed, but keep the model API stable.

### Phase 6: parser migration

- Port one IOT parser and one SUT parser to the new stack first.
- Recommended first pair: generic Excel parser and EXIOBASE SUT parser.
- Keep the legacy normalization code as the parsing foundation; the migration
  point is the output contract, not a speculative rewrite of file readers.
- Let generic Excel cover both IOT and SUT, but persist SUT in split-native
  blocks (`U/S/Ya/Yc/Va/Vc/Ea/Ec/Xa/Xc`) instead of storing duplicated unified
  and split structures side by side.

### Phase 7: compatibility layer

- Implement `compat/database.py`.
- Route `calc_all`, `query`, `get_data`, and `aggregate` through the new stack.
- Use a resolver-first strategy for legacy `calc_all`, with explicit fallback to
  the old recursive formulas where the MARIO 2 compute engine is not yet
  complete, especially in partially migrated SUT paths.
- Keep `query` and `get_data` shape-compatible with the historical API, but let
  their auto-calc path flow through the same compat adapter instead of
  re-implementing dependency handling ad hoc.

### Phase 8: remaining operations

- Move aggregation, export, SUT-to-IOT, Chenery-Moses, and pymrio conversion
  into `ops/` and `views/`.
- Keep `AttrData.py` as a facade where possible: the method names stay where
  users expect them, but the implementation entry points move into focused
  modules such as `ops/transforms.py`, `ops/aggregation.py`,
  `ops/export.py`, and `views/tabular.py`.
- Migrate plotting only after the data and compute contracts stabilize.

## 9. Primi file da creare/modificare subito

Created now in this first restructuring pass:

- `mario/model/enums.py`
- `mario/model/labels.py`
- `mario/compute/types.py`
- `mario/compute/catalog.py`
- `tests/test_compute_catalog.py`
- `doc/architecture/mario2_restructure_plan.md`

Files to create next, in this order:

- `mario/compute/ordering.py`
- `mario/compute/views.py`
- `mario/compute/iot_formulas.py`
- `mario/compute/sut_formulas.py`
- `mario/compute/ghosh_formulas.py`
- `mario/compute/planner.py`
- `mario/compute/graph.py`
- `mario/compute/resolver.py`
- `mario/model/dataset.py`
- `mario/compat/database.py`

Files to modify next:

- `mario/__init__.py` to expose the new public entry points without breaking the
  legacy API
- `mario/core/CoreIO.py` so `calc_all` becomes a wrapper instead of a compute
  engine
- `mario/tools/parsersclass.py` so parse functions can hand off to the new
  parser registry
- `mario/tools/tableparser.py` to peel out reusable normalization helpers into
  `mario/parsers/helpers.py`

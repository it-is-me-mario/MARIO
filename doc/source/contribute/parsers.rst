Parsers
=======

The parser layer exists to turn heterogeneous external sources into one
consistent internal state that can instantiate a ``mario.Database``.

For an expert user, the key point is that MARIO does not treat parsing as a
thin file-reader step. Parsing is where source-specific conventions,
dimensional choices, metadata, and assumptions are normalized into the common
MARIO model.

High-level parser flow
----------------------

The public flow is:

* a package-level entry point such as ``parse_from_txt(...)`` or
	``parse_exiobase(...)`` is imported from ``mario.parsers.entrypoints``;
* the entry point validates the request and dispatches to a source-specific
	parser or a generic state reader;
* the parser returns parsed matrices, indices, units, and source metadata in a
	normalized parser state;
* ``build_database_from_state(...)`` or an equivalent helper turns that state
	into a ``Database`` instance.

This is the main boundary to remember: source-specific code should mostly stop
once a valid parser state exists. After that point, MARIO should behave as if
the data had always been native.

Public entry points
-------------------

``mario.parsers.entrypoints`` is the best place to see the supported ingestion
surface. It contains:

* generic bundle readers such as ``parse_from_txt(...)``,
	``parse_from_excel(...)``, and ``parse_from_parquet(...)``;
* named dataset readers such as ``parse_oecd(...)``, ``parse_figaro(...)``,
	``parse_eurostat(...)``, ``parse_gloria(...)``, ``parse_gtap(...)`` and the
	other source-specific helpers;
* light request-validation logic and dispatch to the actual parsing modules.

In practice, these entry points are the public contract. They are allowed to be
source-aware, but they should stay much thinner than the actual source readers.

What a parser is expected to produce
------------------------------------

Regardless of source, the parser layer is trying to converge on the same
outputs:

* matrix payloads keyed by canonical MARIO names;
* normalized indices and units for the table kind;
* enough metadata to preserve source, price system, year, and special
	assumptions;
* a state that can immediately back ``Database(..., init_by_parsers=...)``.

That normalization step matters more than the raw file format. Two parsers can
read very different inputs and still be considered equivalent if they materialize
the same MARIO state.

Generic readers versus source-specific readers
----------------------------------------------

There are two broad parser families.

Generic readers
	 These read already MARIO-shaped bundles such as Excel, TXT/CSV, or Parquet.
	 Their job is mostly to validate shape, detect table kind, build indices, and
	 preserve layout information.

Source-specific readers
	 These know about one external source, such as OECD, FIGARO, GLORIA, EORA,
	 EXIOBASE, or GTAP. They typically contain the dataset-specific logic for file
	 discovery, layout detection, naming cleanup, satellite selection, and any
	 source-side assumptions needed before the data becomes MARIO-compatible.

The parser family determines where to look when a parse result feels wrong.
If a MARIO-formatted workbook fails, the issue is often in the generic reader or
index validation. If a named dataset fails, the issue is more likely in the
source-specific normalization layer.

Parser state and metadata
-------------------------

MARIO parsers are not only extracting matrices. They are also deciding which
metadata must survive into the runtime object. Examples include:

* table kind, such as ``IOT`` or ``SUT``;
* source label and year;
* price or valuation metadata when relevant;
* technology assumptions for SUT workflows;
* notes that explain non-default parse choices.

That is why the parser layer is structurally important even for advanced users
who never plan to add a new parser. Many later behaviours are only intelligible
once you know which metadata the parser injected into the database.

How to read a parser implementation
-----------------------------------

When reading parser code, a good sequence is:

* start from the public entry point in ``mario.parsers.entrypoints``;
* identify the source-specific function it delegates to;
* look for the point where external files are converted into canonical matrix
	blocks and indices;
* find the handoff into ``build_database_from_state(...)`` or ``Database``.

If you keep that path in view, the source-specific details stay manageable.
Without it, parser modules can look more irregular than they really are.

Testing expectations
--------------------

Parser tests in MARIO are intentionally more integration-heavy than unit-heavy.
The project relies on:

* small real-data fixtures for source-specific regressions;
* roundtrip checks for exported MARIO-formatted bundles;
* validation across both legacy-friendly and explicit-layout paths.

This reflects the real parser risk profile: breakages usually come from shape,
labels, or layout drift rather than from one isolated pure function.

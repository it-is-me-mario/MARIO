Parser Development
==================

This page documents the intended workflow for adding a new parser to MARIO.

The design goal is simple:

* a parser author should only need to understand MARIO blocks, indexes and
  units;
* the parser should interact with one small parser-authoring surface;
* parser authors should not need to edit low-level infrastructure modules.


Where To Start
--------------

If you are writing a new parser, the main module to use is:

``mario.parsers.api``
   The parser-authoring surface. It exposes the small set of helpers needed to
   validate parser arguments and turn parsed blocks into either ``ModelState``
   or ``Database`` objects.

The supporting modules are:

``mario.parsers.base``
   Only needed if you want to register a parser in the internal parser
   registry.

``mario.parsers.registry``
   Only needed if you want your parser to participate in the internal registry.

``mario.parsers.entrypoints``
   Only needed if you want to expose a new user-facing parser function through
   ``mario`` or ``mario.parsers``.


The Minimal Rule
----------------

For a typical new parser you should only need to touch:

1. one new parser module under ``mario/parsers/``;
2. one test file or one new test function;
3. optionally one public entry point export.

You should not need to edit:

* ``mario.parsers.helpers``
* ``mario.parsers.registry``
* ``mario.parsers.base``
* ``mario.internal``

unless you are changing parser infrastructure itself.


What A Parser Must Produce
--------------------------

Every MARIO parser eventually needs to provide three things:

``matrices``
   A mapping of block names to pandas objects. Usually this is wrapped as
   ``{"baseline": {...}}``.

``indexes``
   The logical MARIO sets such as regions, sectors, activities, commodities,
   factors, satellites and final demand categories.

``units``
   Per-set unit tables.

Once you have those three objects, the parser-authoring helpers can do the rest.


Recommended Authoring Helpers
-----------------------------

``validate_parse_request(...)``
   Validates common arguments such as ``table``, ``mode``, ``unit`` and
   ``model``.

``build_parser_state(...)``
   Builds a canonical internal ``ModelState`` from normalized parser output.

``build_database_from_state(...)``
   Converts a parser ``ModelState`` into the public ``Database`` object.

``build_database_from_parser_output(...)``
   The simplest end-to-end helper. Give it normalized blocks, indexes and
   units, and it returns a public ``Database``.


Two Recommended Patterns
------------------------

Pattern 1: Direct public parser
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This is the simplest choice when you just want a new function that returns a
``Database``.

.. code-block:: python

   from mario.parsers.api import (
       build_database_from_parser_output,
       validate_parse_request,
   )


   def parse_my_source(path: str, *, table: str = "IOT", mode: str = "flows"):
       validate_parse_request(table=table, mode=mode)

       matrices = {"baseline": {"Z": Z, "Y": Y, "V": V, "E": E, "EY": EY}}
       indexes = {
           "r": {"main": regions},
           "n": {"main": demand_categories},
           "f": {"main": factors},
           "k": {"main": extensions},
           "s": {"main": sectors},
       }
       units = {
           "Sector": sector_units,
           "Factor of production": factor_units,
           "Satellite account": extension_units,
       }

       return build_database_from_parser_output(
           table=table,
           matrices=matrices,
           indexes=indexes,
           units=units,
           parser_name="my_source",
           mode=mode,
           name="My dataset",
           source=path,
           source_path=path,
       )


Pattern 2: Internal state parser + registry
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use this pattern if you want registry-based parsing or you want to keep the
raw parser separate from the public ``Database`` entry point.

.. code-block:: python

   from mario.parsers import BaseParser, register_parser
   from mario.parsers.api import build_parser_state


   class MyParser(BaseParser):
       name = "my_source"

       def parse(self, path: str, *, table: str = "IOT", mode: str = "flows"):
           matrices = {"baseline": {"Z": Z, "Y": Y, "V": V, "E": E, "EY": EY}}
           indexes = {...}
           units = {...}

           return build_parser_state(
               table=table,
               matrices=matrices,
               indexes=indexes,
               units=units,
               parser_name=self.name,
               mode=mode,
               source=path,
               source_path=path,
           )


   register_parser("my_source", MyParser())


How Much Native Data To Parse
-----------------------------

A parser should materialize only the blocks that are native in the source.

Good examples:

* IOT source with native ``Z``, ``Y``, ``V``, ``E``, ``EY``:
  parse exactly those.
* SUT source with native ``U``, ``S``, ``Ya``, ``Yc``, ``Va``, ``Vc``,
  ``Ea``, ``Ec``, ``EY``:
  parse exactly those.

Avoid eagerly computing derived blocks such as:

* ``X``
* unified SUT blocks if the source is already split-native
* coefficient matrices that the compute engine can derive later

The parser builder helpers already preserve this rule by keeping production
blocks demand-driven and promoting unified SUT blocks into split-native state
when needed.


SUT Guidance
------------

If the source is SUT and already split-native, prefer parsing:

* ``U``, ``S``
* ``Ya``, ``Yc``
* ``Va``, ``Vc``
* ``Ea``, ``Ec``
* ``EY``

If the source gives only unified ``Z``, ``Y``, ``V``, ``E`` and ``EY``, you
can still pass those to ``build_parser_state(...)``. MARIO will promote them to
split-native blocks internally.


When You Need A Public Entry Point
----------------------------------

Only after the parser works and is tested should you expose it publicly.

Typical final steps:

1. add one function in ``mario.parsers.entrypoints``;
2. optionally re-export it in ``mario/parsers/__init__.py``;
3. optionally re-export it in ``mario/__init__.py`` if it is truly public.

Do not start by editing all three surfaces. Start with the parser module and
the test.


Recommended Test Strategy
-------------------------

Every new parser should ideally have:

1. one parser-specific smoke test on a real or reduced fixture;
2. one structural test asserting the native baseline blocks;
3. one semantic test on indexes or units;
4. one compute-aware test if the parser relies on deferred derived matrices.

For SUT parsers specifically, always check that unified blocks such as ``Z`` or
``X`` are not eagerly materialized unless the source is truly unified and that
split blocks are available or derivable as expected.


Current Practical Advice
------------------------

If you want to add many parsers quickly, the most robust approach is:

* keep raw file reading logic local to the parser module;
* normalize the result into canonical MARIO blocks;
* use ``mario.parsers.api`` to build the state or database;
* keep tests close to the parser behavior you care about;
* only add a public entry point after the parser itself is solid.

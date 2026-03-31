Parser Model
============

The parser side of MARIO follows one core idea:

* a parser should materialize only the native blocks present in the source;
* parser infrastructure then turns those blocks into a canonical MARIO state or
  public ``Database`` object.

In practice, a parser needs to provide:

* matrices;
* indexes/sets;
* units.

The parser helpers in ``mario.parsers.api`` handle the rest of the state
construction.

The MARIO Database Model
========================

MARIO revolves around one main public object: ``mario.Database``.

A database stores:

* one or more scenarios;
* a set of matrix blocks such as ``Z``, ``Y``, ``V``, ``E`` for IOTs or
  ``U``, ``S``, ``Ya``, ``Yc``, ``Va``, ``Vc`` for SUTs;
* the logical MARIO sets such as regions, sectors, activities, commodities,
  factors, satellite accounts and final-demand categories;
* units and metadata.

The newer parser and storage layers also use an internal state model, but the
main user-facing abstraction remains ``Database``.

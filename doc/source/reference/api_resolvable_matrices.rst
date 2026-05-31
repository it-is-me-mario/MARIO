Resolvable Matrices and Blocks
==============================

Not every computed result in MARIO has a dedicated Python method. Many are
exposed as named blocks that you access through the generic compute API:

.. code-block:: python

   db.resolve("Xa")
   db.resolve_many(["u", "s", "Xc"])
   db.calc_all(["fc", "pc"])
   db.Xa
   db.wcc

Use :doc:`../api_document/mario.CoreModel.available_matrices` to list the block
names accepted by the current table, and
:doc:`../api_document/mario.CoreModel.get_block_spec` to inspect their semantic
axes.

For SUT databases, the built-in split and quadrant blocks include ``U``, ``u``,
``S``, ``s``, ``Xa``, ``Xc``, ``Va``, ``Vc``, ``Ea``, ``Ec``, ``Ya``, ``Yc``,
``wcc``, ``wca``, ``wac``, ``waa``, ``fa``, ``fc``, ``ma``, ``mc``, ``pa`` and
``pc``. The canonical commodity production vector name is ``Xc``; ``Cx`` is
not a built-in MARIO matrix name.

The reference table below reuses the authoritative nomenclature matrix catalog
and therefore covers both IOT and SUT built-ins, along with their table format,
mode and default axes.

.. raw:: html
   :file: ../concepts/_generated/matrices_table.html

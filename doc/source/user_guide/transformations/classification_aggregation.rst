:page-type: Guide
:summary: Prepare and review a NACE or CPA mapping before grouping the model.

Aggregate by classification
===========================

This example uses a **GLORIA release 060 SUT** already parsed as ``db``.
Check ``db.available_aggregations`` for your model's supported sets and levels.

.. container:: mario-flow

   **Select a hierarchy** → **Prepare mapping** → **Review gaps** → **Aggregate**

.. mario-steps::

   .. mario-step:: 1 · Prepare

      .. code-block:: python

         mapping = db.get_aggregation(
             set="Activity", classification="NACE Rev. 2.1", level="division",
         )
         frame = mapping["Activity"]

      The result is a dictionary of DataFrames, ready for ``aggregate()``.
      The ``Aggregation`` column covers the whole selected native set.

   .. mario-step:: 2 · Review

      .. code-block:: python

         report = frame.attrs["concordance"]
         report["unresolved"]

      **Unresolved items keep their original labels by default.** For example,
      wheat and rice map to division 01, while the packaged Fishing mapping
      spans divisions 01 and 03 and remains separate at this level.

   .. mario-step:: 3 · Apply

      .. code-block:: python

         aggregated = db.aggregate(io=mapping, levels=list(mapping), inplace=False)
         aggregated.get_index("Activity")

      You obtain a grouped copy. Preparing a classification mapping does not
      override unit compatibility: a hybrid model can reject sums across
      different native units.

.. mario-details:: Sections, divisions and unresolved assignments

   Presets cover NACE Rev. 2.1 and CPA 2.2 hierarchies for mapped variants.
   ``level="2 digits"`` means divisions, not NACE Rev. 2.
   Use ``unresolved="raise"`` when every item must have a unique group.

   Missing links, links spanning multiple groups, and overly broad source
   codes can remain unresolved. A unique group still inherits any partial
   overlap in the underlying correspondence. See :doc:`classification_mapping`.

.. mario-details:: Group both sides of a SUT

   .. code-block:: python

      both = {
          **db.get_aggregation(set="Activity", classification="NACE Rev. 2.1", level="section"),
          **db.get_aggregation(set="Commodity", classification="CPA 2.2", level="section"),
      }
      reports = {name: frame.attrs["concordance"] for name, frame in both.items()}

   Review both reports, then apply ``db.aggregate(both, levels=list(both), inplace=False)``.

.. mario-details:: Regional labels and saving the mapping

   Region-specific classifications use a ``(Region, Item)`` index containing
   actual pairs. Keep that index intact. ``get_aggregation()`` prepares the
   whole selected set; it has no item or region filter.

   Keep the mapping **and** its ``attrs["concordance"]`` report with your
   results. CSV and Excel row exports alone do not preserve those attributes.
   After aggregation, concordance queries see the new labels and cannot
   reconstruct the original membership.

Interfaces: :doc:`db.get_aggregation() <../../api_document/mario.CoreModel.get_aggregation>`
and :doc:`db.aggregate() <../../api_document/mario.Database.aggregate>`.
For custom groups or regions, see :doc:`aggregate`.

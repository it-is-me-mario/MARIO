:page-type: Guide
:summary: Prepare NACE or CPA groups, review their coverage and apply them to a copy of your model.

Aggregate by classification
============================

.. container:: mario-guide-facts

   **You need:** a parsed database with a supported hierarchy preset.
   The example below uses a **GLORIA release 060 SUT**, already loaded as ``db``.

   **You obtain:** an aggregated copy. Preparing the mapping does not modify
   the model. Items that cannot be assigned to one group are retained under
   their original labels by default.

1. Choose the set and level
---------------------------

.. code-block:: python

    db.available_aggregations

Available hierarchy presets cover **NACE Rev. 2.1** and **CPA 2.2** for mapped
native variants. Choose ``Activity`` or ``Commodity`` on a SUT, or ``Sector``
on an IOT.

``classification`` selects an edition; ``level`` selects a hierarchy level.
For example, ``level="2 digits"`` means divisions within the selected edition,
not NACE Rev. 2. See the :doc:`levels and assignment rules <classification_mapping>`
for the full hierarchy.

2. Prepare the mapping
-----------------------

.. code-block:: python

    mapping = db.get_aggregation(
        set="Activity",
        classification="NACE Rev. 2.1",
        level="division",
    )
    frame = mapping["Activity"]
    frame.loc[["Growing wheat", "Growing rice", "Fishing"], "Aggregation"].to_dict()
    # {'Growing wheat': 'NACE Rev. 2.1:01',
    #  'Growing rice': 'NACE Rev. 2.1:01',
    #  'Fishing': 'Fishing'}

The dictionary contains one DataFrame per selected set. Its ``Aggregation``
column assigns a target to every current item. Wheat and rice share division
01. The packaged correspondence for Fishing spans divisions 01 and 03, so it
keeps its original label at this level.

The method prepares the **whole selected set**. It has no ``item`` or ``region``
filter; use :doc:`concordances <../inspection/concordances>` to inspect
individual items.

3. Review unresolved items
---------------------------

.. code-block:: python

    import pandas as pd

    report = frame.attrs["concordance"]
    unresolved_items = pd.DataFrame.from_dict(report["unresolved"], orient="index")
    report["unresolved"]["Fishing"]["groups"]  # ['01', '03']
    report["groups"]["NACE Rev. 2.1:01"]       # Code and description.
    unresolved_items

Review missing correspondences, codes that span several groups, and codes too
broad for the requested level. The default ``unresolved="keep"`` can produce
a mixture of hierarchy groups and original labels. A unique group still
inherits any partial-overlap qualifications in the source correspondence.

If your analysis requires every item to be assigned, prepare the mapping with
``unresolved="raise"`` instead; any unresolved item then raises ``WrongInput``.
See :doc:`How classification groups are assigned <classification_mapping>`
for the report's meaning and source limitations.

4. Apply the reviewed mapping
------------------------------

.. code-block:: python

    aggregated = db.aggregate(
        io=mapping,
        levels=list(mapping),
        inplace=False,
    )
    aggregated.get_index("Activity")

**Result:** a new SUT with grouped activities. The original ``db`` remains
available; commodities and regions retain their original classifications.
Different units cannot be summed into one group, so a hybrid model can reject
an otherwise valid classification mapping when it is applied.

Group both sides of a SUT
--------------------------

Prepare and review both mappings before applying them together:

.. code-block:: python

    both_sides = {
        **db.get_aggregation(set="Activity", classification="NACE Rev. 2.1", level="section"),
        **db.get_aggregation(set="Commodity", classification="CPA 2.2", level="section"),
    }
    reports = {name: frame.attrs["concordance"] for name, frame in both_sides.items()}

After reviewing ``reports``:

.. code-block:: python

    aggregated_both = db.aggregate(both_sides, levels=list(both_sides), inplace=False)

Keep the mapping with your results
-----------------------------------

Regional classifications, including BONSAI's, use a ``(Region, Item)`` index
with the pairs actually present. Pass the complete mapping without flattening
that index. Geographic aggregation is a separate operation, covered in
:doc:`Aggregate a database <aggregate>`.

Save the input mapping and its ``attrs["concordance"]`` report. Exporting only
the rows to CSV or Excel does not preserve that report. After aggregation,
concordance queries see the new labels and do not reconstruct original
membership.

API reference: :doc:`db.get_aggregation() <../../api_document/mario.CoreModel.get_aggregation>`
and :doc:`db.aggregate() <../../api_document/mario.Database.aggregate>`.

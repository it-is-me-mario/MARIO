mario.CoreModel.get_aggregation
===============================

.. currentmodule:: mario

.. automethod:: CoreModel.get_aggregation

See :doc:`Aggregating by classification <../user_guide/transformations/classification_aggregation>`
for hierarchy levels, a worked GLORIA example, unresolved-item reports and
application with ``aggregate``. ``get_aggregation`` prepares the complete
selected set; it does not accept an item or region filter.

``unresolved="keep"`` retains original labels alongside standard groups.
Use ``unresolved="raise"`` to require one target group for every item.
Availability of a correspondence alone does not establish availability of a
hierarchy preset; inspect :attr:`~mario.CoreModel.available_aggregations`.

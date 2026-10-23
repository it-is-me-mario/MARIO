mario.CoreModel.get_concordances
================================

.. currentmodule:: mario

.. automethod:: CoreModel.get_concordances

See :doc:`Classification concordances <../user_guide/inspection/concordances>`
for native-set selection, all supported editions, regional lookups, output
examples and interpretation of source qualifications.

Return contract
---------------

``details=False`` returns ``{native_item: [target_codes]}``.
``details=True`` returns ``{native_item: record}``, where each record contains
``codes``, ``classification``, ``native_code``, ``native_name``, ``status``,
``matches``, ``sources``, ``as_of``, ``profile`` and ``note``.

``matches[code]`` holds a description and a list of routes. Each route records
its nodes, steps, status, mapping origin and note; source records are keyed
by the IDs referenced in the steps. A mapped result can retain partial overlaps.

An item absent from the current set raises ``WrongInput``. A current item
without a verified link returns an empty code list. An unsupported database
variant or target edition also raises ``WrongInput``; check
:attr:`~mario.CoreModel.available_concordances` and
:attr:`~mario.CoreModel.database_profile` for availability.

To prepare a model aggregation, use
:meth:`~mario.CoreModel.get_aggregation`. Code lists alone provide no allocation
weights and cannot be used to divide a native item among several groups.

mario.CoreModel.get_configuration
=================================

.. currentmodule:: mario

Inspect the configuration of a selected scenario. The returned immutable
``ModelConfiguration`` exposes ``table_format``, ``regional_scope``,
``trade_representation``, ``import_representation``, ``imports_by``,
``trade_resolution``, ``tech_assumption`` and ``sector_type``.
``to_dict()`` returns independent serializable values.

See :doc:`model configurations <../get_started/table_formats>` and
:doc:`separate import accounts <../user_guide/transformations/import_accounts>`.

.. automethod:: CoreModel.get_configuration

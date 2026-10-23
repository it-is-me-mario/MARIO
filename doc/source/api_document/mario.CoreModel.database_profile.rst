mario.CoreModel.database_profile
================================

.. currentmodule:: mario

.. autoproperty:: CoreModel.database_profile

See :doc:`the database profile guide <../user_guide/advanced/database_profiles>`
for the shared GHG, compute and concordance metadata contract.

This property describes a parsed model. To inspect a family before parsing,
call :func:`mario.get_database_profile` with its family name.
``ghg["selected_profile"]`` is autodetected from source/name metadata;
``compute["parser_presets"]`` describes parser preferences, while
``mario.download_settings()["compute"]`` reports the active session.

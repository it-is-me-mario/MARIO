mario.get_database_profile
==========================

.. currentmodule:: mario

.. autofunction:: get_database_profile

.. code-block:: python

    import mario

    all_families = mario.get_database_profile()
    family = mario.get_database_profile("gloria")  # No database parse.
    model = mario.get_database_profile(db)         # Same as db.database_profile.

The family view includes every bundled variant. Model metadata, selected GHG
profile and native-set availability are ``None`` until a parsed database is
provided. See :doc:`Database profiles <../user_guide/advanced/database_profiles>`
for the fields, availability rules and distinction from active compute settings.

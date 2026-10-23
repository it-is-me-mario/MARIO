mario.CoreModel.available_concordances
======================================

.. currentmodule:: mario

.. autoproperty:: CoreModel.available_concordances

Use this property to discover target editions for each native productive set::

    db.available_concordances
    # {'Activity': ['NACE Rev. 2.1', ...], 'Commodity': ['CPA 2.2', ...]}

A listed target has a supported correspondence route, which may cover only
some items. Inspect individual results with
:meth:`~mario.CoreModel.get_concordances` and ``details=True`` for qualifications.

An unsupported source variant raises ``WrongInput``. To inspect family support
and the reason for model unavailability without making a lookup, use
``db.database_profile["concordances"]``. A correspondence target may lack an
aggregation hierarchy; see :attr:`~mario.CoreModel.available_aggregations`.

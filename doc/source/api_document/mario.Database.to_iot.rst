mario.Database.to\_iot
======================

.. currentmodule:: mario

.. automethod:: Database.to_iot

See :doc:`Convert a SUT to an IOT </user_guide/transformations/sut_to_iot>`
for the assumptions behind methods A–D, allocation examples and equations.

NAM databases expose :meth:`nam.to_iot() <mario.api.nam.NAMDatabase.to_iot>`
with a different signature: ``nam.to_iot(method, region=None)`` returns a
new IOT through the supported national FIGARO SUT projection and preserves
all scenarios. See :doc:`NAM to SUT or IOT </user_guide/transformations/nam_to_sut>`.

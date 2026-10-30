mario.Database.add\_sectors
===========================

.. currentmodule:: mario

For sequential IOT splits, checkpointing and numerical result handling, see
:doc:`../user_guide/transformations/intermediate_sector_steps`.

Prepare the editable worksheet with
:meth:`Database.get_add_sectors_intermediate_steps_plan`. Execution reads the
saved sheet and does not automatically regenerate its order.

With ``intermediate_steps=True``, ``on_step_failure="raise"`` stops at the
first failed optimisation. ``on_step_failure="continue"`` keeps its sectors
in their parents and attempts the following group, retaining the original
inventories and targets. Each group is attempted once per call.

.. automethod:: Database.add_sectors

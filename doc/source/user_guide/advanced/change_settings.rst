Change Settings
===============

This workflow covers the small set of packaged MARIO settings that are meant to
be changed explicitly by users at runtime.

Main entry points
-----------------

The most relevant settings helpers are collected in
:doc:`/reference/api_settings_methods`.

The main ones are:

* ``mario.set_compute_method(...)``;
* ``mario.set_linear_solver(...)``;
* ``mario.set_linear_strategy(...)``;
* ``mario.reset_settings()``.

Typical use
-----------

For example:

.. code-block:: python

   import mario

   mario.set_compute_method("solve")
   mario.set_linear_solver("scipy")
   mario.set_linear_strategy("auto")

These settings affect the default compute behavior used later by operations such
as dotted access and ``calc_all(...)`` when no per-call override is passed.

When to use this workflow
-------------------------

This page is mainly relevant when:

* you want to change the default compute strategy globally for one session;
* you are working with large databases and want more control over the solve path;
* you want to restore the packaged defaults cleanly.

Resetting defaults
------------------

To go back to the packaged defaults:

.. code-block:: python

   mario.reset_settings()

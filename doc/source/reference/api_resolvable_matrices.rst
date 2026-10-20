Resolvable Matrices and Blocks
==============================

Not every computed result in MARIO has a dedicated Python method. Many are
exposed as named blocks that you access through the generic compute API:

.. code-block:: python

   db.resolve("Xa")
   db.resolve_many(["u", "s", "Xc"])
   db.calc_all(["fc", "pc"])
   db.Xa
   db.wcc

Use :doc:`../api_document/mario.CoreModel.available_matrices` to list the block
names accepted by the current table, and
:doc:`../api_document/mario.CoreModel.get_block_spec` to inspect their semantic
axes.

For SUT databases, the built-in split and quadrant blocks include ``U``, ``u``,
``S``, ``s``, ``Xa``, ``Xc``, ``Va``, ``Vc``, ``Ea``, ``Ec``, ``Ya``, ``Yc``,
``wcc``, ``wca``, ``wac``, ``waa``, ``fa``, ``fc``, ``ma``, ``mc``, ``pa`` and
``pc``. The canonical commodity production vector name is ``Xc``; ``Cx`` is
not a built-in MARIO matrix name.

Core equations
--------------

IOT results follow the equations in :doc:`api_calculation_methods`. For SUT,
``u`` maps activity production to commodity inputs and ``s`` maps commodity
demand to activity production. The technology assumption determines the
construction of ``s``; see :doc:`/get_started/table_formats`.
Once those coefficients are available, the four Leontief quadrants are:

.. math::

   \begin{aligned}
   w_{cc} &= (I-us)^{-1}, & w_{ca} &= w_{cc}u, \\
   w_{aa} &= (I-su)^{-1}, & w_{ac} &= w_{aa}s.
   \end{aligned}

The total environmental multipliers include direct coefficients on both sides:

.. math::

   f_a = (e_a+e_cu)w_{aa}, \qquad f_c = (e_as+e_c)w_{cc}.

The value-added multipliers ``ma`` and ``mc`` use the same equations with
:math:`v_a` and :math:`v_c` in place of :math:`e_a` and :math:`e_c`.
The price vectors sum all factor rows:

.. math::

   p_a = m_a^{\mathsf{T}}\mathbf{1}, \qquad
   p_c = m_c^{\mathsf{T}}\mathbf{1}.

The solve path evaluates the same multipliers through transposed linear
systems. For example:

.. math::

   (I-us)^{\mathsf{T}} f_c^{\mathsf{T}} = (e_as+e_c)^{\mathsf{T}}.

This avoids constructing ``wcc`` when it is not otherwise needed. Runtime
settings and already materialized blocks determine the selected path;
``db.explain("fc")`` describes the current dependency plan. An already stored
result is returned directly, so that plan does not reconstruct how it was
originally calculated.

Block catalog
-------------

The reference table below reuses the authoritative nomenclature matrix catalog
and therefore covers both IOT and SUT built-ins, along with their table format,
mode and default axes.

.. raw:: html
   :file: ../get_started/_generated/matrices_table.html

Resolvable Matrices and Blocks
==============================

The database compute API resolves named blocks and their dependencies for a
scenario. Standalone ``calc_*`` functions are listed in
:doc:`api_calculation_methods`. To request blocks from a database:

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

Use and supply coefficients
---------------------------

The native use and supply calculations have dedicated block pages:

* :doc:`db.u — use coefficients <../api_document/mario.CoreModel.lower_u>`
* :doc:`db.U — use flows <../api_document/mario.CoreModel.U>`
* :doc:`db.s — supply coefficients <../api_document/mario.CoreModel.lower_s>`
* :doc:`db.S — supply flows <../api_document/mario.CoreModel.S>`
* :doc:`db.c — product mix <../api_document/mario.CoreModel.c>`

In particular, ``u`` divides each use-flow column by activity production.
``s`` follows the database technology assumption:

.. math::

   u=U\operatorname{diag}(X_a)^{-1},\qquad
   s=\begin{cases}
   S\operatorname{diag}(X_c)^{-1} & \text{IT},\\
   \left(S^{\mathsf{T}}\operatorname{diag}(X_a)^{-1}\right)^{-1} & \text{PT}.
   \end{cases}

The :doc:`native SUT calculation reference <api_calculation_methods>` also
links production vectors, Leontief/Ghosh quadrants, direct-output coefficients
and price vectors.

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


Detailed block reference
------------------------

These pages describe database access to the native SUT blocks and link to
the corresponding standalone ``calc_*`` functions.

.. toctree::
   :hidden:
   :maxdepth: 1

   ../api_document/mario.CoreModel.lower_u
   ../api_document/mario.CoreModel.U
   ../api_document/mario.CoreModel.lower_s
   ../api_document/mario.CoreModel.S
   ../api_document/mario.CoreModel.c
   ../api_document/mario.CoreModel.Xa
   ../api_document/mario.CoreModel.Xc
   ../api_document/mario.CoreModel.wcc
   ../api_document/mario.CoreModel.wca
   ../api_document/mario.CoreModel.wac
   ../api_document/mario.CoreModel.waa
   ../api_document/mario.CoreModel.bu
   ../api_document/mario.CoreModel.bs
   ../api_document/mario.CoreModel.gcc
   ../api_document/mario.CoreModel.gca
   ../api_document/mario.CoreModel.gac
   ../api_document/mario.CoreModel.gaa
   ../api_document/mario.CoreModel.pa
   ../api_document/mario.CoreModel.pc

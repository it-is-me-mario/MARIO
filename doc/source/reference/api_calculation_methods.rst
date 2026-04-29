Calculations
============

These methods compute matrices, indicators and standalone IOT formula outputs.
For normal database workflows, prefer the database compute API because it
understands scenarios, table format and already materialized matrices.

Database Compute API
--------------------

.. list-table::
   :header-rows: 1

   * - Method
     - Use
   * - :doc:`db.calc_all(...) <../api_document/mario.CoreModel.calc_all>`
     - Materialize one or more requested matrices in a scenario.
   * - :doc:`db.resolve(...) <../api_document/mario.CoreModel.resolve>`
     - Resolve one matrix and return the materialized block.
   * - :doc:`db.resolve_many(...) <../api_document/mario.CoreModel.resolve_many>`
     - Resolve several matrices and return a mapping.
   * - :doc:`db.calc_linkages(...) <../api_document/mario.Database.calc_linkages>`
     - Calculate backward and forward linkage indicators.

.. toctree::
   :maxdepth: 1

   ../api_document/mario.CoreModel.calc_all
   ../api_document/mario.CoreModel.resolve
   ../api_document/mario.CoreModel.resolve_many
   ../api_document/mario.Database.calc_linkages


SUT-specific Ghosh matrices
---------------------------

For SUT databases, MARIO resolves Ghosh blocks with the split structure used in
the :doc:`Matrices table in Nomenclature </concepts/nomenclature>`:
``bu``, ``bs``, ``gcc``, ``gca``, ``gac`` and ``gaa``. Materialize them with
``db.calc_all(["bu", "bs", "gcc", "gca", "gac", "gaa"])`` or resolve a
single block with ``db.resolve("gcc")``.


Runtime Compute Options
-----------------------

Demand-driven matrices such as the ``X`` total production vector, the ``f``
total (direct+indirect) environmental transaction coefficients matrix, the
``F`` total (direct+indirect) environmental transaction flows matrix, the ``m``
total (direct+indirect) value added coefficients matrix, the ``M`` total
(direct+indirect) value added transaction matrix and the ``p`` price index
vector can be computed either through the explicit ``w`` Leontief inverse
matrix or through linear-system solves.

See :doc:`mario.set_compute_method <../api_document/mario.set_compute_method>`,
:doc:`mario.set_linear_solver <../api_document/mario.set_linear_solver>` and
:doc:`mario.set_linear_strategy <../api_document/mario.set_linear_strategy>`.


Standalone IOT Helpers
----------------------

The functions below operate on pandas matrices directly. They do not mutate a
``Database`` and they do not infer missing inputs. Matrix names and
descriptions follow the :doc:`Matrices table in Nomenclature
</concepts/nomenclature>`.

.. list-table::
   :header-rows: 1

   * - Function
     - Calculation
   * - ``calc_X(Z, Y)``
     - ``X`` total production vector from ``Z`` intersectoral transaction flows matrix and ``Y`` final demand matrix.
   * - ``calc_z(Z, X)``
     - ``z`` intersectoral transaction coefficients matrix from ``Z`` and ``X``.
   * - ``calc_Z(z, X)``
     - ``Z`` intersectoral transaction flows matrix from ``z`` and ``X``.
   * - ``calc_w(z)``
     - ``w`` Leontief inverse matrix.
   * - ``calc_X_from_w(w, Y)``
     - ``X`` total production vector using a precomputed ``w``.
   * - ``calc_X_from_z(z, Y)``
     - ``X`` total production vector directly from ``z`` and ``Y``.
   * - ``calc_v(V, X)`` / ``calc_V(v, X)``
     - Convert between ``V`` value added transaction flows matrix and ``v`` value added coefficients matrix.
   * - ``calc_e(E, X)`` / ``calc_E(e, X)``
     - Convert between ``E`` environmental transaction flows matrix and ``e`` environmental transaction coefficients matrix.
   * - ``calc_m(v, w)`` / ``calc_m_from_z(v, z)``
     - ``m`` total (direct+indirect) value added coefficients matrix.
   * - ``calc_f(e, w)`` / ``calc_f_from_z(e, z)``
     - ``f`` total (direct+indirect) environmental transaction coefficients matrix.
   * - ``calc_M(m, Y)``
     - ``M`` total (direct+indirect) value added transaction matrix.
   * - ``calc_F(f, Y)``
     - ``F`` total (direct+indirect) environmental transaction flows matrix.
   * - ``calc_p(v, w)`` / ``calc_p_from_z(v, z)``
     - ``p`` price index vector.
   * - ``calc_b(X, Z)`` / ``calc_g(b)``
     - ``b`` intersectoral transaction direct-output coefficients matrix and ``g`` Ghosh coefficients matrix.
   * - ``calc_y(Y)``
     - Shares of the ``Y`` final demand matrix.

.. toctree::
   :maxdepth: 1

   ../api_document/mario.calc_X
   ../api_document/mario.calc_lower_z
   ../api_document/mario.calc_Z
   ../api_document/mario.calc_w
   ../api_document/mario.calc_X_from_z
   ../api_document/mario.calc_X_from_w
   ../api_document/mario.calc_lower_v
   ../api_document/mario.calc_V
   ../api_document/mario.calc_lower_e
   ../api_document/mario.calc_E
   ../api_document/mario.calc_lower_m
   ../api_document/mario.calc_m_from_z
   ../api_document/mario.calc_M
   ../api_document/mario.calc_lower_f
   ../api_document/mario.calc_f_from_z
   ../api_document/mario.calc_f_dis
   ../api_document/mario.calc_F
   ../api_document/mario.calc_p
   ../api_document/mario.calc_p_from_z
   ../api_document/mario.calc_b
   ../api_document/mario.calc_g
   ../api_document/mario.calc_y


Exploded Multiplier Matrices
-----------------------------

These methods decompose multiplier (``f``, ``m``) matrices by stacking
one scaled transfer matrix per account/factor, yielding a ``(account, region,
sector)`` MultiIndex result. IOT and SUT use separate methods.

The ``_all`` property variants (e.g. ``db.f_ex_all``) are zero-argument
shorthands that return the full matrix for all accounts/factors at baseline
scenario. Use the method form (e.g. ``db.f_ex(...)``) to filter or select a
different scenario.

.. list-table::
   :header-rows: 1

   * - Method
     - Property shorthand
     - Table
     - Formula
   * - :doc:`db.f_ex(...) <../api_document/mario.CoreModel.f_ex>`
     - :doc:`db.f_ex_all <../api_document/mario.CoreModel.f_ex_all>`
     - IOT
     - ``diag(e_k) @ w``
   * - :doc:`db.fa_ex(...) <../api_document/mario.CoreModel.fa_ex>`
     - :doc:`db.fa_ex_all <../api_document/mario.CoreModel.fa_ex_all>`
     - SUT
     - ``diag(ea_k) @ waa``
   * - :doc:`db.fc_ex(...) <../api_document/mario.CoreModel.fc_ex>`
     - :doc:`db.fc_ex_all <../api_document/mario.CoreModel.fc_ex_all>`
     - SUT
     - ``diag(ea_k) @ (s @ wcc)``
   * - :doc:`db.m_ex(...) <../api_document/mario.CoreModel.m_ex>`
     - :doc:`db.m_ex_all <../api_document/mario.CoreModel.m_ex_all>`
     - IOT
     - ``diag(v_f) @ w``
   * - :doc:`db.ma_ex(...) <../api_document/mario.CoreModel.ma_ex>`
     - :doc:`db.ma_ex_all <../api_document/mario.CoreModel.ma_ex_all>`
     - SUT
     - ``diag(va_f) @ waa``
   * - :doc:`db.mc_ex(...) <../api_document/mario.CoreModel.mc_ex>`
     - :doc:`db.mc_ex_all <../api_document/mario.CoreModel.mc_ex_all>`
     - SUT
     - ``diag(va_f) @ (s @ wcc)``

.. toctree::
   :maxdepth: 1

   ../api_document/mario.CoreModel.f_ex
   ../api_document/mario.CoreModel.f_ex_all
   ../api_document/mario.CoreModel.fa_ex
   ../api_document/mario.CoreModel.fa_ex_all
   ../api_document/mario.CoreModel.fc_ex
   ../api_document/mario.CoreModel.fc_ex_all
   ../api_document/mario.CoreModel.m_ex
   ../api_document/mario.CoreModel.m_ex_all
   ../api_document/mario.CoreModel.ma_ex
   ../api_document/mario.CoreModel.ma_ex_all
   ../api_document/mario.CoreModel.mc_ex
   ../api_document/mario.CoreModel.mc_ex_all

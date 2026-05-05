Calculations
============

These methods compute matrices, indicators and standalone IOT/SUT formula outputs.
For normal database workflows, prefer the database compute API because it
understands scenarios, table format and already materialized matrices.

For a compact spreadsheet overview of the nomenclature and worked matrix
calculations on the MARIO test ``IOT``, ``SUT_IT`` and ``SUT_PT`` examples,
download the :download:`terminology workbook </_static/data/supporting_files/Terminology.xlsx>`.

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

For a minimal SUT example:

.. code-block:: python

   import mario

   sut = mario.load_test("SUT")
   sut.calc_all(["Xc", "u", "gac"])

   sut.Xc   # commodity production vector
   sut.u    # use coefficients
   sut.gac  # one SUT Ghosh quadrant

If you only need one block, ask the resolver directly:

.. code-block:: python

   fc = sut.resolve("fc")


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


SUT Activity-side Totals
------------------------

When unified final demand ``Y`` is available, MARIO builds the activity-side
final-demand total from commodity final demand ``Yc`` and the supply
coefficients matrix ``s``:

.. math::

  Y_a^{\mathrm{tot}} = s Y_c \mathbf{1}

The activity-side total value-added and satellite transaction matrices then
follow as:

.. math::

  M_a = ma \, \operatorname{diag}(Y_a^{\mathrm{tot}})

.. math::

  F_a = fa \, \operatorname{diag}(Y_a^{\mathrm{tot}})


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
   ../api_document/mario.calc_F
   ../api_document/mario.calc_p
   ../api_document/mario.calc_p_from_z
   ../api_document/mario.calc_b
   ../api_document/mario.calc_g
   ../api_document/mario.calc_y


Standalone SUT Split Helpers
----------------------------

The functions below operate on split SUT blocks directly. They are useful when
you already have activity-side and commodity-side blocks as pandas matrices and
want one standalone numerical helper instead of resolving through a
``Database``.

.. list-table::
   :header-rows: 1

   * - Function
     - Calculation
   * - ``calc_va(Va, Xa)`` / ``calc_Va(va, Xa)``
     - Convert between ``Va`` activity-side value added flows and ``va`` activity-side value added coefficients.
   * - ``calc_vc(Vc, Xc)`` / ``calc_Vc(vc, Xc)``
     - Convert between ``Vc`` commodity-side value added flows and ``vc`` commodity-side value added coefficients.
   * - ``calc_ea(Ea, Xa)`` / ``calc_Ea(ea, Xa)``
     - Convert between ``Ea`` activity-side environmental flows and ``ea`` activity-side environmental coefficients.
   * - ``calc_ec(Ec, Xc)`` / ``calc_Ec(ec, Xc)``
     - Convert between ``Ec`` commodity-side environmental flows and ``ec`` commodity-side environmental coefficients.
   * - ``calc_ma(va, waa)`` / ``calc_Ma(ma, s, Yc)``
     - Build activity-side value added multipliers and total activity-side value added footprints.
   * - ``calc_mc(va, s, wcc)`` / ``calc_Mc(mc, Yc)``
     - Build commodity-side value added multipliers and total commodity-side value added footprints.
   * - ``calc_fa(ea, waa)`` / ``calc_Fa(fa, s, Yc)``
     - Build activity-side environmental multipliers and total activity-side environmental footprints.
   * - ``calc_fc(ea, s, wcc)`` / ``calc_Fc(fc, Yc)``
     - Build commodity-side environmental multipliers and total commodity-side environmental footprints.

.. toctree::
   :maxdepth: 1

   ../api_document/mario.calc_Va
   ../api_document/mario.calc_Vc
   ../api_document/mario.calc_lower_va
   ../api_document/mario.calc_lower_vc
   ../api_document/mario.calc_Ea
   ../api_document/mario.calc_Ec
   ../api_document/mario.calc_lower_ea
   ../api_document/mario.calc_lower_ec
   ../api_document/mario.calc_lower_ma
   ../api_document/mario.calc_lower_mc
   ../api_document/mario.calc_Ma
   ../api_document/mario.calc_Mc
   ../api_document/mario.calc_lower_fa
   ../api_document/mario.calc_lower_fc
   ../api_document/mario.calc_Fa
   ../api_document/mario.calc_Fc

Deprecated Compatibility Helper
-------------------------------

``calc_f_dis`` remains available for backward compatibility, but it is no
longer the preferred way to inspect diagonalized environmental multipliers.
Prefer :doc:`db.f_ex(...) <../api_document/mario.CoreModel.f_ex>` for IOT and
:doc:`db.fa_ex(...) <../api_document/mario.CoreModel.fa_ex>` /
:doc:`db.fc_ex(...) <../api_document/mario.CoreModel.fc_ex>` for SUT.


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

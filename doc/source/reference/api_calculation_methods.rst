Calculations
============

These methods compute matrices, indicators and standalone IOT/SUT formula outputs.
For normal database workflows, prefer the database compute API because it
understands scenarios, table format and already materialized matrices.

For a compact spreadsheet overview of the nomenclature and worked matrix
calculations on the MARIO test ``IOT``, ``SUT_IT`` and ``SUT_PT`` examples,
download the :download:`dedicated workbook </_static/data/supporting_files/Terminology.xlsx>`.

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
   * - :doc:`db.explain(...) <../api_document/mario.CoreModel.explain>`
     - Explain which compute path MARIO would use for one matrix.
   * - :doc:`db.calc_linkages(...) <../api_document/mario.Database.calc_linkages>`
     - Calculate backward and forward linkage indicators.
   * - :doc:`db.calc_ghg(...) <../api_document/mario.Database.calc_ghg>`
     - Build a greenhouse-gas aggregate extension from selected satellite rows.
   * - :doc:`db.calc_trades(...) <../api_document/mario.Database.calc_trades>`
     - Aggregate one sector or commodity into a region-by-region trade matrix and optional heatmap.
   * - :doc:`db.calc_trades_content(...) <../api_document/mario.Database.calc_trades_content>`
     - Calculate embodied trade content and, with ``breakdown=True``, decompose it by contributor.
   * - :doc:`db.calc_trades_content_breakdown(...) <../api_document/mario.Database.calc_trades_content_breakdown>`
     - Shortcut for ``db.calc_trades_content(..., breakdown=True)``.
   * - :doc:`db.calc_spa(...) <../api_document/mario.Database.calc_spa>`
     - Enumerate demand-driven structural paths for one indicator and final-demand bundle.
   * - :doc:`db.calc_embodied_imports(...) <../api_document/mario.Database.calc_embodied_imports>`
     - Collapse embodied trade-content matrices into import accounts by destination Region.
   * - :doc:`db.calc_embodied_exports(...) <../api_document/mario.Database.calc_embodied_exports>`
     - Collapse embodied trade-content matrices into export accounts by origin Region.
   * - :doc:`db.calc_embodied_net_imports(...) <../api_document/mario.Database.calc_embodied_net_imports>`
     - Calculate embodied net imports as imports minus exports.
   * - :doc:`db.calc_trades_concentration(...) <../api_document/mario.Database.calc_trades_concentration>`
     - Calculate contributor-region concentration of embodied trade content.
   * - :doc:`db.calc_trades_exposure(...) <../api_document/mario.Database.calc_trades_exposure>`
     - Calculate embodied trade-content exposure to selected contributor Regions.

.. toctree::
  :maxdepth: 1

  ../api_document/mario.CoreModel.calc_all
  ../api_document/mario.CoreModel.resolve
  ../api_document/mario.CoreModel.resolve_many
  ../api_document/mario.CoreModel.explain
  ../api_document/mario.Database.calc_linkages
  ../api_document/mario.Database.calc_ghg
  ../api_document/mario.Database.calc_trades
  ../api_document/mario.Database.calc_trades_content
  ../api_document/mario.Database.calc_trades_content_breakdown
  ../api_document/mario.Database.calc_spa
  ../api_document/mario.Database.calc_embodied_imports
  ../api_document/mario.Database.calc_embodied_exports
  ../api_document/mario.Database.calc_embodied_net_imports
  ../api_document/mario.Database.calc_trades_concentration
  ../api_document/mario.Database.calc_trades_exposure
  api_resolvable_matrices


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


Resolvable Database Blocks
--------------------------

Many SUT and IOT results do not have dedicated Python methods. They are still
part of the public compute API through ``db.resolve(...)``, ``db.resolve_many(...)``,
``db.calc_all(...)`` and dotted access such as ``db.Xa`` or ``db.wcc``.

See :doc:`api_resolvable_matrices` for the authoritative list of built-in block
names currently supported by MARIO.


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
     - Formula
   * - ``calc_X(Z, Y)``
     - ``X`` total production vector from ``Z`` intersectoral transaction flows matrix and ``Y`` final demand matrix.
     - ``X = Z 1 + Y 1``
   * - ``calc_z(Z, X)``
     - ``z`` intersectoral transaction coefficients matrix from ``Z`` and ``X``.
     - ``z = Z diag(X)^{-1}``
   * - ``calc_Z(z, X)``
     - ``Z`` intersectoral transaction flows matrix from ``z`` and ``X``.
     - ``Z = z diag(X)``
   * - ``calc_w(z)``
     - ``w`` Leontief inverse matrix.
     - ``w = (I - z)^{-1}``
   * - ``calc_X_from_w(w, Y)``
     - ``X`` total production vector using a precomputed ``w``.
     - ``X = w (Y 1)``
   * - ``calc_X_from_z(z, Y)``
     - ``X`` total production vector directly from ``z`` and ``Y``.
     - ``X = (I - z)^{-1} (Y 1)``
   * - ``calc_v(V, X)`` / ``calc_V(v, X)``
     - Convert between ``V`` value added transaction flows matrix and ``v`` value added coefficients matrix.
     - ``v = V diag(X)^{-1}``; ``V = v diag(X)``
   * - ``calc_e(E, X)`` / ``calc_E(e, X)``
     - Convert between ``E`` environmental transaction flows matrix and ``e`` environmental transaction coefficients matrix.
     - ``e = E diag(X)^{-1}``; ``E = e diag(X)``
   * - ``calc_m(v, w)`` / ``calc_m_from_z(v, z)``
     - ``m`` total (direct+indirect) value added coefficients matrix.
     - ``m = v w``; ``m = v (I - z)^{-1}``
   * - ``calc_f(e, w)`` / ``calc_f_from_z(e, z)``
     - ``f`` total (direct+indirect) environmental transaction coefficients matrix.
     - ``f = e w``; ``f = e (I - z)^{-1}``
   * - ``calc_M(m, Y)``
     - ``M`` total (direct+indirect) value added transaction matrix.
     - ``M = m diag(Y 1)``
   * - ``calc_F(f, Y)``
     - ``F`` total (direct+indirect) environmental transaction flows matrix.
     - ``F = f diag(Y 1)``
   * - ``calc_p(v, w)`` / ``calc_p_from_z(v, z)``
     - ``p`` price index vector.
     - ``p = w^T (v^T 1)``; ``p = (I - z)^{-T} (v^T 1)``
   * - ``calc_b(X, Z)`` / ``calc_g(b)``
     - ``b`` intersectoral transaction direct-output coefficients matrix and ``g`` Ghosh coefficients matrix.
     - ``b = diag(X)^{-1} Z``; ``g = (I - b)^{-1}``
   * - ``calc_y(Y)``
     - Shares of the ``Y`` final demand matrix.
     - ``y = Y / (1^T Y 1)``

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
     - Formula
   * - ``calc_va(Va, Xa)`` / ``calc_Va(va, Xa)``
     - Convert between ``Va`` activity-side value added flows and ``va`` activity-side value added coefficients.
     - ``va = Va diag(Xa)^{-1}``; ``Va = va diag(Xa)``
   * - ``calc_vc(Vc, Xc)`` / ``calc_Vc(vc, Xc)``
     - Convert between ``Vc`` commodity-side value added flows and ``vc`` commodity-side value added coefficients.
     - ``vc = Vc diag(Xc)^{-1}``; ``Vc = vc diag(Xc)``
   * - ``calc_ea(Ea, Xa)`` / ``calc_Ea(ea, Xa)``
     - Convert between ``Ea`` activity-side environmental flows and ``ea`` activity-side environmental coefficients.
     - ``ea = Ea diag(Xa)^{-1}``; ``Ea = ea diag(Xa)``
   * - ``calc_ec(Ec, Xc)`` / ``calc_Ec(ec, Xc)``
     - Convert between ``Ec`` commodity-side environmental flows and ``ec`` commodity-side environmental coefficients.
     - ``ec = Ec diag(Xc)^{-1}``; ``Ec = ec diag(Xc)``
   * - ``calc_ma(va, waa)`` / ``calc_Ma(ma, s, Yc)``
     - Build activity-side value added multipliers and total activity-side value added footprints.
     - ``ma = va waa``; ``Ma = ma diag(s (Yc 1))``
   * - ``calc_mc(va, s, wcc)`` / ``calc_Mc(mc, Yc)``
     - Build commodity-side value added multipliers and total commodity-side value added footprints.
     - ``mc = va s wcc``; ``Mc = mc diag(Yc 1)``
   * - ``calc_fa(ea, waa)`` / ``calc_Fa(fa, s, Yc)``
     - Build activity-side environmental multipliers and total activity-side environmental footprints.
     - ``fa = ea waa``; ``Fa = fa diag(s (Yc 1))``
   * - ``calc_fc(ea, s, wcc)`` / ``calc_Fc(fc, Yc)``
     - Build commodity-side environmental multipliers and total commodity-side environmental footprints.
     - ``fc = ea s wcc``; ``Fc = fc diag(Yc 1)``

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



Exploded Multiplier Matrices
-----------------------------

These methods decompose multiplier (``f``, ``m``, ``p``) matrices by stacking
scaled transfer matrices. IOT and SUT use separate methods.

The ``f_ex`` and ``m_ex`` families return a ``(account/factor, region,
sector)`` MultiIndex on rows, while the ``p_ex`` family returns aggregated
contributions whose rows identify the contributing region-sector.

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
   * - :doc:`db.p_ex(...) <../api_document/mario.CoreModel.p_ex>`
     - :doc:`db.p_ex_all <../api_document/mario.CoreModel.p_ex_all>`
     - IOT
     - ``diag(v @ 1) @ w``
   * - :doc:`db.pa_ex(...) <../api_document/mario.CoreModel.pa_ex>`
     - :doc:`db.pa_ex_all <../api_document/mario.CoreModel.pa_ex_all>`
     - SUT
     - ``diag(va @ 1) @ waa``
   * - :doc:`db.pc_ex(...) <../api_document/mario.CoreModel.pc_ex>`
     - :doc:`db.pc_ex_all <../api_document/mario.CoreModel.pc_ex_all>`
     - SUT
     - ``diag(va @ 1) @ (s @ wcc)``

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
   ../api_document/mario.CoreModel.p_ex
   ../api_document/mario.CoreModel.p_ex_all
   ../api_document/mario.CoreModel.pa_ex
   ../api_document/mario.CoreModel.pa_ex_all
   ../api_document/mario.CoreModel.pc_ex
   ../api_document/mario.CoreModel.pc_ex_all

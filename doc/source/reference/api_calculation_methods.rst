Calculations
============

These methods compute matrices, indicators and standalone IOT/SUT formula outputs.
For normal database workflows, prefer the database compute API because it
understands scenarios, table format and already materialized matrices.

For a compact spreadsheet overview of the nomenclature and worked matrix
calculations on the MARIO test ``IOT``, ``SUT_IT`` and ``SUT_PT`` examples,
download the :download:`nomenclature and formulas workbook </_static/data/supporting_files/Nomenclature_and_formulas.xlsx>`.

Reading the formulas
--------------------

Each standalone helper below documents its equation, inputs and returned axes.
The same information is available in Python with, for example,
``help(mario.calc_fc)``. Matrix products use ordinary mathematical multiplication
in equations and ``@`` in Python.

* :math:`I` is the identity matrix and :math:`\mathbf{1}` is a vector of ones
  with the length required by the product.
* :math:`\operatorname{diag}(x)` puts a vector on the diagonal.
  :math:`\mathsf{T}` denotes transpose.
* :math:`Y\mathbf{1}` sums final-demand categories and regions **for each
  production node**. It is ``Y.sum(axis=1)`` in Python, not the matrix ``Y``.
* Subscripts :math:`a` and :math:`c` identify activity and commodity nodes in
  SUT formulas: :math:`e_a` is ``ea``, :math:`f_c` is ``fc`` and
  :math:`w_{aa}` is ``waa`` in the API.

For example, :math:`F=f\operatorname{diag}(Y\mathbf{1})` returns accounts by
production nodes. To retain the final-demand category columns, use the separate
matrix product ``f @ Y`` instead.

Coefficient helpers use an elementwise inverse of production, assigning zero
to inverse entries where production is zero. The notation
:math:`\operatorname{diag}(X)^{-1}` describes this convention even when the
diagonal matrix would be singular.

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
  :hidden:
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

The optional UMFPACK backend uses sparse direct LU for solve-based IOT and SUT
targets. Install ``scikit-umfpack`` and its SuiteSparse libraries, then select:

.. code-block:: python

   mario.set_compute_method("solve")
   mario.set_linear_solver("umfpack")
   mario.set_linear_strategy("direct")

``auto`` is also supported as the linear strategy and selects direct solves
for UMFPACK. The ``iterative`` strategy requires the SciPy backend. Selecting
UMFPACK does not change matrices that are already materialized. It preserves
float64 precision and raises an error for failed solves instead of applying a
pseudo-inverse or least-squares fallback.
Sparse factorization uses 64-bit indices and compares fill-reducing orderings.
Singular diagonal blocks are diagnosed before native factorization, with the
affected node labels in the error message. Selecting a faster solver cannot
make a singular system invertible.

Singular systems raise an error by default. To request only independently
determined coefficients, enable the partial policy explicitly:

.. code-block:: python

   mario.set_singular_policy("partial")
   fc = db.fc

This policy applies to solve-based IOT and SUT targets with either SciPy or
UMFPACK, using a direct or automatic linear strategy. Singular components and
every coefficient depending on them become ``NaN``; the remaining equations
are solved without changing their coefficients or right-hand sides. The
residual check applies to this independent subsystem, not to the full singular
system, which may be inconsistent or have nonunique solutions. Full inverse
requests still raise an error.

A :doc:`mario.PartialResultWarning <../api_document/mario.PartialResultWarning>`
reports the singular node labels and the affected coefficient count whenever
a partial result is computed. The result's ``attrs["mario_partial"]`` records
the singular components and all affected node labels. MARIO compute reductions
and products preserve undefined values; when using pandas directly, pass
``skipna=False`` to reductions such as ``fc.sum(axis=1, skipna=False)``.
User-defined pandas operations retain pandas' usual missing-value behavior.

Use ``db.resolve("fc", compute_options=mario.ComputeOptions(
backend_override="sparse_direct", singular_policy="partial"))`` for a
per-call override. See
:doc:`mario.set_singular_policy <../api_document/mario.set_singular_policy>`.
Changing the policy does not recompute already materialized matrices.


Resolvable Database Blocks
--------------------------

SUT and IOT results can also be requested as named blocks through
``db.resolve(...)``, ``db.resolve_many(...)``,
``db.calc_all(...)`` and dotted access such as ``db.Xa`` or ``db.wcc``.

See :doc:`api_resolvable_matrices` for the authoritative list of built-in block
names currently supported by MARIO.


Standalone SUT Use, Supply and Quadrant Helpers
-----------------------------------------------

These functions operate directly on pandas matrices, like ``calc_X`` and
``calc_z``. They return a result without changing a database. Open a function
for its signature, inputs, formula and returned axes.

.. code-block:: python

   u = mario.calc_u(U, Xa)
   s = mario.calc_s(S, Xc)  # Industry-based technology (IT).
   s_pt = mario.calc_s(S, Xa=Xa, tech_assumption="PT")
   wcc = mario.calc_wcc(u, s)

For scenario-aware calculation and automatic input resolution, the same
blocks remain available through the :doc:`database compute API
<api_resolvable_matrices>`.

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Function
     - Formula
   * - :func:`~mario.calc_u`
     - .. math::

          u = U\operatorname{diag}(X_a)^{-1}
   * - :func:`~mario.calc_U`
     - .. math::

          U = u\operatorname{diag}(X_a)
   * - :func:`~mario.calc_s`
     - .. math::

          s = \begin{cases}
              S\operatorname{diag}(X_c)^{-1} & \text{IT},\\
              \left(S^{\mathsf{T}}\operatorname{diag}(X_a)^{-1}\right)^{-1}
              & \text{PT}.
          \end{cases}
   * - :func:`~mario.calc_S`
     - .. math::

          S = \begin{cases}
              s\operatorname{diag}(X_c) & \text{IT},\\
              \left(c\operatorname{diag}(X_a)\right)^{\mathsf{T}},
              \quad c=s^{-1} & \text{PT}.
          \end{cases}
   * - :func:`~mario.calc_c`
     - .. math::

          c = S^{\mathsf{T}}\operatorname{diag}(X_a)^{-1}
   * - :func:`~mario.calc_Xa`
     - .. math::

          X_a = S\mathbf{1} + Y_a\mathbf{1}
   * - :func:`~mario.calc_Xc`
     - .. math::

          X_c = U\mathbf{1} + Y_c\mathbf{1}
   * - :func:`~mario.calc_wcc`
     - .. math::

          w_{cc} = (I-us)^{-1}
   * - :func:`~mario.calc_wca`
     - .. math::

          w_{ca} = (I-us)^{-1}u = w_{cc}u
   * - :func:`~mario.calc_wac`
     - .. math::

          w_{ac} = (I-su)^{-1}s = w_{aa}s
   * - :func:`~mario.calc_waa`
     - .. math::

          w_{aa} = (I-su)^{-1}
   * - :func:`~mario.calc_bu`
     - .. math::

          b_u = \operatorname{diag}(X_c)^{-1}U
   * - :func:`~mario.calc_bs`
     - .. math::

          b_s = \operatorname{diag}(X_a)^{-1}S
   * - :func:`~mario.calc_gcc`
     - .. math::

          g_{cc} = (I-b_u b_s)^{-1}
   * - :func:`~mario.calc_gca`
     - .. math::

          g_{ca} = g_{cc}b_u
   * - :func:`~mario.calc_gac`
     - .. math::

          g_{ac} = g_{aa}b_s
   * - :func:`~mario.calc_gaa`
     - .. math::

          g_{aa} = (I-b_s b_u)^{-1}
   * - :func:`~mario.calc_pa`
     - .. math::

          p_a = w_{aa}^{\mathsf{T}}v_a^{\mathsf{T}}\mathbf{1} + w_{ca}^{\mathsf{T}}v_c^{\mathsf{T}}\mathbf{1}
   * - :func:`~mario.calc_pc`
     - .. math::

          p_c = w_{ac}^{\mathsf{T}}v_a^{\mathsf{T}}\mathbf{1} + w_{cc}^{\mathsf{T}}v_c^{\mathsf{T}}\mathbf{1}

.. toctree::
   :hidden:
   :maxdepth: 1

   ../api_document/mario.calc_lower_u
   ../api_document/mario.calc_U
   ../api_document/mario.calc_lower_s
   ../api_document/mario.calc_S
   ../api_document/mario.calc_c
   ../api_document/mario.calc_Xa
   ../api_document/mario.calc_Xc
   ../api_document/mario.calc_wcc
   ../api_document/mario.calc_wca
   ../api_document/mario.calc_wac
   ../api_document/mario.calc_waa
   ../api_document/mario.calc_bu
   ../api_document/mario.calc_bs
   ../api_document/mario.calc_gcc
   ../api_document/mario.calc_gca
   ../api_document/mario.calc_gac
   ../api_document/mario.calc_gaa
   ../api_document/mario.calc_pa
   ../api_document/mario.calc_pc


Standalone IOT Helpers
----------------------

The functions below operate on pandas matrices directly. They do not mutate a
``Database`` and they do not infer missing inputs. Select a function for its signature, parameters and returned axes.
Matrix names and descriptions follow the :doc:`matrix catalogue
<api_resolvable_matrices>` and the :doc:`IOT guide </get_started/table_formats/iot>`.

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Function
     - Formula
   * - :func:`~mario.calc_X`
     - :math:`X = Z\mathbf{1} + Y\mathbf{1}`
   * - :func:`~mario.calc_z`
     - :math:`z = Z\operatorname{diag}(X)^{-1}`
   * - :func:`~mario.calc_Z`
     - :math:`Z = z\operatorname{diag}(X)`
   * - :func:`~mario.calc_w`
     - :math:`w = (I-z)^{-1}`
   * - :func:`~mario.calc_X_from_w`
     - :math:`X = w(Y\mathbf{1})`
   * - :func:`~mario.calc_X_from_z`
     - :math:`(I-z)X = Y\mathbf{1}`
   * - :func:`~mario.calc_v` / :func:`~mario.calc_V`
     - :math:`v = V\operatorname{diag}(X)^{-1}`

       :math:`V = v\operatorname{diag}(X)`
   * - :func:`~mario.calc_e` / :func:`~mario.calc_E`
     - :math:`e = E\operatorname{diag}(X)^{-1}`

       :math:`E = e\operatorname{diag}(X)`
   * - :func:`~mario.calc_m` / :func:`~mario.calc_m_from_z`
     - :math:`m = vw = v(I-z)^{-1}`
   * - :func:`~mario.calc_f` / :func:`~mario.calc_f_from_z`
     - :math:`f = ew = e(I-z)^{-1}`
   * - :func:`~mario.calc_M`
     - :math:`M = m\operatorname{diag}(Y\mathbf{1})`
   * - :func:`~mario.calc_F`
     - :math:`F = f\operatorname{diag}(Y\mathbf{1})`
   * - :func:`~mario.calc_p` / :func:`~mario.calc_p_from_z`
     - :math:`p = w^{\mathsf{T}}v^{\mathsf{T}}\mathbf{1}`
   * - :func:`~mario.calc_b` / :func:`~mario.calc_g`
     - :math:`b = \operatorname{diag}(X)^{-1}Z`

       :math:`g = (I-b)^{-1}`
   * - :func:`~mario.calc_y`
     - :math:`y = Y / (\mathbf{1}^{\mathsf{T}}Y\mathbf{1})`
   * - :func:`~mario.calc_f_dis`
     - :math:`f_{\mathrm{dis}} = \operatorname{diag}(e_k)w`

.. toctree::
   :hidden:
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
   ../api_document/mario.calc_f_dis


Standalone SUT Split Helpers
----------------------------

The functions below operate on split SUT blocks directly. They are useful when
you already have activity-side and commodity-side blocks as pandas matrices and
want one standalone numerical helper instead of resolving through a
``Database``.

The total multipliers include both activity-side and commodity-side direct
coefficients. In ``calc_ma`` / ``calc_fa``, supplying ``vc`` / ``ec`` also
requires ``u``. Omitting the commodity-side argument sets that term to zero.
Here :math:`u` has commodity rows and activity columns; :math:`s` has activity
rows and commodity columns. Consequently,
:math:`w_{aa}=(I-su)^{-1}` and :math:`w_{cc}=(I-us)^{-1}`.

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Function
     - Formula
   * - :func:`~mario.calc_va` / :func:`~mario.calc_Va`
     - :math:`v_a = V_a\operatorname{diag}(X_a)^{-1}`

       :math:`V_a = v_a\operatorname{diag}(X_a)`
   * - :func:`~mario.calc_vc` / :func:`~mario.calc_Vc`
     - :math:`v_c = V_c\operatorname{diag}(X_c)^{-1}`

       :math:`V_c = v_c\operatorname{diag}(X_c)`
   * - :func:`~mario.calc_ea` / :func:`~mario.calc_Ea`
     - :math:`e_a = E_a\operatorname{diag}(X_a)^{-1}`

       :math:`E_a = e_a\operatorname{diag}(X_a)`
   * - :func:`~mario.calc_ec` / :func:`~mario.calc_Ec`
     - :math:`e_c = E_c\operatorname{diag}(X_c)^{-1}`

       :math:`E_c = e_c\operatorname{diag}(X_c)`
   * - :func:`~mario.calc_ma` / :func:`~mario.calc_Ma`
     - :math:`m_a = (v_a+v_cu)w_{aa}`

       :math:`M_a = m_a\operatorname{diag}(s(Y_c\mathbf{1}))`
   * - :func:`~mario.calc_mc` / :func:`~mario.calc_Mc`
     - :math:`m_c = (v_as+v_c)w_{cc}`

       :math:`M_c = m_c\operatorname{diag}(Y_c\mathbf{1})`
   * - :func:`~mario.calc_fa` / :func:`~mario.calc_Fa`
     - :math:`f_a = (e_a+e_cu)w_{aa}`

       :math:`F_a = f_a\operatorname{diag}(s(Y_c\mathbf{1}))`
   * - :func:`~mario.calc_fc` / :func:`~mario.calc_Fc`
     - :math:`f_c = (e_as+e_c)w_{cc}`

       :math:`F_c = f_c\operatorname{diag}(Y_c\mathbf{1})`

.. toctree::
   :hidden:
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

In the formulas below, a two-block column means vertical concatenation:
activity contributors first, then commodity contributors.
The subscript ``k`` selects one satellite account and ``h`` selects one factor.
Summing contributor rows recovers the corresponding total coefficient or price
index. These are multiplier contributions; final demand is not applied.

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Method / table
     - Formula
   * - :doc:`db.f_ex(...) <../api_document/mario.CoreModel.f_ex>` (IOT)
     - :math:`f_{\mathrm{ex}} = \operatorname{diag}(e_k)\,w`
   * - :doc:`db.fa_ex(...) <../api_document/mario.CoreModel.fa_ex>` (SUT)
     - :math:`f_{a,\mathrm{ex}} = \begin{bmatrix} \operatorname{diag}(e_{a,k})w_{aa} \\ \operatorname{diag}(e_{c,k})w_{ca} \end{bmatrix}`
   * - :doc:`db.fc_ex(...) <../api_document/mario.CoreModel.fc_ex>` (SUT)
     - :math:`f_{c,\mathrm{ex}} = \begin{bmatrix} \operatorname{diag}(e_{a,k})s\,w_{cc} \\ \operatorname{diag}(e_{c,k})w_{cc} \end{bmatrix}`
   * - :doc:`db.m_ex(...) <../api_document/mario.CoreModel.m_ex>` (IOT)
     - :math:`m_{\mathrm{ex}} = \operatorname{diag}(v_h)\,w`
   * - :doc:`db.ma_ex(...) <../api_document/mario.CoreModel.ma_ex>` (SUT)
     - :math:`m_{a,\mathrm{ex}} = \begin{bmatrix} \operatorname{diag}(v_{a,h})w_{aa} \\ \operatorname{diag}(v_{c,h})w_{ca} \end{bmatrix}`
   * - :doc:`db.mc_ex(...) <../api_document/mario.CoreModel.mc_ex>` (SUT)
     - :math:`m_{c,\mathrm{ex}} = \begin{bmatrix} \operatorname{diag}(v_{a,h})s\,w_{cc} \\ \operatorname{diag}(v_{c,h})w_{cc} \end{bmatrix}`
   * - :doc:`db.p_ex(...) <../api_document/mario.CoreModel.p_ex>` (IOT)
     - :math:`p_{\mathrm{ex}} = \operatorname{diag}(v^{\mathsf{T}}\mathbf{1})\,w`
   * - :doc:`db.pa_ex(...) <../api_document/mario.CoreModel.pa_ex>` (SUT)
     - :math:`p_{a,\mathrm{ex}} = \begin{bmatrix} \operatorname{diag}(v_a^{\mathsf{T}}\mathbf{1})w_{aa} \\ \operatorname{diag}(v_c^{\mathsf{T}}\mathbf{1})w_{ca} \end{bmatrix}`
   * - :doc:`db.pc_ex(...) <../api_document/mario.CoreModel.pc_ex>` (SUT)
     - :math:`p_{c,\mathrm{ex}} = \begin{bmatrix} \operatorname{diag}(v_a^{\mathsf{T}}\mathbf{1})s\,w_{cc} \\ \operatorname{diag}(v_c^{\mathsf{T}}\mathbf{1})w_{cc} \end{bmatrix}`

.. toctree::
   :hidden:
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

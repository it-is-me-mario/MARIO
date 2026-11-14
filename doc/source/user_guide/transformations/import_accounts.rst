:page-type: Guide
:summary: Extract an open single-region model with native import flows and coefficients.

Separate import accounts
========================

.. container:: mario-companion

   :download:`Download notebook <import_accounts.ipynb>`

.. container:: mario-recipe

   .. code-block:: python

      import mario

      source = mario.load_test("SUT")
      regional = source.to_single_region(
          source.regions[0], imports_by="commodity",
          import_representation="separate", inplace=False,
      )
      factors = regional.query("Va")
      imported_use = regional.query("IMP_a")
      imported_supply = regional.query("IMP_c")
      imported_final = regional.query("IMP_Y")

   .. container:: mario-result

      Factor accounts contain the original primary inputs. External purchases
      have native import blocks, with the requested commodity descriptors.

Choose the representation
-------------------------

:meth:`db.to_single_region() <mario.Database.to_single_region>` and
:meth:`db.to_region_subset() <mario.Database.to_region_subset>` accept
``import_representation="separate"`` when exactly one region is retained.
The default ``"factor-accounts"`` keeps external imports in ``V`` or
``Va`` / ``Vc``, with direct final-demand imports in ``VY``.

``imports_by`` and ``trade_mode`` control detail in both representations.
IOT accepts ``"sector"``. SUT accepts ``"commodity"`` or ``"activity"``.
``None`` uses total imports with the default extraction layout.
``trade_mode="by_region"`` retains source regions. See
:doc:`regional extraction <mrio_to_srio>` for producer attribution and exports.

Import rows use existing Region and productive-classification descriptors.
Total foreign sourcing without a classification has one ``Total imports``
row with the descriptor name ``Import account``. No extra classification set
is needed. External source labels can include products or activities absent
from domestic production.

Switch an extracted database using
:meth:`db.to_import_representation() <mario.Database.to_import_representation>`.
The conversion applies to every scenario and preserves import detail.
It recognizes the explicit ``imports`` accounts created by extraction.

.. code-block:: python

   combined = regional.to_import_representation("factor-accounts", inplace=False)
   separated = combined.to_import_representation("separate", inplace=False)
   configuration = separated.configuration.to_dict()

Native blocks
-------------

IOT uses ``IMP`` for imports purchased by productive sectors and ``IMP_Y`` for
direct final-demand imports. SUT distinguishes use-side ``IMP_a`` from
supply-side ``IMP_c`` and direct final-demand ``IMP_Y``. A Chenery–Moses source
can carry imports on the supply side. Imports attached to either side remain
visible after extraction.

The IOT and SUT diagrams under :doc:`/get_started/table_formats` show the
additional row when single-region and separate imports are selected.
The :ref:`import matrix reference <separate-import-matrices>` lists all native
flows, coefficients and results.

Coefficients, requirements and prices
-------------------------------------

IOT import coefficients and total requirements follow

.. math::

   \mathrm{imp}=\mathrm{IMP}\,\widehat X^{-1},\qquad
   \mathrm{im}=\mathrm{imp}(I-z)^{-1},\qquad
   \mathrm{IM}=\mathrm{im}\,\operatorname{diag}(Y\mathbf 1).

For SUT, normalize each side by its own output vector. The existing technology
assumption determines ``s``.

.. math::

   \mathrm{imp}_a=\mathrm{IMP}_a\widehat X_a^{-1},\qquad
   \mathrm{imp}_c=\mathrm{IMP}_c\widehat X_c^{-1},

.. math::

   \mathrm{im}_a=(\mathrm{imp}_a+\mathrm{imp}_c u)(I-su)^{-1},\qquad
   \mathrm{im}_c=(\mathrm{imp}_a s+\mathrm{imp}_c)(I-us)^{-1}.

``im_a`` and ``im_c`` express the same import pathways on different output
bases. ``IM_a`` equals ``im_a s diag(Yc 1)`` and ``IM_c`` equals
``im_c diag(Yc 1)``, following the existing ``Ma`` / ``Mc`` conventions.
The unified SUT views ``IMP``, ``imp``, ``im`` and ``IM`` concatenate their
activity and commodity blocks. These allocations use commodity final output.
For arbitrary final demand including nonzero ``Ya``, apply the appropriate
coefficients to the resolved activity and commodity production vectors.
Direct final-demand imports remain in ``IMP_Y`` as absolute flows.

Prices include both primary-input and import requirements

.. math::

   p=m^{\mathsf T}\mathbf 1+\mathrm{im}^{\mathsf T}\mathbf 1,

.. math::

   p_a=m_a^{\mathsf T}\mathbf 1+\mathrm{im}_a^{\mathsf T}\mathbf 1,\qquad
   p_c=m_c^{\mathsf T}\mathbf 1+\mathrm{im}_c^{\mathsf T}\mathbf 1.

Balance diagnostics include imports once on the input side. In monetary IOTs,
``Z.T 1 + V.T 1 + IMP.T 1 = X``. SUT uses
``U.T 1 + Va.T 1 + IMP_a.T 1 = Xa`` and
``S.T 1 + Vc.T 1 + IMP_c.T 1 = Xc``. Factor multipliers and GDP calculated from
the separate factor blocks represent the retained primary inputs.

Aggregation, scenarios and files
--------------------------------

:meth:`db.aggregate() <mario.Database.aggregate>` maps productive classifications
and observed import descriptors together. Region descriptors of foreign
suppliers remain external to the model boundary.
Flow/coefficient resets retain native import blocks.
:meth:`db.update_scenarios() <mario.CoreModel.update_scenarios>` accepts native
import flows and coefficients with the same reset workflow as factor accounts.
SUT-to-IOT conversion carries import accounts into the resulting IOT.

:meth:`db.export() <mario.Database.export>` accepts import block names directly.
Excel, text and Parquet database exports include native import blocks and a
structural accounting manifest. Excel stores it in an ``accounting`` sheet.
Directory exports store ``accounting.json`` beside each mode's matrices.
Keep the manifest with the files when reloading with MARIO.
It records structural choices even when ``include_meta=False``.

:meth:`db.export_sets() <mario.Database.export_sets>` writes the native model
sets in a separate workbook. Import row descriptors are available on the
import matrices themselves. See :doc:`export and round trips
</user_guide/inspection/export_and_roundtrip>` for file choices.

API
---

* :attr:`db.configuration <mario.CoreModel.configuration>`
* :meth:`db.get_configuration() <mario.CoreModel.get_configuration>`
* :meth:`db.to_import_representation() <mario.Database.to_import_representation>`
* :meth:`db.to_single_region() <mario.Database.to_single_region>`

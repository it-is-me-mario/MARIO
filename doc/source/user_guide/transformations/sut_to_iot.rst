:page-type: Guide
:summary: Understand the four conversion methods and choose how to allocate inputs or sales.

Convert a SUT to an IOT
=======================

.. container:: mario-companion

   :download:`Download notebook <sut_to_iot.ipynb>`

A SUT records what each activity **uses** and **produces**, but an activity can
make several products. Converting it to an IOT requires an assumption about
how to assign those inputs or sales to a single productive set.

.. container:: mario-recipe

   .. code-block:: python

      import mario

      sut = mario.load_test("SUT")
      iot = sut.to_iot(method="B", inplace=False)
      iot.Z

   .. container:: mario-result

      **Result** · A product-by-product IOT. Its ``Sector`` labels and units
      come from the SUT's commodities. ``inplace=False`` keeps the SUT intact.

Choose the assumption
---------------------

In this guide, **product** means MARIO's ``Commodity`` and **industry** means
``Activity``. A symmetric IOT uses the same set on both axes; its values need
not be symmetric.

.. list-table::
   :header-rows: 1
   :widths: 13 27 60

   * - Method
     - IOT axes
     - What is held fixed?
   * - :ref:`A <sut-iot-method-a>`
     - Products
     - Input recipe of each product, across producers
   * - :ref:`B <sut-iot-method-b>`
     - Products
     - Input recipe of each industry, across its products
   * - :ref:`C <sut-iot-method-c>`
     - Industries
     - Customer proportions of each industry, across its products
   * - :ref:`D <sut-iot-method-d>`
     - Industries
     - Customer proportions of each product, across its producers

.. container:: mario-guide-facts

   **Check feasibility first.** A/C require a square, invertible supply matrix
   and zero activity final demand (``Ya``). B/D also support rectangular supply
   and nonzero ``Ya``. All methods retain the observed regional nodes; regional
   classifications need not be uniform.

Product-by-product IOT: A and B
-------------------------------

Both methods turn the **activity columns of use** into product columns.
The resulting ``Z`` records products used to produce other products.

.. _sut-iot-method-a:

A · Product technology
~~~~~~~~~~~~~~~~~~~~~~

**The recipe belongs to the product.** A product requires the same input
coefficients regardless of which industry makes it.

MARIO solves for product recipes that reproduce the observed industry inputs
and product mixes. Inputs associated with secondary production are therefore
assigned using that product's recipe.

.. container:: mario-flow

   **Example:** cakes made by a bread bakery use the cake recipe, even though
   bread is that bakery's main output. Their inputs need not follow the bakery's
   average input mix.

Use A when a common recipe across producers is a defensible assumption.
**Negative entries can appear**, even with nonnegative source flows. MARIO
keeps them; it does not adjust the data or substitute a pseudoinverse for a
singular supply matrix.

.. _sut-iot-method-b:

B · Industry technology
~~~~~~~~~~~~~~~~~~~~~~~

**The recipe belongs to the industry.** All products of an industry receive
its average input coefficients. MARIO allocates each industry's inputs across
its products in proportion to their shares of its output.

.. container:: mario-flow

   **Example:** if bread and cakes account for 80% and 20% of a bakery's output
   value, B assigns 80% of each input to bread and 20% to cakes. Activity-level
   emissions are split in the same proportions.

Use B when proportional allocation within each industry suits the analysis.
For a monetary SUT these are **value shares**, not physical quantities.
B does not introduce negative flows when source flows are nonnegative; this
property alone does not validate the allocation assumption.

Industry-by-industry IOT: C and D
---------------------------------

Both methods turn the **product rows of use and final demand** into industry
rows. The resulting ``Z`` records deliveries from producing industries to
using industries. Here, a sales structure means proportions sold to each
industry or final-demand category.

.. _sut-iot-method-c:

C · Fixed industry sales structure
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**The customer mix belongs to the industry.** An industry sells every product
in the same proportions to its customers. MARIO solves for industry sales
patterns consistent with the observed product deliveries and supply mixes.

.. container:: mario-flow

   **Example:** if a producer's inferred customer mix is 70% food manufacturers
   and 30% households, C applies that split to every product it supplies.

Use C when a common customer mix across an industry's products is defensible.
Like A, it requires a supply-matrix solve and **can produce negative entries**,
including in final demand.

.. _sut-iot-method-d:

D · Fixed product sales structure
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**The customer mix belongs to the product.** Every producer of a product serves
the same customer proportions. Equivalently, each buyer sources that product
from industries in proportion to their shares of its total supply.

.. container:: mario-flow

   **Example:** if two industries supply 80% and 20% of all bread, D assigns
   each buyer's bread purchases to those industries in an 80/20 split.

Use D when average supplier shares are appropriate for all buyers. The same
shares apply to every buyer of a given regional product. As with B,
nonnegative source flows give nonnegative transformed flows.

Matrix calculation
------------------

The method operates on native SUT flows. The SUT's current ``IT`` or ``PT``
setting does not choose the conversion: pass ``method`` explicitly. See
:ref:`SUT technology assumptions <concept-technology-assumptions>` for the
separate setting used when calculating directly on a SUT.

.. mario-details:: Equations for Z and Y

   MARIO uses ``S`` with **activity rows and commodity columns**, and ``U``
   with **commodity rows and activity columns**. ``Ya`` and ``Yc`` are the two
   final-demand blocks. See the :doc:`SUT block diagram
   </get_started/table_formats/sut>`.

   Let :math:`g=S\mathbf{1}+Y_a\mathbf{1}` and
   :math:`q=U\mathbf{1}+Y_c\mathbf{1}`. Define diagonal output matrices
   :math:`G=\operatorname{diag}(g)` and :math:`Q=\operatorname{diag}(q)`.
   On a balanced product account, :math:`q=S^{\mathsf T}\mathbf{1}`.

   **A — product recipes from a supply solve**

   .. math::

      Z=U S^{-\mathsf T}Q, \qquad Y=Y_c

   **B — industry inputs allocated over output**

   .. math::

      Z=U G^{-1}S, \qquad Y=Y_c+U G^{-1}Y_a

   **C — industry sales from a supply solve**

   .. math::

      Z=G S^{-\mathsf T}U, \qquad Y=G S^{-\mathsf T}Y_c

   **D — product purchases allocated over suppliers**

   .. math::

      Z=S Q^{-1}U, \qquad Y=Y_a+S Q^{-1}Y_c

   Here :math:`S^{-\mathsf T}=(S^{\mathsf T})^{-1}`. A/C use linear solves;
   MARIO does not construct a dense inverse. For divisions by output, a fully
   inactive node is allowed, but zero output with nonzero flows or accounts
   raises an error. These operations do not balance the source or harmonize
   incompatible units.

.. mario-details:: Extensions, factors and direct final-demand accounts

   The conversion rebuilds ``E``, ``V``, ``EY`` and ``VY`` alongside ``Z`` and
   ``Y``. For A/B, activity accounts are allocated to products and existing
   commodity accounts are added. For C/D, activity accounts stay on activities;
   commodity accounts are allocated over intermediate and final uses.

   With B, nonzero ``Ya`` also receives its share of activity inputs and
   accounts. With C/D, accounts attached to commodities consumed directly by
   final users contribute to ``EY`` or ``VY``. Existing direct final-demand
   accounts are retained. Inspect productive and direct accounts together
   when comparing totals.

Inspect the result
------------------

.. code-block:: python

   iot.get_index("Sector")
   iot.units["Sector"]
   iot.Y

**Only the baseline is converted; other scenarios are absent from the IOT.**
Its public baseline name is retained. With the default ``inplace=True``, the
original object is replaced and the call returns ``None``. Use
``inplace=False`` when comparing methods.

A/B inherit the commodity labels and units; C/D inherit the activity labels
and units. Review negative flows and account totals before comparing footprints.
For hybrid SUTs, check that the output sums and allocations are meaningful in
the source units; conversion does not provide an allocation rule for combining
incompatible physical units.

The method names and assumptions follow the `Eurostat Manual of Supply, Use
and Input-Output Tables (2008), Chapter 11
<https://ec.europa.eu/eurostat/cache/metadata/Annexes/naio_10_n_esms_an_3.pdf#page=310>`_.
For the complete call contract, see :doc:`db.to_iot()
<../../api_document/mario.Database.to_iot>`.

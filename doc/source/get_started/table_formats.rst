Table formats
=============

MARIO handles both Input-Output Tables (IOTs) and Supply and Use Tables
(SUTs). They share many workflows, but they do not carry the same internal
structure.

.. mario-switch::
   :label: Table format
   :hint: Choose a format to see its structure.

   .. mario-switch-option:: concept-iots
      :badge: IOT
      :title: Input-Output Tables
      :text: One symmetric system: sectors buy from and sell to sectors.
      :blocks: Z Y / V VY / E EY

   .. mario-switch-option:: concept-suts concept-technology-assumptions
      :badge: SUT
      :title: Supply and Use Tables
      :text: Activities produce commodities, so supply and use are kept apart.
      :blocks: . U Yc / S . Ya / Vc Va VY / Ec Ea EY
      :chips: Technology assumptions

.. _concept-iots:

Input-Output Tables (IOTs)
--------------------------

IOTs, also known as symmetric input-output *tables*, represent a squared representation of a productive system.
The main native *flow* *matrices* are:

* ``Z`` for intersectoral flows
* ``Y`` for final demand
* ``V`` and ``VY`` for factors of production
* ``E`` and ``EY`` for satellite accounts

From these flow matrices MARIO can derive *coefficient* *matrices* such as ``z``,
``v`` and ``e`` (and viceversa), the total production vector ``X``, and demand-driven results
such as footprints (``f`` and ``F``), multipliers (``m`` and ``M``) and prices indices (``p``).

.. mario-scheme:: IOT native flow matrices and coefficient matrices
   :flows: Z Y / V VY / E EY
   :coefficients: z / v / e
   :col-sizes: 3 1
   :row-sizes: 3 0.8 0.8

   Native IOT flow matrices and the corresponding coefficient matrices. Matrices ``Y``, ``VY`` and ``EY`` are always expressed in flows.


.. _concept-suts:

Supply-Use Tables (SUTs)
------------------------

SUTs, unlike IOTs, distinguish between commodities and the activity supplying them. The
native flow *matrices* are split into activity-side and commodity-side blocks:

* ``U`` and ``S``
* ``Yc`` and ``Ya``
* ``Vc``, ``Va`` and ``VY``
* ``Ec``, ``Ea`` and ``EY``

While ``U`` and ``S`` are commonly known in input-output literature as Use and
Make or Supply *matrices*, MARIO uses the ``a`` and ``c`` suffixes to indicate
the activity-side and commodity-side parts of ``Y``, ``V`` and ``E``.

**Some of these matrices may be entirely null and therefore absent in some databases!**

.. mario-scheme:: SUT native flow matrices and coefficient matrices
   :flows: . U Yc / S . Ya / Vc Va VY / Ec Ea EY
   :coefficients: . u / s . / vc va / ec ea
   :col-sizes: 1.5 1.5 1
   :row-sizes: 1.5 1.5 0.8 0.8

   Native SUT flow matrices and the corresponding coefficient matrices. Matrices ``Yc``, ``Ya``, ``VY`` and ``EY`` are always expressed in flows.

.. important::

   MARIO can also generate unified views for SUTs such as ``Z``, ``Y``, ``V`` and
   ``E`` on top of the standard matrices. These are convenient for inspection and
   some exports, but they are not the most native representation of a SUT
   database. This feature is particularly useful for retrocompatibility with
   versions up to v0.3.5.

.. important::

   When computing a *matrix*,  MARIO will calculate all the dependencies automatically.


.. _concept-technology-assumptions:

Technology assumptions
----------------------

When dealing with SUTs, it is possible to adopt:

* ``Industry-based`` technology assumption, which implies commodities are produced by industrial activities with a fixed market share
* ``Product-based`` technology assumption, which implies industrial activities produced a fixed mix of products

When parsing a SUT, you can specify the assumption. For instance:

.. code-block:: python

   db = mario.parse_from_excel(
    path = 'path/to/sut.xlsx',
    table = 'SUT',
    tech_assumption='product-based'  # or "industry-based"
    )

At the API level, the short aliases ``IT`` and ``PT`` are also accepted.
``tech_assumption`` is stored as a property of the *database*.

.. code-block:: python

   db.tech_assumption


Mathematics
~~~~~~~~~~~

The technology assumption does not affect every *matrix*,
but mainly the make transaction coefficients matrix ``s``. Independently of the assumption,
this *matrix* will always be called ``s``, but calculated differently.

In MARIO notation, the two cases are:

* under ``industry-based`` technology assumption:

  .. math::

     s = S \cdot \operatorname{diag}(X_c)^{-1}

  where ``Xc`` is the total demand of commodities vector. In this case, ``s`` is the
  market-share matrix.

* under ``product-based`` technology assumption:

  .. math::

     c = S^T \cdot \operatorname{diag}(X_a)^{-1}

  .. math::

     s = c^{-1}

  where ``Xa`` is the total production of activities vector. In this case, MARIO first builds
  the product-mix matrix ``c`` and then derives ``s`` as its inverse.


Switching assumption
~~~~~~~~~~~~~~~~~~~~

The technology assumption can be changed after parsing. When this
happens, MARIO resets all *tables* in all *scenarios* to flow *mode* first and then rebuilds the
affected coefficient-side structure under the new assumption,
avoiding mixing coefficients computed under different structural rules.

.. code-block:: python

   db.change_tech_assumption('PT') # or 'IT'



Caveats
~~~~~~~

Product-based technology assumption requires a squared SUT
(i.e. same number of commodities and activities).
If a user requests ``PT`` on a non-square SUT, MARIO does not fail the
import, but will warn the user it's falling back to ``IT`` instead.


Why this matters
----------------

In principle, many operations are common to both *table* formats. One can even
apply the same mathematics of IOTs to SUTs in a formal sense: see `Lenzen and
Rueda-Cantuche 2012 <https://www.idescat.cat/sort/sort362/36.2.2.lenzen-cantuche.pdf>`_.
In practice, however, efficient SUT formulas depend on the underlying supply
and use structure. Parsing, calculations and table transformations therefore
need to know whether a database is IOT or SUT.

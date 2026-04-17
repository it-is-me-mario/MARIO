Technology assumptions
======================

When dealing with SUTs, it is possible to adopt:

* ``Industry-based`` technology assumption, which implies commodities are produced by industrial activities with a fixed market share. 
* ``Product-based`` technology assumption, which implies industrial activities produced a fixed mix of products .

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
-----------

The assumption does not affect every *matrix*, 
but mainly the supply technical coefficients ``s``. Independently of the assumption, 
the *matrix* will always be called ``s``, but calculated differently.

In MARIO notation, the two cases are:

* under ``industry-based`` technology assumption:

  .. math::

     s = S \cdot \operatorname{diag}(X_c)^{-1}

  where ``Xc`` is the commodity output vector. In this case, ``s`` is the
  market-share matrix.

* under ``product-based`` technology assumption:

  .. math::

     c = S^T \cdot \operatorname{diag}(X_a)^{-1}

  .. math::

     s = c^{-1}

  where ``Xa`` is the activity output vector. In this case, MARIO first builds
  the product-mix matrix ``c`` and then derives ``s`` as its inverse.


Switching assumption
--------------------

The technology assumption can be changed after parsing. When this
happens, MARIO resets all *tables* in all *scenarios* to flow *mode* first and then rebuilds the
affected coefficient-side structure under the new assumption, 
avoiding mixing coefficients computed under different structural rules.

.. code-block:: python

   db.change_tech_assumption('PT') # or 'IT'



Square-table requirement
------------------------

Product-based technology assumption requires a squared SUT (i.e. same number of commodities and activities).
If a user requests ``PT`` on a non-square SUT, MARIO does not fail the
import. It falls back to ``IT`` instead.


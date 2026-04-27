Calculate linkages
==================

This workflow collects the quickest ways to calculate backward and forward
linkages from a parsed *database*.

What linkages measure
---------------------

Linkages are summary indicators of how strongly each sector is connected to the
rest of the system.

MARIO returns four main indicators:

* ``Total Backward``: total upstream requirements activated by one sector,
  based on the Leontief inverse;
* ``Total Forward``: total downstream supply-side propagation from one sector,
  based on the Ghosh inverse;
* ``Direct Backward``: direct upstream requirements only;
* ``Direct Forward``: direct downstream propagation only.

For multi-regional databases, the default output also separates each indicator
into ``Local`` and ``Foreign`` components.

Typical use
-----------

Start from a parsed database. The examples below use the packaged MARIO test
table:

.. code-block:: python

   import mario

   db = mario.load_test("IOT")

Calculate the default linkages:

.. code-block:: python

   linkages = db.calc_linkages()
   linkages

Default options
---------------

The default call is equivalent to:

.. code-block:: python

   linkages = db.calc_linkages(
      normalized=True,
      cut_diag=True,
      multi_mode=True,
   )

``multi_mode=True`` keeps the multi-regional interpretation. The results are
split between:

* ``Local``: flows that stay inside the same region;
* ``Foreign``: flows connected to other regions.

Normalization
-------------

``normalized=True`` divides each linkage column by its average value. In a
normalized result:

* values above ``1`` are above the average linkage intensity;
* values below ``1`` are below the average linkage intensity;
* values around ``1`` are close to the average.

This is useful when you want to compare sectors by relative structural
importance instead of by raw coefficient magnitude.

For multi-regional results with ``multi_mode=True``, MARIO keeps the ``Local``
and ``Foreign`` split and does not normalize the columns. If you want a
normalized table, use ``multi_mode=False``:

.. code-block:: python

   normalized_linkages = db.calc_linkages(
      normalized=True,
      multi_mode=False,
   )

To inspect raw, non-normalized linkage sums:

.. code-block:: python

   raw_linkages = db.calc_linkages(
      normalized=False,
      multi_mode=False,
   )

The non-normalized result keeps the original magnitude of the calculated
linkage sums. It is useful when absolute scale matters, but it is usually less
convenient for ranking sectors across different indicators.

Diagonal terms
--------------

``cut_diag=True`` removes self-linkages before calculating the indicators. This
means a sector is not allowed to count its own direct self-requirement as part
of the linkage score.

This is the default because self-flows can dominate small examples and make
cross-sector dependencies harder to read.

To keep self-linkages:

.. code-block:: python

   linkages_with_self_flows = db.calc_linkages(cut_diag=False)

When to use it
--------------

This workflow is useful when you want to:

* inspect structural interdependencies across sectors or activities;
* compare linkage profiles across scenarios;
* support exploratory structural analysis before applying transformations.

Checks after calculation
------------------------

After computing linkages, it is usually worth checking:

* which scenario was used;
* whether normalization was applied;
* how diagonal terms were treated.

For example:

.. code-block:: python

   db.calc_linkages(scenario="baseline")
   db.calc_linkages(normalized=False, multi_mode=False)
   db.calc_linkages(cut_diag=False)

Notebook walkthrough
--------------------

Use the notebook below as the main linkages guide:

* :doc:`Calculate linkages walkthrough <../../notebooks/user_guide/inspection/calc_linkages>`

If you prefer to run it locally, you can also download the source notebook:

* :download:`Download the linkages notebook <../../notebooks/user_guide/inspection/calc_linkages.ipynb>`

.. toctree::
   :hidden:

   ../../notebooks/user_guide/inspection/calc_linkages

mario.CoreModel.search
======================

.. currentmodule:: mario

.. automethod:: CoreModel.search

Searching one set normally returns an ordered list. In the
:ref:`special case of regional classifications <regional-classifications>`,
the result is a dictionary whose keys are only the regions containing matches::

    db.search("Activity", "^A_ADVERT$")
    # {"IT": ["A_ADVERT"], "DE": ["A_ADVERT"], ...}

Explicitly request the ordered union of distinct matching labels, or limit
the search to one region::

    db.search("Activity", "^A_ADVERT$", flat=True)
    # ["A_ADVERT"]

    db.search("Activity", "^A_ADVERT$", region="IT")
    # ["A_ADVERT"]

``region`` and ``flat=True`` are mutually exclusive. A regional set with no
matches returns ``{}``; a list-shaped search with no matches returns ``[]``.
The default result shape depends on the classification before filtering, even
if the matching lists happen to be identical in every region.

Global searches keep their outer grouping by set and use the same result
shapes inside each group::

    db.search("^A_ADVERT$")
    # {"Activity": {"IT": ["A_ADVERT"], "DE": ["A_ADVERT"], ...}, ...}

    db.search("^A_ADVERT$", flat=True)
    # {"Activity": ["A_ADVERT"], ...}

Set aliases, regular expressions, case matching and existing positional
arguments retain their previous behavior. Searches read materialized index
views without computing matrices.

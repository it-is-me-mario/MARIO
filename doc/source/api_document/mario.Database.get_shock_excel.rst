mario.Database.get\_shock\_excel
================================

.. currentmodule:: mario

.. automethod:: Database.get_shock_excel

For regional classifications, Excel picklists show the distinct union of
observed codes and cluster names. The regional cluster definitions remain on
the database (or are supplied through ``clusters=``); the menus do not imply
that every code is valid in every region. Shock application validates and
expands the actual regional selections. Template generation checks sparse
blocks for nonzero entries without converting them to dense arrays.

mario.download\_exiobase3
=========================

.. currentmodule:: mario

.. autofunction:: download_exiobase3

EXIOBASE 3.11.2 and interrupted downloads
----------------------------------------

Select the release and system explicitly, for example::

    files = mario.download_exiobase3(
        path="data/exiobase",
        years=[2022],
        version="3.11.2",
        system="ixi",
    )

Use ``system="pxp"`` for product-by-product tables. A failed transfer keeps
its downloaded bytes in a ``.part`` file. Run the same call again with the
default ``overwrite=False`` to resume it. MARIO makes up to six attempts per
call and checks Zenodo's published size and checksum before extracting or
reusing the archive. ``overwrite=True`` starts a fresh download.

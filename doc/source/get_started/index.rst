Installation
============

1. Create and activate a clean Python environment.

   .. code-block:: bash

      conda create -n mario python=3.12
      conda activate mario

2. Install MARIO from PyPI.

   .. code-block:: bash

      pip install mariopy

   .. note::

      MARIO requires **Python 3.11, 3.12 or 3.13** (``>=3.11,<3.14``).
      Python 3.14 and later are **not supported**: MARIO pins ``numpy==2.1.1``,
      which supports Python only up to 3.13. Always specify a supported Python
      version when creating an environment, as in the example above.

Test the installation
---------------------

Run a quick sanity check after the installation in a new Python session:

.. code-block:: python

   import mario
   db = mario.load_test("IOT")
   print(db)

If this runs without errors, the installation is working and MARIO can load
the packaged test database.

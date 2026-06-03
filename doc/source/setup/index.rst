Setup
=====

What is MARIO
-------------

MARIO is a Python library for working with :ref:`Input-Output Tables (IOTs) <concept-iots>`
and :ref:`Supply and Use Tables (SUTs) <concept-suts>`.

It turns a parsed table into a database object that you can inspect, compute,
transform and export.

Installation
------------

1. Create and activate a clean Python environment.

   .. code-block:: bash

      conda create -n mario python=3.12
      conda activate mario

2. Install MARIO from PyPI.

   .. code-block:: bash

      pip install mariopy

Test the installation
~~~~~~~~~~~~~~~~~~~~~

Run a quick sanity check after the installation in a new Python session:

.. code-block:: python

   import mario
   db = mario.load_test("IOT")
   print(db)

If this runs without errors, the installation is working and MARIO can load
the packaged test database.

Advanced installation
~~~~~~~~~~~~~~~~~~~~~

Use this path if you want to work with a specific Git branch, an unreleased
commit, or a local editable checkout.

1. Create and activate a clean Python environment.

   .. code-block:: bash

      conda create -n mario python=3.12
      conda activate mario

2. Install from a specific Git branch.

   .. code-block:: bash

      pip install "git+https://github.com/it-is-me-mario/MARIO.git@main"

   Replace ``main`` with the branch name, tag, or commit you want to install.

3. Or clone the repository and install it locally.

   .. code-block:: bash

      git clone https://github.com/it-is-me-mario/MARIO.git
      cd MARIO
      git checkout main
      pip install -e .

   This is the most convenient option if you plan to inspect or modify the
   source code locally.

4. After the installation, run the same sanity check shown above.

   .. code-block:: python

      import mario
      db = mario.load_test("IOT")
      print(db)

.. note::

   The documentation is usually updated together with the ``main`` branch. If
   you intentionally install a different branch or commit, some features or
   examples in the docs may not match your local installation exactly.

Next steps
----------

Head over to :doc:`../concepts/index` to understand the cornerstone definitions and conventions, 
before moving to the :doc:`../user_guide/index` sections.
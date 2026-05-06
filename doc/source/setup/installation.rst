Installation
============

.. note::

   These instructions are temporary. This documentation follows the code in
   ``main``, but this version is not on PyPI yet. A PyPI publication is
   expected by June 2026.

   Until then, you can either:

   * follow the instructions to install ``v0.3.5``, `available here <https://mario-suite.readthedocs.io/en/stable/intro.html#recommended-installation-method>`_, or
   * use the current version documented here by installing MARIO locally from the GitHub repository, following the instructions below.

1. Create a clean Python environment.

   .. code-block:: bash

      conda create -n mario python=3.12
      conda activate mario

2. Download the source code from GitHub.

   Option A: clone the repository

   .. code-block:: bash

      git clone https://github.com/it-is-me-mario/MARIO.git
      cd directory/where/you/stored/the/MARIO/repository

   Option B: download the ZIP archive from GitHub, extract it locally, and
   move into the extracted ``MARIO`` folder.

3. Make sure you are using the current ``main`` branch.

   If you cloned the repository with Git:

   .. code-block:: bash

      git checkout main
      git pull

4. Install MARIO from the local source tree.

   .. code-block:: bash

      pip install .

5. Run a quick sanity check.

   .. code-block:: python

      import mario
      db = mario.load_test("IOT")  # or "SUT"
      print(db)

If this works, the local installation is ready and you are using the same
codebase that this documentation describes.

Once the new release is published on PyPI, these temporary instructions will be
replaced by the standard ``pip install mariopy`` workflow.

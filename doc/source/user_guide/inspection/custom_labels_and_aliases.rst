:page-type: Guide
:summary: Use familiar matrix names and set aliases in the current Python session.

Customize names and aliases
===========================

.. container:: mario-companion

   :download:`Download notebook <custom_labels_and_aliases.ipynb>`

Settings are shared by all databases in the process. Keep a copy to restore
when the custom naming is no longer needed.

.. container:: mario-recipe

   .. code-block:: python

      from copy import deepcopy
      import mario

      previous = mario.download_settings()
      custom = deepcopy(previous)
      custom["nomenclature"]["z"] = "A"
      custom["nomenclature"]["w"] = "L"
      mario.upload_settings(custom)

      db = mario.load_test("IOT")
      db.query("A")

   .. container:: mario-result

      **Result** · ``A`` resolves the technical coefficients normally called
      ``z``; ``L`` resolves the inverse normally called ``w``. Canonical names
      remain usable. Matrix values are unchanged.

.. mario-details:: Add a set alias

   .. code-block:: python

      custom["index_aliases"]["s"].append("ProductionSector")
      mario.upload_settings(custom)
      db.get_index("ProductionSector")

   Aliases change how you address a set. They do not rename individual sectors.
   Reserved or conflicting matrix names are rejected.

Restore the session
-------------------

.. code-block:: python

   mario.upload_settings(previous)

``mario.reset_settings()`` instead restores built-in session defaults.
For saving defaults across sessions see :doc:`../../reference/api_settings_methods`.

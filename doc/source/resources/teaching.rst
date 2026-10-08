Teaching
========

Course material and guided examples to learn MARIO, from the first concepts to
real databases and scenarios.


.. _courses:

Course materials
----------------

.. mario-cards::
   :columns: 1
   :links:

   .. mario-card:: `MARIO crash course <https://github.com/it-is-me-mario/Crash-course>`_
      :kicker: GitHub · it-is-me-mario/Crash-course
      :logo: /_static/images/logos/github.svg

      A hands-on course on input-output analysis with Python, in three Jupyter
      notebooks: the basics on the test tables, real databases with EXIOBASE, and
      new sectors and scenarios.

      .. note::

         The three lectures of the 2026 edition are available as video recordings
         in the `course-recordings-2026 release <https://github.com/it-is-me-mario/Crash-course/releases/tag/course-recordings-2026>`_.
         They are recordings of live, interactive sessions, not tutorials produced
         for online viewing: they include pauses, discussions with participants and
         some troubleshooting. They complement the notebooks of the course.


Past courses
~~~~~~~~~~~~

MARIO has been taught in the following courses and summer schools.

* **EMP-LAC 2025** — Energy Modelling Platform for Latin America and the
  Caribbean. Climate Compatible Growth (CCG), Buenos Aires, Argentina.
  `Programme <https://climatecompatiblegrowth.com/wp-content/uploads/Concept-Note-EMP-LAC-25.pdf>`__.
* **EMP-LAC 2024** — Energy Modelling Platform for Latin America and the
  Caribbean. Climate Compatible Growth (CCG), Niterói, Brazil.
  `Programme <https://climatecompatiblegrowth.com/wp-content/uploads/Concept-Flyer-for-Summer-School_20230824.pdf>`__.
* **ICTP Summer School 2023** — Joint Summer School on Modelling Tools for
  Sustainable Development. CCG and the Abdus Salam International Centre for
  Theoretical Physics (ICTP), Trieste, Italy. The MARIO track covered
  input-output-based life-cycle assessment.
  `Programme <https://indico.ictp.it/event/10186>`__.

For CCG's current framework for institution-led training events, see
`EMP-X <https://climatecompatiblegrowth.com/international-partnerships/capacity-building/emp-x/>`_.


Guided examples
---------------

.. mario-cards::
   :columns: 1
   :links:

   .. mario-card:: `MRIO disaggregation model <https://github.com/it-is-me-mario/MRIO-disaggregation-model>`_
      :kicker: GitHub · it-is-me-mario/MRIO-disaggregation-model
      :logo: /_static/images/logos/github.svg

      Split a sector out of a multi-regional table with ``add_sectors`` and CVXLab:
      cement carved out of an aggregated GTAP 12 table with two regions, EU27 and
      the rest of the world, from an Excel inventory. Developed within ENTICE.

.. raw:: html

   <script>
   if (["#nomenclature-and-formulas", "#notebooks"].includes(window.location.hash)) {
     window.location.replace("material.html" + window.location.hash);
   }
   </script>

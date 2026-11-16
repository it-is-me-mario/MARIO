:page-type: Research model
:summary: Link GCAM technology pathways with hybrid input-output footprints for European steel policy.

GCAM–MARIO steel scenarios
==========================

Debora Ghezzi, Lorenzo Rinaldi, Russell Horowitz, Dirk-Jan van de Ven, Georg Holtz, Alexander Jülich, Matteo Vincenzo Rocco (2026). `Linking Global Integrated Assessment and Hybrid Input–Output Models To Support Steel Decarbonization Policies in Europe <https://doi.org/10.1021/acs.est.5c15099>`__. *Environmental Science \& Technology*.

Link GCAM technology pathways with hybrid input-output footprints for European steel policy.

Model and scope
---------------

Couples integrated assessment scenarios with technology-specific supply-chain accounting to examine steel decarbonisation policies.

Baseline, CBAM and subsidy scenarios; steel and electricity pathways, GHG and energy footprints.

Database
--------

Uses an extended EXIOBASE Hybrid steel database. The paper cites the Green steel archive; the later coupling example explicitly pins version 1.3.0.

:doc:`Database lineage <databases>`

Available editions
------------------

Original study scripts
~~~~~~~~~~~~~~~~~~~~~~

Original database-building, GCAM preparation, shock and result-processing scripts.

`Code and instructions <https://github.com/SESAM-Polimi/ExioSteel/blob/151dcf6bcdeed5a3f76277ace5decf93c408066a/shocks_analysis.py>`__ · `Recorded revision 151dcf6b <https://github.com/SESAM-Polimi/ExioSteel/tree/151dcf6bcdeed5a3f76277ace5decf93c408066a>`__

* `Database archive cited by the paper <https://doi.org/10.5281/zenodo.10843374>`__
* `GCAM version cited by the paper <https://github.com/russellhz/gcam-core/tree/Study9_IAMCOMPACT>`__
* `Published inputs and results <https://doi.org/10.1021/acs.est.5c15099.s001>`__

The scripts require external files and local path configuration. Full paper reproduction and the exact archived database edition remain to be verified.

* `Study sources and reproduction scope <https://github.com/SESAM-Polimi/ExioSteel/blob/be43497a18302f7c2ad0df13a3cb6b6536355839/docs/research-workflow.md>`__

Executable coupling example
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Reads GCAM exports and applies electricity and steel mix changes to a teaching database or the extended EXIOBASE source.

`Code and instructions <https://github.com/SESAM-Polimi/ExioSteel/blob/be43497a18302f7c2ad0df13a3cb6b6536355839/notebooks/GCAM_to_MARIO.ipynb>`__ · `Recorded revision be43497a <https://github.com/SESAM-Polimi/ExioSteel/tree/be43497a18302f7c2ad0df13a3cb6b6536355839>`__

* `Green steel database · v1.3.0 <https://zenodo.org/records/16779787>`__

This development example preserves background demand and trade. It demonstrates the coupling mechanism and does not reproduce all study scenarios or figures.

* `Source-reported execution · 26 October 2026 <https://github.com/SESAM-Polimi/ExioSteel/blob/be43497a18302f7c2ad0df13a3cb6b6536355839/verification/full-model.json>`__

Related studies
---------------

* :doc:`EU steel decarbonisation <steel-transition-eu>`
* :doc:`Solar PV reshoring <pv-hlca>`

Source review: 2026-11-16. Models have not been rerun by the gallery. Execution evidence linked above belongs to the source maintainers.

:doc:`All models <index>`

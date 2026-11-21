ISTAT tutorial receiving model
==============================

``istat_tutorial_settings.xlsx`` is the unmodified receiving model from
``it-is-me-mario/Tutorials`` commit
``eed931bfb37b2a3694cc1ef660421f0fdd95e25c``:

``preparing-supply-use-data-for-cvxlab/cvxlab_model/model_settings.xlsx``

SHA-256: ``40aa3c9df67ebfd0e13917dd9a00419743cddfa9a80a6b5862dff3826895263f``.

The upstream Apache-2.0 license is retained alongside it. This workbook contains
sets, variables, filters and equations, without source observations. Tests use
small synthetic ISTAT workbooks and satellite snapshots with this real model;
they require CVXLab but no downloads or large national database fixtures.

Keep the symbolic problem intact when updating the fixture. A simplified
input-only model cannot detect compatibility failures with this tutorial.

.. MARIO documentation master file, created by
   sphinx-quickstart on Thu Oct 14 17:00:18 2021.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Terminology
=================================
In the lack of consistent terminology for IO systems in the
scientific community, MARIO uses its own customized variable names. MARIO follows
a thermodynamic way of nomencluture which:

* Uppercase letters represents Flows
* Lowercase lettters represents Coefficients

Following table represents the variables and their explanations in MARIO:

.. list-table:: MARIO Terminology
   :widths: 25 25 50
   :header-rows: 1

   * - variable name
     - also known as
     - extended name
   * - Z
     - T
     - Intersectoral transaction flows matrix 
   * -  z
     - A
     - Intersectoral transaction coefficients matrix
   * - w
     - L
     - Leontief coefficient matrix
   * - Y
     - F
     - Final demand matrix
   * - X
     - x, q, g
     - Production vector
   * - V
     - F
     - Factor of production transaction flows matrix
   * - v
     - f, B, S
     - Factor of production transaction coefficients matrix
   * - E
     - F, D_pba, terr
     - Satellite transaction flows matrix
   * - U
     - T
     - Use transaction flow matrix
   * - u
     - A
     - Use coefficients matrix
   * - S
     - V, M, T
     - Supply transaction flow matrix
   * - s
     - A
     - Supply coefficients matrix
   * - EY
     - S_Y, F_hh, F_y
     - Satellite transaction flows matrix for final use
   * - M
     - ...
     - Economic impact matrix
   * - m
     - M
     - Multipliers coefficient matrix
   * - F
     - D_cba, con
     - Footprint matrix
   * - e
     - f, B, S
     - Satellite transaction coefficients matrix
   * - f
     - M
     - Footprint coefficients matrix
   * - g
     - G
     - Gosh coefficients matrix
   * - b
     - B
     - Intersectoral transaction direct-output coefficients matrix
   * - p
     - ...
     - Price index coefficients vector



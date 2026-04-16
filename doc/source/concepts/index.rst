Concepts
========

This section explains the model behind MARIO rather than the exact sequence of
commands to run.

Use it when you already know how to parse or manipulate a database, but want to
understand why MARIO behaves the way it does.

The pages in this section answer questions such as:

* why IOT and SUT databases expose different native blocks;
* why the same system can be represented either as flows or as coefficients;
* why SUT databases sometimes expose split blocks and sometimes unified views;
* why large databases may switch from inverse-based formulas to linear solves.

.. toctree::
   :maxdepth: 1

   iot_vs_sut
   flows_vs_coefficients
   scenarios
   matrix_layouts
   sut_split_and_unified_blocks
   technology_assumptions
   compute_resolver
   large_database_computation
   file_formats

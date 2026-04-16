Large Database Computation
==========================

Large databases are not just a bigger version of small ones. Some standard IO
formulas become impractical once tables are large enough.

Why the classical path breaks down
----------------------------------

For large IOT systems, the classical demand-driven route often relies on an
explicit inverse such as ``w = (I - z)^-1``. This becomes problematic because:

* the inverse is typically dense even when the original matrix is sparse;
* memory cost grows very quickly with system size;
* materializing the inverse is often unnecessary if only a few right-hand sides
  are needed.

This is why the large-database story in MARIO is not just about speed. It is
mainly about avoiding the wrong objects altogether.

Solve-based paths
-----------------

For several demand-driven targets, MARIO can solve the underlying linear system
directly instead of building the full inverse first.

This matters especially for targets such as:

* ``X``;
* ``f`` and ``F``;
* ``m`` and ``M``;
* ``p``;
* their SUT counterparts such as ``Xc``, ``fa``, ``fc``, ``ma``, ``mc``,
  ``pa`` and ``pc``.

With ``compute_method="auto"``, MARIO uses heuristics to decide when the
solve-based path is preferable.

Sparse-aware helpers
--------------------

Large-database support is not only about ``solve`` versus ``inverse``. MARIO
also uses sparse-aware helper operations when blocks are sparse-backed.

Typical examples are:

* row sums on large sparse blocks;
* row and column scaling without dense diagonal matrices;
* matrix products routed through sparse backends when that is structurally
  useful.

These optimizations are important because many large-database workflows spend a
lot of time in apparently simple operations such as ``sum(axis=1)``.

What remains expensive
----------------------

Even with these improvements, large systems can still be heavy.

Typical bottlenecks are:

* ill-conditioned or singular systems;
* iterative solves that converge slowly;
* factorization-heavy direct sparse solves;
* workflows that still require dense outputs at the end.

So the right mental model is not "large databases are now cheap". It is:

* the compute engine is better at avoiding needless explosions;
* users still need to choose realistic workflows and runtime settings.

Practical guidance
------------------

For very large databases, the safest default is usually:

* ``compute_method="auto"``;
* ``linear_solver="scipy"``;
* ``linear_strategy="auto"``.

Then profile the specific target that matters. Some blocks become easy after
the recent sparse-aware improvements, while others still depend on the
conditioning and size of the system you are solving.

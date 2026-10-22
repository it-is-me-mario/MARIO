Advanced workflows
==================

Practical guidance for configuring calculations and combining MARIO features
in analyses of real databases.

.. mario-cards::
   :columns: 2
   :links:

   .. mario-card:: :doc:`Computation settings <compute_settings>`
      :kicker: Compute configuration
      :icon: advanced

      Choose inverse or solve, configure the numerical solver and handle
      singular systems.

   .. mario-card:: :doc:`Updating the electricity supply and trade mix <electricity_mix>`
      :kicker: db.update_supply_mix
      :icon: power

      Rewrite the electricity generation mix and the bilateral trade with recent
      statistics.

   .. mario-card:: :doc:`Greenhouse gas calculations <greenhouse_gas_calculations>`
      :kicker: db.calc_ghg
      :icon: cloud

      Compute greenhouse gas indicators across the supported database profiles.

   .. mario-card:: :doc:`Supply-chain analyses <supply_chain_analyses>`
      :kicker: db.calc_trades_content
      :icon: chain

      Study a supply chain on EXIOBASE, from structural indicators to bilateral
      trade and its content.

   .. mario-card:: :doc:`Structural path analysis <structural_path_analysis>`
      :kicker: db.calc_spa
      :icon: paths

      Find the main paths through which final demand reaches an impact.

.. toctree::
   :hidden:

   compute_settings
   electricity_mix
   greenhouse_gas_calculations
   supply_chain_analyses
   structural_path_analysis

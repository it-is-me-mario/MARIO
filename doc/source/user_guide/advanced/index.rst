Advanced workflows
==================

End-to-end analyses that combine several MARIO features on real databases such
as EXIOBASE.

.. mario-cards::
   :columns: 2
   :links:

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

   electricity_mix
   greenhouse_gas_calculations
   supply_chain_analyses
   structural_path_analysis

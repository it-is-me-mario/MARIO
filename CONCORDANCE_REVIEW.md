# Concordance review — NACE Rev. 2.1 and CPA 2.2

Review completed 2026-10-11. Reproduce with `snapshot_nxbase_scope.py`, `build_sectoral_scope.py`, then `audit_classification_scope.py`.

All primary and alternative routes were checked for typed dimensions, valid leaf endpoints, continuity, cycles, attributable sources and native identities. This is a classification lookup, not an allocation matrix.

| Dimension / database | Native categories | With fine links | Unverified / pending |
|---|---:|---:|---:|
| activity / EXIOBASE · Monetary | 163 | 161 | 2 |
| activity / EXIOBASE · Hybrid | 164 | 162 | 2 |
| activity / ADB | 35 | 35 | 0 |
| activity / CEDA | 400 | 391 | 9 |
| activity / FIGARO | 64 | 64 | 0 |
| activity / GLORIA | 120 | 120 | 0 |
| activity / GTAP | 65 | 64 | 1 |
| activity / OECD | 50 | 50 | 0 |
| activity / WIOD | 56 | 56 | 0 |
| commodity / EXIOBASE · Monetary | 200 | 193 | 7 |
| commodity / EXIOBASE · Hybrid · IOT | 164 | 157 | 7 |
| commodity / EXIOBASE · Hybrid · SUT | 200 | 193 | 7 |
| commodity / EMERGING · Monetary · IOT · 2.0/2.2 | 133 | 0 | 133 |
| commodity / EMERGING · Monetary · IOT · 1.0 | 134 | 0 | 134 |
| commodity / EMERGING · Monetary · IOT · E | 146 | 0 | 146 |
| commodity / FIGARO | 64 | 64 | 0 |
| commodity / GLORIA | 120 | 112 | 8 |
| commodity / WIOD | 56 | 56 | 0 |

## Corrections and limits

- A connected correspondence path is not proof of exact containment. Published binary links, revision joins and producer bridges retain qualified precision.
- Activity and commodity graphs are separate. Commodity routes never traverse an activity namespace. Explicit product-to-producer activity bridges remain typed and qualified.
- Workbook parents are retained as lineage context. Current reviewed membership overrides do not rewrite nxbase_sets.xlsx or materialise SQL.
- Raw milk includes cattle, sheep and goat farming; wastewater treatment is sewerage. EXIOBASE crops, metals, waste technologies and legacy source anomalies have explicit editorial reviews.
- Hybrid product coverage uses the published 200 SUT to 164 IOT product correspondence, including all seven monetary products without CPA 2002 links.
- CEDA and GLORIA product routes through EPA/BEA aggregates are qualified. Explicit producer-scope exclusion reviews remove incompatible candidates; this cannot prove every remaining fine product link.
- GTAP thermal electricity/heat co-production remains qualified. The historical technical note assigns no heat to wind, solar, hydro or nuclear; no licensed numerical data are exported.
- EMERGING has native product inventories but no verified fine CPA bridge. EORA has no verified current fine concordance. OECD and ADB IOT industry sets are activities, not inferred product sets.
- NACE 46.89 has no predecessor in the supplied NACE 2 revision table; an unverified cell is not absence. CPA 2002 codes 33.30.90, 34.10.25 and 34.10.43 are absent from the historical revision table.
- EXIOBASE fertiliser and six landfill products lack CPA 2002 publisher links. GTAP product definitions without CPC codes remain unverified. No fuzzy matching or economic allocation weights are used.
- Country lookups, including GTAP Power and the separate WIOD SUT activity vocabulary, are checked against the same current references and actual native profile labels.
- GTAP and Open CEDA are displayed only in Activities: their catalogued sector/industry vocabularies do not supply a separate native Commodity set. CPC and EPA product concordances remain documented intermediate sources; Open CEDA provides emission factors rather than a raw IOT.

## Full route checks

- reference_nodes: 6,871
- reference_leaves: 4,005
- edge_visits: 384,667
- routes: 74,887
- native_reference_links: 32,264
- native_categories: 2,334
- unique_used_steps: 35,995
- sources: 56
- country_unique_routes: 33,751
- country_entries: 33,751

## Source register

| ID | Source | URL | SHA-256 |
|---|---|---|---|
| P01 | CPA 2.2 · official structure and explanatory notes | https://showvoc.op.europa.eu/semanticturkey/it.uniroma2.art.semanticturkey/st-core-services/Download/getFile?ctx_project=ESTAT_Statistical_classification_of_products_by_activity%2C_2.2_%28CPA_2.2%29&fileName=CPA+Ver.+2.2+-+Structure+and+explanatory+notes_EN.tsv | a97027da3a158ed842e53e5f85c25b1e64b7d53696c7a8161ae31a495de27a02 |
| P02 | CPA 2.2 · latest multilingual headings | https://showvoc.op.europa.eu/semanticturkey/it.uniroma2.art.semanticturkey/st-core-services/Download/getFile?ctx_project=ESTAT_Statistical_classification_of_products_by_activity%2C_2.2_%28CPA_2.2%29&fileName=CPA2.2_Names_Multilingual.tsv | 41da641c531dd87b9b5d79f4a84a1e6f99705905a0deada1206da43f5f659840 |
| P03 | CPA 2.1 · official RDF classification | https://showvoc.op.europa.eu/semanticturkey/it.uniroma2.art.semanticturkey/st-core-services/Download/getFile?ctx_project=ESTAT_Statistical_classification_of_products_by_activity%2C_2.1_%28CPA_2.1%29&fileName=RDF_DATASET.zip | 594aac581a540392701b0076c62c4e59e5b4aa41d1ccef42446a0df43bd90846 |
| P04 | CPA 2008 · official RDF classification and CPA 2.1 correspondence | https://showvoc.op.europa.eu/semanticturkey/it.uniroma2.art.semanticturkey/st-core-services/Download/getFile?ctx_project=ESTAT_Statistical_classification_of_products_by_activity%2C_2008_%28CPA_2008%29&fileName=CPA_2008.zip | 991eb81afb3b257ed9e51f5cac89820860280da48162fe7b7a9a572f0cdae1a8 |
| P05 | CPA 2.1 → CPA 2.2 · official correspondence | https://showvoc.op.europa.eu/semanticturkey/it.uniroma2.art.semanticturkey/st-core-services/Download/getFile?ctx_project=ESTAT_Statistical_classification_of_products_by_activity%2C_2.1_%28CPA_2.1%29&fileName=CPA+Ver.+2.1+-+CPA+Ver.+2.2.tsv | 33be65f28782f221ce0fb77fa7281441bc4e3fd2ecc356ec1ff24c5cbfdee798 |
| P06 | CPA 2002 → CPA 2008 · official historical correspondence | https://www.insee.fr/fr/statistiques/fichier/2579545/table_CPA02-CPA08.pdf | 0f397593954e402d4c7e069686d5eabd9daf4a44b8635c2a681d24b5576e6801 |
| P07 | EXIOBASE products ↔ CPA 2002 | https://github.com/EXIOBASE/00-concordances-public/blob/355e4da3f065ae145c601e784faa24e3f1746b5e/concordances/international/cpa2002_exiobase3p.csv | 00bbc03ac813e4c5ca33a978569877123fff4dbd6499f688fd8bb3f052d69a23 |
| P08 | nxbase · actual native commodity identities | nxbase-products.json | 0af4b1509e8589ed11d682dad453c4f4d25ada6a523f21d4c7a1b816920153e2 |
| P09 | EPA · EXIOBASE to USEEIO commodity concordance | https://github.com/USEPA/USEEIO/blob/20bec26a49a0eaffe6cc4c1aca327b6e309f2bd7/import_emission_factors/concordances/exio_to_useeio2_commodity_concordance.csv | 5090ee137d1044e7e88c0ef2c958ffb59992faf614c165c22290f0d089ec041f |
| P10 | EPA · CEDA to USEEIO commodity concordance | https://github.com/USEPA/USEEIO/blob/20bec26a49a0eaffe6cc4c1aca327b6e309f2bd7/import_emission_factors/concordances/ceda_to_useeio_commodity_concordance.csv | 5a33c370505a475eebb98aaed4ebdc85bd028943d67794de363a3c0e3b8a3a92 |
| P11 | EPA · GLORIA to USEEIO commodity concordance | https://github.com/USEPA/USEEIO/blob/20bec26a49a0eaffe6cc4c1aca327b6e309f2bd7/import_emission_factors/concordances/GLORIA_to_useeio2_commodity_concordance.csv | 3ee5ed24b8b6995bde1fff1e89e69948d33eb2f62c6d2e1dd87e7b6680c4c071 |
| P12 | FIGARO · CPA 2.1 product definitions | https://ec.europa.eu/eurostat/cache/metadata/en/naio_10_fg_esms.htm | 6b87a3a90732f48e17b0bcd36d4a1805d2addbac44897fa04b047489116dea0c |
| P13 | WIOD 2016 · supply-use product classification | https://www.rug.nl/ggdc/html_publications/memorandum/gd162.pdf | d2137e66fd260cb08f8ce9d3e411f0f0772e8feffc93bdcc78f7c1798415266c |
| P14 | CPA 2.1 ↔ CPC 2.1 · official product correspondence | https://unstats.un.org/unsd/classifications/Econ/tables/CPC/CPCv21_CPA21/CPA_2_1-CPC_2_1_final_26_April_2021.xlsx | d6c19358750c1ffb16b6836086305b556b920bbbb0ff68aacb06540d55bbf95e |
| P15 | GTAP GSC3 · CPC 2.1 and ISIC Rev. 4 concordances | https://www.gtap.agecon.purdue.edu/databases/contribute/concordinfo.asp | a64b8054f8b581145d47e3d2877b5fe4dffad755f2d0e42306c5996374c34f3c |
| P16 | EXIOBASE · complete public product identities | https://github.com/EXIOBASE/00-concordances-public/blob/355e4da3f065ae145c601e784faa24e3f1746b5e/concordances/exiobase/exiobase3p_exiobase3i.csv | abed9987d12b3aa907323761d9610e607e370df609dfbedd7162c2054fd0989a |
| P17 | EXIOBASE Hybrid · product identities and 200 → 164 aggregation | https://zenodo.org/records/7244919/files/Classifications_v_3_3_18.xlsx?download=1 | 0b2571697a308877f5b6cff881e85598141bb4c324c61cac6e93192d0e046167 |
| P18 | EXIOBASE · monetary product codes and aliases | https://github.com/EXIOBASE/00-class/blob/main/class/exio3class.xlsx | 6a789314d8e984eee1352a0b87cdd5a5b2c618e6211e5a5582f7922afd99dbe2 |
| P19 | nxbase · qualified product-origin and crop reviews | product-production-reviews.json | 18e69666296524aa02567dbb2002b286b7fb8fe4518742bd110e11f9a7e8a1bf |
| S01 | EXIOBASE products and NACE Rev. 2 | https://github.com/EXIOBASE/00-concordances-public/blob/355e4da3f065ae145c601e784faa24e3f1746b5e/concordances/international/nace2_exiobase3p.csv | ca73ffbd6903ef0b551e8f96b61759c5d77ee5657aad852a91ea5192ce5bbd81 |
| S02 | EXIOBASE product and industry correspondence | https://github.com/EXIOBASE/00-concordances-public/blob/355e4da3f065ae145c601e784faa24e3f1746b5e/concordances/exiobase/exiobase3p_exiobase3i.csv | abed9987d12b3aa907323761d9610e607e370df609dfbedd7162c2054fd0989a |
| S04 | ADB 35-sector definitions | https://www.adb.org/sites/default/files/publication/720461/part3-gvcs.pdf | 64ea77edb581aa3026793d372b17a43a3f431516cb902fa6592a2dd4910e8f3f |
| S05 | ISIC Rev. 3.1 to ISIC Rev. 4 | https://unstats.un.org/unsd/classifications/Econ/tables/ISIC/ISIC31_ISIC4/ISIC31_ISIC4.txt | 5edbf40aa5e75dd778782896dc2054a76bcd252c2fbad9f704d00a883a3f66a5 |
| S06 | NACE Rev. 2 to ISIC Rev. 4 | https://unstats.un.org/unsd/classifications/Econ/tables/ISIC/NACE2_ISIC4/NACE2_ISIC4.txt | 1220d7f920783418b82d0da6d35cf90a31d69efae47e41835417f5a3bdd5ebfe |
| S07 | NACE Rev. 2.1 and NACE Rev. 2 | https://showvoc.op.europa.eu/semanticturkey/it.uniroma2.art.semanticturkey/st-core-services/Download/getFile?ctx_project=ESTAT_Statistical_Classification_of_Economic_Activities_in_the_European_Community_Rev._2.1._%28NACE_2.1%29&fileName=NACE_Rev.2.1_NACE_Rev.2_+CorrespondenceTable.tsv | 54f4377a40b97e84e29ac94e49d6c5be61457aa4e1ecf75b9beba23480da5348 |
| S08 | CEDA 2024 to USEEIO BEA schemas | https://pasteur.epa.gov/uploads/10.23719/1531906/documents/ceda_to_useeio_commodity_concordance.csv | 1cde160b36dfa2080db62e9b3a791807426e590758e89336dc9a2199ea8aff47 |
| S09 | BEA industry/commodity codes and NAICS 2017 | https://www.bea.gov/sites/default/files/2023-10/BEA-Industry-and-Commodity-Codes-and-NAICS-Concordance.xlsx | 6e25267ff60ccedc0808c14153b0cdeb566a7f5e9097536c70c2b9694ef5ff47 |
| S10 | NAICS US 2017 to ISIC Rev. 4 | https://unstats.un.org/unsd/classifications/Econ/tables/ISIC/NAICS2017US-ISIC4.zip | c8d4ba0537fbba4a30f93a056ee32a1571234d1312e6b2eae6bd58a2d973138b |
| S11 | nxbase · reviewed EXIOBASE electricity activity paths | nxbase-activity-refinements.json | 0af4b1509e8589ed11d682dad453c4f4d25ada6a523f21d4c7a1b816920153e2 |
| S14 | NACE Rev. 2.1 structure | https://showvoc.op.europa.eu/semanticturkey/it.uniroma2.art.semanticturkey/st-core-services/Download/getFile?ctx_project=ESTAT_Statistical_Classification_of_Economic_Activities_in_the_European_Community_Rev._2.1._%28NACE_2.1%29&fileName=NACE_Rev2.1_Heading_All_Languages.tsv | 89becf36186d7d3f07954e9f7b5a8fc4b12528eb24e51a0ae76eecd55ddb54fc |
| S15 | ISIC Rev. 3.1 structure | https://unstats.un.org/unsd/classifications/Econ/Download/In%20Text/ISIC_Rev_3_1_english_structure.txt | ac3e59375eca1756b85530078397a69a98bf3c5ffd642abd96e45e37de098c92 |
| S17 | Eurostat · NACE Rev. 2.1 explanatory notes | https://ec.europa.eu/eurostat/documents/3859598/21633320/KS-GQ-24-007-EN-N.pdf | 40c69a62305dff21442368fabd0af32b17ef03278b6828ab7bec4eb1497a7235 |
| S18 | GLORIA v060 · published ISIC section concordance | https://ielab.info/resources/gloria/supportingdocs | 2be13d43339e37c7f417a49d73daca8374de24110838e97f14f7300731c16206 |
| S19 | UN Statistics Division · ISIC Rev. 4 structure | https://unstats.un.org/unsd/classifications/Econ/Download/In%20Text/ISIC_Rev_4_english_structure.txt | 18b645efc5a0b001fda5852cfd0690eb579011651e405631e50cb2d271ee2cc6 |
| S20 | nxbase · GLORIA v060 activity review | activity_correspondences.json |  |
| S21 | OECD ICIO 2025 · published industry definitions | https://webfs-sti.oecd.org/files/STI-PIE/ICIO/2025/ICIO2025annex.pdf | 16809b1684d44cf7f1ac4e410a8bd08d8638dce80678ef1bb0b26e17242c9cb5 |
| S22 | nxbase · governed activity parents | nxbase-gloria-icio.json | 0af4b1509e8589ed11d682dad453c4f4d25ada6a523f21d4c7a1b816920153e2 |
| S23 | EXIOBASE Hybrid 3.3.18 activity classifications | https://zenodo.org/records/7244919/files/Classifications_v_3_3_18.xlsx?download=1 | 0b2571697a308877f5b6cff881e85598141bb4c324c61cac6e93192d0e046167 |
| S24 | nxbase · EXIOBASE Hybrid activity parent chains | nxbase-exiobase-hybrid.json | 0af4b1509e8589ed11d682dad453c4f4d25ada6a523f21d4c7a1b816920153e2 |
| S25 | EXIOBASE 3 monetary industry classifications | https://github.com/EXIOBASE/00-class/blob/main/class/exio3class.xlsx | 6a789314d8e984eee1352a0b87cdd5a5b2c618e6211e5a5582f7922afd99dbe2 |
| S26 | FIGARO · published 64-industry NACE Rev. 2 classification | https://ec.europa.eu/eurostat/cache/metadata/en/naio_10_fg_esms.htm |  |
| S27 | WIOD 2016 · published industry classification | https://www.rug.nl/ggdc/html_publications/memorandum/gd162.pdf#page=44 | d2137e66fd260cb08f8ce9d3e411f0f0772e8feffc93bdcc78f7c1798415266c |
| S29 | Eurostat · complete NACE Rev. 2 → Rev. 2.1 correspondence | https://showvoc.op.europa.eu/semanticturkey/it.uniroma2.art.semanticturkey/st-core-services/Download/getFile?ctx_project=ESTAT_Statistical_Classification_of_Economic_Activities_in_the_European_Community_Rev._2.1._%28NACE_2.1%29&fileName=NACE_Rev.2.1_NACE_Rev.2_+CorrespondenceTable.tsv | 54f4377a40b97e84e29ac94e49d6c5be61457aa4e1ecf75b9beba23480da5348 |
| S30 | nxbase · FIGARO and WIOD activity identities and parents | nxbase-figaro-wiod.json | 0af4b1509e8589ed11d682dad453c4f4d25ada6a523f21d4c7a1b816920153e2 |
| S31 | GTAP GSC3 · CPC 2.1 and ISIC Rev. 4 concordances | https://www.gtap.agecon.purdue.edu/databases/contribute/concordinfo.asp | a64b8054f8b581145d47e3d2877b5fe4dffad755f2d0e42306c5996374c34f3c |
| S32 | GTAP 12 · Power sector definitions | https://www.gtap.agecon.purdue.edu/databases/Utilities/v12.aspx |  |
| S33 | CPC 2.1 → ISIC Rev. 4 · producing-activity correspondence | https://unstats.un.org/unsd/classifications/Econ/tables/CPC/CPCv21_ISIC4/cpc21-isic4.txt | 0272188c086fb5d8efa3923749cc7b5a1bd5a12e7719843d26c2f2b38ea2f392 |
| S34 | NACE Rev. 2 ↔ ISIC Rev. 4 · full official correspondence | https://unstats.un.org/unsd/classifications/Econ/tables/ISIC/NACE2_ISIC4/NACE2_ISIC4.txt | 1220d7f920783418b82d0da6d35cf90a31d69efae47e41835417f5a3bdd5ebfe |
| S35 | nxbase · existing power activity containment paths | nxbase-gtap.json | 0af4b1509e8589ed11d682dad453c4f4d25ada6a523f21d4c7a1b816920153e2 |
| S36 | GTAP-Power · heat and co-generation scope, technical note | https://www.gtap.agecon.purdue.edu/resources/res_display.asp?RecordID=5938 | 648749e0d0e2596dceead0df7978f9cccff4cad975a0675ede0b42a3be4d742f |
| S37 | GTAP 12 · public regional definitions | https://www.gtap.agecon.purdue.edu/databases/regions.aspx?Version=12.211 | ad6c34f1c95a7136b5940e255fa9a51dc707e50278c7ba1b7ca16d34dda07060 |
| S38 | GTAP 12 Power 2023 · local MARIO native index verification | gtap-scope-metadata.json |  |
| S39 | nxbase · reviewed native activity identities | reviewed-activity-correspondences.json | 0af4b1509e8589ed11d682dad453c4f4d25ada6a523f21d4c7a1b816920153e2 |
| S40 | EXIOBASE · native industry definitions and NACE Rev. 1.1 | https://zenodo.org/records/23039074 | d23c6b0e899ff6c3d40092d7a085eebdbaac5f3db73df511c23ab2290a4222ef |
| S41 | NACE Rev. 1.1 → NACE Rev. 2 correspondence | https://www.ine.es/daco/daco42/clasificaciones/cnae09/nace11_nace2.pdf | 129d46f8f9e4e1f2a9deea0b84a45d051659f44f68dc37d8a5c2979c310f7902 |
| S42 | nxbase · reviewed current activity correspondence | reviewed-activity-correspondences.json |  |

## Unverified native categories

### activity / EXIOBASE · Monetary

- `i40.11.g` Production of electricity by biomass and waste: pending
- `i40.11.l` Production of electricity nec: pending

### activity / EXIOBASE · Hybrid

- `i40.11.g` Production of electricity by biomass and waste: pending
- `i40.11.l` Production of electricity nec: pending

### activity / CEDA

- `4200ID` Customs duties: No verified fine correspondence
- `531HSO` Owner-occupied housing: No verified fine correspondence
- `S00500` Federal general government (defense): No verified fine correspondence
- `S00600` Federal general government (nondefense): No verified fine correspondence
- `S00102` Other federal government enterprises: No verified fine correspondence
- `GSLGE` State and local government educational services: No verified fine correspondence
- `GSLGH` State and local government hospitals and health services: No verified fine correspondence
- `GSLGO` State and local government other services: No verified fine correspondence
- `S00203` Other state and local government enterprises: No verified fine correspondence

### activity / GTAP

- `dwe` Dwellings: No verified fine correspondence

### commodity / EXIOBASE · Monetary

- `p90.5.a` Food waste for treatment: landfill: No verified fine correspondence
- `p90.5.d` Inert/metal/hazardous waste for treatment: landfill: No verified fine correspondence
- `p24.b` N-fertiliser: No verified fine correspondence
- `p90.5.b` Paper for treatment: landfill: No verified fine correspondence
- `p90.5.c` Plastic waste for treatment: landfill: No verified fine correspondence
- `p90.5.e` Textiles waste for treatment: landfill: No verified fine correspondence
- `p90.5.f` Wood waste for treatment: landfill: No verified fine correspondence

### commodity / EXIOBASE · Hybrid · IOT

- `p24.b` N-fertiliser: No verified fine correspondence
- `p90.5.a` Food waste for treatment: landfill: No verified fine correspondence
- `p90.5.b` Paper for treatment: landfill: No verified fine correspondence
- `p90.5.c` Plastic waste for treatment: landfill: No verified fine correspondence
- `p90.5.d` Inert/metal/hazardous waste for treatment: landfill: No verified fine correspondence
- `p90.5.e` Textiles waste for treatment: landfill: No verified fine correspondence
- `p90.5.f` Wood waste for treatment: landfill: No verified fine correspondence

### commodity / EXIOBASE · Hybrid · SUT

- `p24.b` N-fertiliser: No verified fine correspondence
- `p90.5.a` Food waste for treatment: landfill: No verified fine correspondence
- `p90.5.b` Paper for treatment: landfill: No verified fine correspondence
- `p90.5.c` Plastic waste for treatment: landfill: No verified fine correspondence
- `p90.5.d` Inert/metal/hazardous waste for treatment: landfill: No verified fine correspondence
- `p90.5.e` Textiles waste for treatment: landfill: No verified fine correspondence
- `p90.5.f` Wood waste for treatment: landfill: No verified fine correspondence

### commodity / EMERGING · Monetary · IOT · 2.0/2.2

- `C.4EAAF41CC34B` live animals: No verified fine correspondence
- `C.0B8599BC36DA` meat and edible meat offal: No verified fine correspondence
- `C.910A8500E761` fish, crustaceans, molluscs, aquatic invertebrates ne: No verified fine correspondence
- `C.DE89A5E96927` dairy products, eggs, honey, edible animal product ne: No verified fine correspondence
- `C.9B70B21A29AC` products of animal origin, nes: No verified fine correspondence
- `C.A09DEC9ABE4F` live trees, plants, bulbs, roots, cut flowers etc: No verified fine correspondence
- `C.EB41CFC2EADF` edible vegetables and certain roots and tubers: No verified fine correspondence
- `C.CEBF64C31D70` edible fruit, nuts, peel of citrus fruit, melons: No verified fine correspondence
- `C.F838C4E5F9AD` coffee, tea, mate and spices: No verified fine correspondence
- `C.1BE7E29FBC18` cereals: No verified fine correspondence
- `C.F0E2809ADDA6` milling products, malt, starches, inulin, wheat glute: No verified fine correspondence
- `C.6E44D0496F81` oil seed, oleagic fruits, grain, seed, fruit, etc, ne: No verified fine correspondence
- `C.1CD13F82EB81` lac, gums, resins, vegetable saps and extracts nes: No verified fine correspondence
- `C.0433F1ED33D8` vegetable plaiting materials, vegetable products nes: No verified fine correspondence
- `C.4075ED65E8EC` animal,vegetable fats and oils, cleavage products, et: No verified fine correspondence
- `C.9A57276D53D7` meat, fish and seafood food preparations nes: No verified fine correspondence
- `C.89F46513E1A1` sugars and sugar confectionery: No verified fine correspondence
- `C.E086745EDF2B` cocoa and cocoa preparations: No verified fine correspondence
- `C.08CFC1CB1409` cereal, flour, starch, milk preparations and products: No verified fine correspondence
- `C.560A42904794` vegetable, fruit, nut, etc food preparations: No verified fine correspondence
- `C.571945CDC779` miscellaneous edible preparations: No verified fine correspondence
- `C.1CD8A830EF6F` beverages, spirits and vinegar: No verified fine correspondence
- `C.4E47F84BA199` residues, wastes of food industry, animal fodder: No verified fine correspondence
- `C.C0B086908B51` tobacco and manufactured tobacco substitutes: No verified fine correspondence
- `C.EC1E42FDE50C` salt, sulphur, earth, stone, plaster, lime and cement: No verified fine correspondence
- `C.607C2664925C` ores, slag and ash: No verified fine correspondence
- `C.1AD46172ED82` inorganic chemicals, precious metal compound, isotope: No verified fine correspondence
- `C.CFD746BAF638` organic chemicals: No verified fine correspondence
- `C.5C9536518D2A` pharmaceutical products: No verified fine correspondence
- `C.10EC9DC90CF7` fertilizers: No verified fine correspondence
- `C.B828E8B3595A` tanning, dyeing extracts, tannins, derivs,pigments et: No verified fine correspondence
- `C.8866EF4B541B` essential oils, perfumes, cosmetics, toileteries: No verified fine correspondence
- `C.444F6A9BDA16` soaps, lubricants, waxes, candles, modelling pastes: No verified fine correspondence
- `C.93F47FF85CFF` albuminoids, modified starches, glues, enzymes: No verified fine correspondence
- `C.EFC065B9E8E8` explosives, pyrotechnics, matches, pyrophorics, etc: No verified fine correspondence
- `C.A0E5C7716251` photographic or cinematographic goods: No verified fine correspondence
- `C.56C07CF41124` miscellaneous chemical products: No verified fine correspondence
- `C.C979615BAA71` plastics and articles thereof: No verified fine correspondence
- `C.CE7A7C60F7A0` rubber and articles thereof: No verified fine correspondence
- `C.B1E6E7F70263` raw hides and skins (other than furskins) and leather: No verified fine correspondence
- `C.515F2AE8E0E6` articles of leather, animal gut, harness, travel good: No verified fine correspondence
- `C.DA1F44BEA08A` furskins and artificial fur, manufactures thereof: No verified fine correspondence
- `C.7D3224D24C78` wood and articles of wood, wood charcoal: No verified fine correspondence
- `C.E02E97EA8FA6` cork and articles of cork: No verified fine correspondence
- `C.99DF0004C958` manufactures of plaiting material, basketwork, etc.: No verified fine correspondence
- `C.32EF6ABF831B` pulp of wood, fibrous cellulosic material, waste etc: No verified fine correspondence
- `C.8E63A195D00D` paper & paperboard, articles of pulp, paper and board: No verified fine correspondence
- `C.B3640858FC79` printed books, newspapers, pictures etc: No verified fine correspondence
- `C.5D951A4CDF49` silk: No verified fine correspondence
- `C.9A41696B0FEA` wool, animal hair, horsehair yarn and fabric thereof: No verified fine correspondence
- `C.6524D6D4E3C1` cotton: No verified fine correspondence
- `C.B2583E4DD916` vegetable textile fibres nes, paper yarn, woven fabri: No verified fine correspondence
- `C.926B968E6675` manmade filaments: No verified fine correspondence
- `C.F866D91E551D` manmade staple fibres: No verified fine correspondence
- `C.C0A8D577E461` wadding, felt, nonwovens, yarns, twine, cordage, etc: No verified fine correspondence
- `C.73BCADF77497` carpets and other textile floor coverings: No verified fine correspondence
- `C.69B4E48AEF32` special woven or tufted fabric, lace, tapestry etc: No verified fine correspondence
- `C.9CA89DAFD251` impregnated, coated or laminated textile fabric: No verified fine correspondence
- `C.A51EB3231A58` knitted or crocheted fabric: No verified fine correspondence
- `C.2B8AC52F2A7B` articles of apparel, accessories, knit or crochet: No verified fine correspondence
- `C.309BBEC7CBF8` articles of apparel, accessories, not knit or crochet: No verified fine correspondence
- `C.88C7F53B5B8E` other made textile articles, sets, worn clothing etc: No verified fine correspondence
- `C.CABEFD385FE3` footwear, gaiters and the like, parts thereof: No verified fine correspondence
- `C.375AA4ECC5D3` headgear and parts thereof: No verified fine correspondence
- `C.5D396BA921E9` umbrellas, walking-sticks, seat-sticks, whips, etc: No verified fine correspondence
- `C.343C5EA051EC` bird skin, feathers, artificial flowers, human hair: No verified fine correspondence
- `C.3621A0078094` stone, plaster, cement, asbestos, mica, etc articles: No verified fine correspondence
- `C.4FE928CC4D3B` ceramic products undata: No verified fine correspondence
- `C.9CF17185D6D4` glass and glassware: No verified fine correspondence
- `C.329D600EEC05` pearls, precious stones, metals, coins, etc: No verified fine correspondence
- `C.BA30125D0CFE` iron and steel: No verified fine correspondence
- `C.70BB87F5C963` articles of iron or steel: No verified fine correspondence
- `C.811ED7A38C95` copper and articles thereof: No verified fine correspondence
- `C.227AC9D26736` nickel and articles thereof: No verified fine correspondence
- `C.1A337B304A25` aluminium and articles thereof: No verified fine correspondence
- `C.9DA93EB91526` lead and articles thereof: No verified fine correspondence
- `C.B208E7640C77` zinc and articles thereof: No verified fine correspondence
- `C.BE311F6812B1` tin and articles thereof: No verified fine correspondence
- `C.C3529964DA16` other base metals, cermets, articles thereof: No verified fine correspondence
- `C.C7B28BDE61A2` tools, implements, cutlery, etc of base metal: No verified fine correspondence
- `C.4DCFF9BD1C56` miscellaneous articles of base metal: No verified fine correspondence
- `C.750434A6BAEF` nuclear reactors, boilers, machinery, etc: No verified fine correspondence
- `C.8811528E242A` electrical, electronic equipment: No verified fine correspondence
- `C.4475ED745105` railway, tramway locomotives, rolling stock, equipmen: No verified fine correspondence
- `C.7BBF283F7C41` vehicles other than railway, tramway: No verified fine correspondence
- `C.AD09A45C4E8C` aircraft, spacecraft, and parts thereof: No verified fine correspondence
- `C.53ED75801DD6` ships, boats and other floating structures: No verified fine correspondence
- `C.255DD480FD55` optical, photo, technical, medical, etc apparatus: No verified fine correspondence
- `C.451D6764A048` clocks and watches and parts thereof: No verified fine correspondence
- `C.84CF53C3397B` musical instruments, parts and accessories: No verified fine correspondence
- `C.60BD50AC1ABF` arms and ammunition, parts and accessories thereof: No verified fine correspondence
- `C.2C1F762E3AE5` furniture, lighting, signs, prefabricated buildings: No verified fine correspondence
- `C.732F01839B9F` toys, games, sports requisites: No verified fine correspondence
- `C.ED263E434516` miscellaneous manufactured articles: No verified fine correspondence
- `C.D1177BE34D5C` works of art, collectors pieces and antiques: No verified fine correspondence
- `C.F9E74190B225` commodities not specified according to kind: No verified fine correspondence
- `C.8A4310B45A10` electricity: No verified fine correspondence
- `C.72D561062B05` gas manufacture, distribution: No verified fine correspondence
- `C.4351EA1F1824` water collection, puriﬁcation, and distribution: No verified fine correspondence
- `C.DBAAADDF0404` coal: No verified fine correspondence
- `C.2280AED5E509` oil: No verified fine correspondence
- `C.D23113684F0E` gas: No verified fine correspondence
- `C.2B6AC848B288` petroleum, coal products: No verified fine correspondence
- `C.74E4F42E485B` manufacturing services on physical inputs owned by others: No verified fine correspondence
- `C.776923AC6BA8` maintenance and repair services n.i.e.: No verified fine correspondence
- `C.46D939BCBF55` sea transport: No verified fine correspondence
- `C.35807290AA5C` air transport: No verified fine correspondence
- `C.A31657155972` other modes of transport: No verified fine correspondence
- `C.2B4706496E2A` postal and courier services: No verified fine correspondence
- `C.CEBE9F862F7E` goods (travel): No verified fine correspondence
- `C.0EE247DF19E8` local transport services: No verified fine correspondence
- `C.3E77E0AA6E16` accommodation services: No verified fine correspondence
- `C.FCA724636CE6` food-serving services: No verified fine correspondence
- `C.031841DD844E` construction: No verified fine correspondence
- `C.E1A3AEB9C612` direct insurance: No verified fine correspondence
- `C.A76DCA3431B0` pension and standardized guaranteed services: No verified fine correspondence
- `C.9631B946BE77` financial services: No verified fine correspondence
- `C.F7F0557581F6` real estate: No verified fine correspondence
- `C.821CAA1FFF2B` charges for the use of intellectual property n.i.e.: No verified fine correspondence
- `C.02210B60FE74` telecommunications services: No verified fine correspondence
- `C.BF2329B0A26F` computer services: No verified fine correspondence
- `C.9A5690ACEA78` information services: No verified fine correspondence
- `C.EA9D75F85CFA` research and development services: No verified fine correspondence
- `C.2B1857DC3C72` professional and management consulting services: No verified fine correspondence
- `C.AE8ECF648D89` engineering: No verified fine correspondence
- `C.4E013A6D0F0D` waste treatment and de-pollution agricultural and mining services: No verified fine correspondence
- `C.087DB8382625` operating leasing services: No verified fine correspondence
- `C.113CDB2C5A2F` other business services n.i.e.: No verified fine correspondence
- `C.0433335988FE` audiovisual and related services: No verified fine correspondence
- `C.B66FB71F8CC6` health services: No verified fine correspondence
- `C.6A347FFD266A` education services: No verified fine correspondence
- `C.2AE1F8C60287` recreation & other services: No verified fine correspondence
- `C.19198FCB2C5F` government goods and services n.i.e.: No verified fine correspondence

### commodity / EMERGING · Monetary · IOT · 1.0

- `C.4EAAF41CC34B` live animals: No verified fine correspondence
- `C.0B8599BC36DA` meat and edible meat offal: No verified fine correspondence
- `C.910A8500E761` fish, crustaceans, molluscs, aquatic invertebrates ne: No verified fine correspondence
- `C.DE89A5E96927` dairy products, eggs, honey, edible animal product ne: No verified fine correspondence
- `C.9B70B21A29AC` products of animal origin, nes: No verified fine correspondence
- `C.A09DEC9ABE4F` live trees, plants, bulbs, roots, cut flowers etc: No verified fine correspondence
- `C.EB41CFC2EADF` edible vegetables and certain roots and tubers: No verified fine correspondence
- `C.CEBF64C31D70` edible fruit, nuts, peel of citrus fruit, melons: No verified fine correspondence
- `C.F838C4E5F9AD` coffee, tea, mate and spices: No verified fine correspondence
- `C.1BE7E29FBC18` cereals: No verified fine correspondence
- `C.F0E2809ADDA6` milling products, malt, starches, inulin, wheat glute: No verified fine correspondence
- `C.6E44D0496F81` oil seed, oleagic fruits, grain, seed, fruit, etc, ne: No verified fine correspondence
- `C.1CD13F82EB81` lac, gums, resins, vegetable saps and extracts nes: No verified fine correspondence
- `C.0433F1ED33D8` vegetable plaiting materials, vegetable products nes: No verified fine correspondence
- `C.4075ED65E8EC` animal,vegetable fats and oils, cleavage products, et: No verified fine correspondence
- `C.9A57276D53D7` meat, fish and seafood food preparations nes: No verified fine correspondence
- `C.89F46513E1A1` sugars and sugar confectionery: No verified fine correspondence
- `C.E086745EDF2B` cocoa and cocoa preparations: No verified fine correspondence
- `C.08CFC1CB1409` cereal, flour, starch, milk preparations and products: No verified fine correspondence
- `C.560A42904794` vegetable, fruit, nut, etc food preparations: No verified fine correspondence
- `C.571945CDC779` miscellaneous edible preparations: No verified fine correspondence
- `C.1CD8A830EF6F` beverages, spirits and vinegar: No verified fine correspondence
- `C.4E47F84BA199` residues, wastes of food industry, animal fodder: No verified fine correspondence
- `C.C0B086908B51` tobacco and manufactured tobacco substitutes: No verified fine correspondence
- `C.EC1E42FDE50C` salt, sulphur, earth, stone, plaster, lime and cement: No verified fine correspondence
- `C.607C2664925C` ores, slag and ash: No verified fine correspondence
- `C.77C4A2990CC2` mineral fuels, oils, distillation products, etc: No verified fine correspondence
- `C.1AD46172ED82` inorganic chemicals, precious metal compound, isotope: No verified fine correspondence
- `C.CFD746BAF638` organic chemicals: No verified fine correspondence
- `C.5C9536518D2A` pharmaceutical products: No verified fine correspondence
- `C.10EC9DC90CF7` fertilizers: No verified fine correspondence
- `C.B828E8B3595A` tanning, dyeing extracts, tannins, derivs,pigments et: No verified fine correspondence
- `C.8866EF4B541B` essential oils, perfumes, cosmetics, toileteries: No verified fine correspondence
- `C.444F6A9BDA16` soaps, lubricants, waxes, candles, modelling pastes: No verified fine correspondence
- `C.93F47FF85CFF` albuminoids, modified starches, glues, enzymes: No verified fine correspondence
- `C.EFC065B9E8E8` explosives, pyrotechnics, matches, pyrophorics, etc: No verified fine correspondence
- `C.A0E5C7716251` photographic or cinematographic goods: No verified fine correspondence
- `C.56C07CF41124` miscellaneous chemical products: No verified fine correspondence
- `C.C979615BAA71` plastics and articles thereof: No verified fine correspondence
- `C.CE7A7C60F7A0` rubber and articles thereof: No verified fine correspondence
- `C.B1E6E7F70263` raw hides and skins (other than furskins) and leather: No verified fine correspondence
- `C.515F2AE8E0E6` articles of leather, animal gut, harness, travel good: No verified fine correspondence
- `C.DA1F44BEA08A` furskins and artificial fur, manufactures thereof: No verified fine correspondence
- `C.7D3224D24C78` wood and articles of wood, wood charcoal: No verified fine correspondence
- `C.E02E97EA8FA6` cork and articles of cork: No verified fine correspondence
- `C.99DF0004C958` manufactures of plaiting material, basketwork, etc.: No verified fine correspondence
- `C.32EF6ABF831B` pulp of wood, fibrous cellulosic material, waste etc: No verified fine correspondence
- `C.8E63A195D00D` paper & paperboard, articles of pulp, paper and board: No verified fine correspondence
- `C.B3640858FC79` printed books, newspapers, pictures etc: No verified fine correspondence
- `C.5D951A4CDF49` silk: No verified fine correspondence
- `C.9A41696B0FEA` wool, animal hair, horsehair yarn and fabric thereof: No verified fine correspondence
- `C.6524D6D4E3C1` cotton: No verified fine correspondence
- `C.B2583E4DD916` vegetable textile fibres nes, paper yarn, woven fabri: No verified fine correspondence
- `C.926B968E6675` manmade filaments: No verified fine correspondence
- `C.F866D91E551D` manmade staple fibres: No verified fine correspondence
- `C.C0A8D577E461` wadding, felt, nonwovens, yarns, twine, cordage, etc: No verified fine correspondence
- `C.73BCADF77497` carpets and other textile floor coverings: No verified fine correspondence
- `C.69B4E48AEF32` special woven or tufted fabric, lace, tapestry etc: No verified fine correspondence
- `C.9CA89DAFD251` impregnated, coated or laminated textile fabric: No verified fine correspondence
- `C.A51EB3231A58` knitted or crocheted fabric: No verified fine correspondence
- `C.2B8AC52F2A7B` articles of apparel, accessories, knit or crochet: No verified fine correspondence
- `C.309BBEC7CBF8` articles of apparel, accessories, not knit or crochet: No verified fine correspondence
- `C.88C7F53B5B8E` other made textile articles, sets, worn clothing etc: No verified fine correspondence
- `C.CABEFD385FE3` footwear, gaiters and the like, parts thereof: No verified fine correspondence
- `C.375AA4ECC5D3` headgear and parts thereof: No verified fine correspondence
- `C.5D396BA921E9` umbrellas, walking-sticks, seat-sticks, whips, etc: No verified fine correspondence
- `C.343C5EA051EC` bird skin, feathers, artificial flowers, human hair: No verified fine correspondence
- `C.3621A0078094` stone, plaster, cement, asbestos, mica, etc articles: No verified fine correspondence
- `C.4FE928CC4D3B` ceramic products undata: No verified fine correspondence
- `C.9CF17185D6D4` glass and glassware: No verified fine correspondence
- `C.329D600EEC05` pearls, precious stones, metals, coins, etc: No verified fine correspondence
- `C.BA30125D0CFE` iron and steel: No verified fine correspondence
- `C.70BB87F5C963` articles of iron or steel: No verified fine correspondence
- `C.811ED7A38C95` copper and articles thereof: No verified fine correspondence
- `C.227AC9D26736` nickel and articles thereof: No verified fine correspondence
- `C.1A337B304A25` aluminium and articles thereof: No verified fine correspondence
- `C.9DA93EB91526` lead and articles thereof: No verified fine correspondence
- `C.B208E7640C77` zinc and articles thereof: No verified fine correspondence
- `C.BE311F6812B1` tin and articles thereof: No verified fine correspondence
- `C.C3529964DA16` other base metals, cermets, articles thereof: No verified fine correspondence
- `C.C7B28BDE61A2` tools, implements, cutlery, etc of base metal: No verified fine correspondence
- `C.4DCFF9BD1C56` miscellaneous articles of base metal: No verified fine correspondence
- `C.750434A6BAEF` nuclear reactors, boilers, machinery, etc: No verified fine correspondence
- `C.8811528E242A` electrical, electronic equipment: No verified fine correspondence
- `C.4475ED745105` railway, tramway locomotives, rolling stock, equipmen: No verified fine correspondence
- `C.7BBF283F7C41` vehicles other than railway, tramway: No verified fine correspondence
- `C.AD09A45C4E8C` aircraft, spacecraft, and parts thereof: No verified fine correspondence
- `C.53ED75801DD6` ships, boats and other floating structures: No verified fine correspondence
- `C.255DD480FD55` optical, photo, technical, medical, etc apparatus: No verified fine correspondence
- `C.451D6764A048` clocks and watches and parts thereof: No verified fine correspondence
- `C.84CF53C3397B` musical instruments, parts and accessories: No verified fine correspondence
- `C.60BD50AC1ABF` arms and ammunition, parts and accessories thereof: No verified fine correspondence
- `C.2C1F762E3AE5` furniture, lighting, signs, prefabricated buildings: No verified fine correspondence
- `C.732F01839B9F` toys, games, sports requisites: No verified fine correspondence
- `C.ED263E434516` miscellaneous manufactured articles: No verified fine correspondence
- `C.D1177BE34D5C` works of art, collectors pieces and antiques: No verified fine correspondence
- `C.F9E74190B225` commodities not specified according to kind: No verified fine correspondence
- `C.8A4310B45A10` electricity: No verified fine correspondence
- `C.72D561062B05` gas manufacture, distribution: No verified fine correspondence
- `C.4351EA1F1824` water collection, puriﬁcation, and distribution: No verified fine correspondence
- `C.DBAAADDF0404` coal: No verified fine correspondence
- `C.2280AED5E509` oil: No verified fine correspondence
- `C.D23113684F0E` gas: No verified fine correspondence
- `C.2B6AC848B288` petroleum, coal products: No verified fine correspondence
- `C.74E4F42E485B` manufacturing services on physical inputs owned by others: No verified fine correspondence
- `C.776923AC6BA8` maintenance and repair services n.i.e.: No verified fine correspondence
- `C.46D939BCBF55` sea transport: No verified fine correspondence
- `C.35807290AA5C` air transport: No verified fine correspondence
- `C.A31657155972` other modes of transport: No verified fine correspondence
- `C.2B4706496E2A` postal and courier services: No verified fine correspondence
- `C.CEBE9F862F7E` goods (travel): No verified fine correspondence
- `C.0EE247DF19E8` local transport services: No verified fine correspondence
- `C.3E77E0AA6E16` accommodation services: No verified fine correspondence
- `C.FCA724636CE6` food-serving services: No verified fine correspondence
- `C.031841DD844E` construction: No verified fine correspondence
- `C.E96A918E6E0C` direct insurance, reinsurance, auxiliary insurance services: No verified fine correspondence
- `C.A76DCA3431B0` pension and standardized guaranteed services: No verified fine correspondence
- `C.9631B946BE77` financial services: No verified fine correspondence
- `C.F7F0557581F6` real estate: No verified fine correspondence
- `C.821CAA1FFF2B` charges for the use of intellectual property n.i.e.: No verified fine correspondence
- `C.02210B60FE74` telecommunications services: No verified fine correspondence
- `C.BF2329B0A26F` computer services: No verified fine correspondence
- `C.9A5690ACEA78` information services: No verified fine correspondence
- `C.EA9D75F85CFA` research and development services: No verified fine correspondence
- `C.2B1857DC3C72` professional and management consulting services: No verified fine correspondence
- `C.AE8ECF648D89` engineering: No verified fine correspondence
- `C.4E013A6D0F0D` waste treatment and de-pollution agricultural and mining services: No verified fine correspondence
- `C.087DB8382625` operating leasing services: No verified fine correspondence
- `C.AD229BEE8ECC` trade-related services, other business services n.i.e.: No verified fine correspondence
- `C.0433335988FE` audiovisual and related services: No verified fine correspondence
- `C.DA42EDFD22FA` health services, education services: No verified fine correspondence
- `C.6A347FFD266A` education services: No verified fine correspondence
- `C.86539587C012` heritage and recreational services, other personal services: No verified fine correspondence
- `C.19198FCB2C5F` government goods and services n.i.e.: No verified fine correspondence

### commodity / EMERGING · Monetary · IOT · E

- `` Live animals: No verified fine correspondence
- `` Meat and edible meat offal: No verified fine correspondence
- `` Fish, crustaceans, molluscs, aquatic invertebrates ne: No verified fine correspondence
- `` Dairy products, eggs, honey, edible animal product ne: No verified fine correspondence
- `` Products of animal origin, nes: No verified fine correspondence
- `` Live trees, plants, bulbs, roots, cut flowers etc: No verified fine correspondence
- `` Edible vegetables and certain roots and tubers: No verified fine correspondence
- `` Edible fruit, nuts, peel of citrus fruit, melons: No verified fine correspondence
- `` Coffee, tea, mate and spices: No verified fine correspondence
- `` Cereals: No verified fine correspondence
- `` Milling products, malt, starches, inulin, wheat glute: No verified fine correspondence
- `` Oil seed, oleagic fruits, grain, seed, fruit, etc, ne: No verified fine correspondence
- `` Lac, gums, resins, vegetable saps and extracts nes: No verified fine correspondence
- `` Vegetable plaiting materials, vegetable products nes: No verified fine correspondence
- `` Animal,vegetable fats and oils, cleavage products, et: No verified fine correspondence
- `` Meat, fish and seafood food preparations nes: No verified fine correspondence
- `` Sugars and sugar confectionery: No verified fine correspondence
- `` Cocoa and cocoa preparations: No verified fine correspondence
- `` Cereal, flour, starch, milk preparations and products: No verified fine correspondence
- `` Vegetable, fruit, nut, etc food preparations: No verified fine correspondence
- `` Miscellaneous edible preparations: No verified fine correspondence
- `` Beverages, spirits and vinegar: No verified fine correspondence
- `` Residues, wastes of food industry, animal fodder: No verified fine correspondence
- `` Tobacco and manufactured tobacco substitutes: No verified fine correspondence
- `` Salt, sulphur, earth, stone, plaster, lime and cement: No verified fine correspondence
- `` Ores, slag and ash: No verified fine correspondence
- `` Inorganic chemicals, precious metal compound, isotope: No verified fine correspondence
- `` Organic chemicals: No verified fine correspondence
- `` Pharmaceutical products: No verified fine correspondence
- `` Fertilizers: No verified fine correspondence
- `` Tanning, dyeing extracts, tannins, derivs,pigments et: No verified fine correspondence
- `` Essential oils, perfumes, cosmetics, toileteries: No verified fine correspondence
- `` Soaps, lubricants, waxes, candles, modelling pastes: No verified fine correspondence
- `` Albuminoids, modified starches, glues, enzymes: No verified fine correspondence
- `` Explosives, pyrotechnics, matches, pyrophorics, etc: No verified fine correspondence
- `` Photographic or cinematographic goods: No verified fine correspondence
- `` Miscellaneous chemical products: No verified fine correspondence
- `` Plastics and articles thereof: No verified fine correspondence
- `` Rubber and articles thereof: No verified fine correspondence
- `` Raw hides and skins (other than furskins) and leather: No verified fine correspondence
- `` Articles of leather, animal gut, harness, travel good: No verified fine correspondence
- `` Furskins and artificial fur, manufactures thereof: No verified fine correspondence
- `` Wood and articles of wood, wood charcoal: No verified fine correspondence
- `` Cork and articles of cork: No verified fine correspondence
- `` Manufactures of plaiting material, basketwork, etc.: No verified fine correspondence
- `` Pulp of wood, fibrous cellulosic material, waste etc: No verified fine correspondence
- `` Paper & paperboard, articles of pulp, paper and board: No verified fine correspondence
- `` Printed books, newspapers, pictures etc: No verified fine correspondence
- `` Silk: No verified fine correspondence
- `` Wool, animal hair, horsehair yarn and fabric thereof: No verified fine correspondence
- `` Cotton: No verified fine correspondence
- `` Vegetable textile fibres nes, paper yarn, woven fabri: No verified fine correspondence
- `` manmade filaments: No verified fine correspondence
- `` manmade staple fibres: No verified fine correspondence
- `` Wadding, felt, nonwovens, yarns, twine, cordage, etc: No verified fine correspondence
- `` Carpets and other textile floor coverings: No verified fine correspondence
- `` Special woven or tufted fabric, lace, tapestry etc: No verified fine correspondence
- `` Impregnated, coated or laminated textile fabric: No verified fine correspondence
- `` Knitted or crocheted fabric: No verified fine correspondence
- `` Articles of apparel, accessories, knit or crochet: No verified fine correspondence
- `` Articles of apparel, accessories, not knit or crochet: No verified fine correspondence
- `` Other made textile articles, sets, worn clothing etc: No verified fine correspondence
- `` Footwear, gaiters and the like, parts thereof: No verified fine correspondence
- `` Headgear and parts thereof: No verified fine correspondence
- `` Umbrellas, walking-sticks, seat-sticks, whips, etc: No verified fine correspondence
- `` Bird skin, feathers, artificial flowers, human hair: No verified fine correspondence
- `` Stone, plaster, cement, asbestos, mica, etc articles: No verified fine correspondence
- `` Ceramic products Undata: No verified fine correspondence
- `` Glass and glassware: No verified fine correspondence
- `` Pearls, precious stones, metals, coins, etc: No verified fine correspondence
- `` Iron and steel: No verified fine correspondence
- `` Articles of iron or steel: No verified fine correspondence
- `` Copper and articles thereof: No verified fine correspondence
- `` Nickel and articles thereof: No verified fine correspondence
- `` Aluminium and articles thereof: No verified fine correspondence
- `` Lead and articles thereof: No verified fine correspondence
- `` Zinc and articles thereof: No verified fine correspondence
- `` Tin and articles thereof: No verified fine correspondence
- `` Other base metals, cermets, articles thereof: No verified fine correspondence
- `` Tools, implements, cutlery, etc of base metal: No verified fine correspondence
- `` Miscellaneous articles of base metal: No verified fine correspondence
- `` Nuclear reactors, boilers, machinery, etc: No verified fine correspondence
- `` Electrical, electronic equipment: No verified fine correspondence
- `` Railway, tramway locomotives, rolling stock, equipmen: No verified fine correspondence
- `` Vehicles other than railway, tramway: No verified fine correspondence
- `` Aircraft, spacecraft, and parts thereof: No verified fine correspondence
- `` Ships, boats and other floating structures: No verified fine correspondence
- `` Optical, photo, technical, medical, etc apparatus: No verified fine correspondence
- `` Clocks and watches and parts thereof: No verified fine correspondence
- `` Musical instruments, parts and accessories: No verified fine correspondence
- `` Arms and ammunition, parts and accessories thereof: No verified fine correspondence
- `` Furniture, lighting, signs, prefabricated buildings: No verified fine correspondence
- `` Toys, games, sports requisites: No verified fine correspondence
- `` Miscellaneous manufactured articles: No verified fine correspondence
- `` Works of art, collectors pieces and antiques: No verified fine correspondence
- `` Commodities not specified according to kind: No verified fine correspondence
- `` Production of electricity by coal: No verified fine correspondence
- `` Production of electricity by gas: No verified fine correspondence
- `` Production of electricity by nuclear: No verified fine correspondence
- `` Production of electricity by hydro: No verified fine correspondence
- `` Production of electricity by wind: No verified fine correspondence
- `` Production of electricity by petroleum and other oil derivatives: No verified fine correspondence
- `` Production of electricity by biomass and waste: No verified fine correspondence
- `` Production of electricity by solar photovoltaic: No verified fine correspondence
- `` Production of electricity by solar thermal: No verified fine correspondence
- `` Production of electricity by tide, wave, ocean: No verified fine correspondence
- `` Production of electricity by Geothermal: No verified fine correspondence
- `` Production of electricity nec: No verified fine correspondence
- `` Transmission of electricity: No verified fine correspondence
- `` Distribution and trade of electricity: No verified fine correspondence
- `` Gas manufacture, distribution: No verified fine correspondence
- `` Water collection, puriﬁcation, and distribution: No verified fine correspondence
- `` coal: No verified fine correspondence
- `` oil: No verified fine correspondence
- `` gas: No verified fine correspondence
- `` Petroleum, coal products: No verified fine correspondence
- `` Manufacturing services on physical inputs owned by others: No verified fine correspondence
- `` Maintenance and repair services n.i.e.: No verified fine correspondence
- `` Sea transport: No verified fine correspondence
- `` Air transport: No verified fine correspondence
- `` Other modes of transport: No verified fine correspondence
- `` Postal and courier services: No verified fine correspondence
- `` Goods (travel): No verified fine correspondence
- `` Local transport services: No verified fine correspondence
- `` Accommodation services: No verified fine correspondence
- `` Food-serving services: No verified fine correspondence
- `` Construction: No verified fine correspondence
- `` Direct insurance: No verified fine correspondence
- `` Pension and standardized guaranteed services: No verified fine correspondence
- `` Financial services: No verified fine correspondence
- `` real estate: No verified fine correspondence
- `` Charges for the use of intellectual property n.i.e.: No verified fine correspondence
- `` Telecommunications services: No verified fine correspondence
- `` Computer services: No verified fine correspondence
- `` Information services: No verified fine correspondence
- `` Research and development services: No verified fine correspondence
- `` Professional and management consulting services: No verified fine correspondence
- `` engineering: No verified fine correspondence
- `` Waste treatment and de-pollution agricultural and mining services: No verified fine correspondence
- `` Operating leasing services: No verified fine correspondence
- `` Other business services n.i.e.: No verified fine correspondence
- `` Audiovisual and related services: No verified fine correspondence
- `` Health services: No verified fine correspondence
- `` Education services: No verified fine correspondence
- `` recreation & other services: No verified fine correspondence
- `` Government goods and services n.i.e.: No verified fine correspondence

### commodity / GLORIA

- `25` Lignite and peat: No verified fine correspondence
- `29` Uranium ores: No verified fine correspondence
- `52` Animal oils and fats: No verified fine correspondence
- `62` Coke oven products: No verified fine correspondence
- `78` Basic aluminium: No verified fine correspondence
- `89` Repair and installation of machinery and equipment (service): No verified fine correspondence
- `94` Distribution of gaseous fuels through mains: No verified fine correspondence
- `96` Waste collection, treatment, and disposal: No verified fine correspondence

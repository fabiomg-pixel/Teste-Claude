# PubMed Search Query Templates for Xenobiotics-Immunometabolic Research

## Master Query Strategy

The search is organized in three tiers:
1. **Xenobiotic-specific immunometabolic effects**
2. **Biomonitoring/exposure data in contaminated populations**
3. **Geographic overlap with arboviral disease**

---

## Tier 1: Immunometabolic Effects by Compound Class

### Query 1A: PFAS and Immunometabolism
```
("PFAS" OR "PFOA" OR "PFOS" OR "perfluoroalkyl" OR "polyfluoroalkyl" OR "perfluorinated")
AND
("immunometabolism" OR "immunometabolic" OR "immune metabolism" OR
 "macrophage polarization" OR "M1/M2" OR "trained immunity" OR
 "glycolysis" AND "immune" OR "Warburg effect" AND "immune" OR
 "mTOR" AND "immune" OR "AMPK" AND "immune" OR
 "inflammasome" OR "NLRP3" OR "NF-kB" AND "metabolism" OR
 "cytokine" AND "metabolic" OR "immunosuppression" OR
 "antibody response" OR "vaccine response")
```

### Query 1B: Dioxins/PCBs and Immunometabolism
```
("dioxin" OR "TCDD" OR "PCB" OR "polychlorinated biphenyl" OR "AhR" OR "aryl hydrocarbon receptor")
AND
("immunometabolism" OR "immunometabolic" OR "immune metabolism" OR
 "T cell metabolism" OR "Th17" OR "Treg" OR "regulatory T cell" OR
 "macrophage" AND "metabolism" OR "dendritic cell" AND "metabolism" OR
 "cytokine" OR "interleukin" OR "TNF" OR "interferon")
```

### Query 1C: Heavy Metals and Immunometabolism
```
("arsenic" OR "lead" OR "cadmium" OR "mercury" OR "heavy metal")
AND
("immunometabolism" OR "immunometabolic" OR "immune function" OR
 "macrophage" OR "phagocytosis" OR "oxidative burst" OR
 "lymphocyte" OR "T cell" OR "B cell" OR "NK cell" OR
 "cytokine" OR "inflammation" OR "innate immunity")
```

### Query 1D: Pesticides and Immunometabolism
```
("pesticide" OR "organophosphate" OR "organochlorine" OR "DDT" OR "chlorpyrifos" OR
 "glyphosate" OR "atrazine" OR "paraquat" OR "herbicide" OR "insecticide")
AND
("immune" OR "immunotoxic" OR "immunomodulation" OR "immunosuppression" OR
 "macrophage" OR "lymphocyte" OR "cytokine" OR "inflammation" OR
 "metabolic" AND "immune")
```

### Query 1E: Plasticizers/Endocrine Disruptors and Immunometabolism
```
("BPA" OR "bisphenol" OR "phthalate" OR "DEHP" OR "endocrine disruptor" OR "xenoestrogen")
AND
("immune" OR "macrophage" OR "inflammation" OR "cytokine" OR
 "metabolic inflammation" OR "adipose" AND "immune" OR
 "obesity" AND "inflammation")
```

### Query 1F: Air Pollutants and Immunometabolism
```
("particulate matter" OR "PM2.5" OR "PM10" OR "air pollution" OR "PAH" OR "benzo[a]pyrene")
AND
("immune" OR "inflammation" OR "lung" AND "immunity" OR
 "systemic inflammation" OR "macrophage" OR "cytokine")
```

---

## Tier 2: Biomonitoring and Human Exposure Queries

### Query 2A: Biomonitoring in Contaminated Populations
```
("biomonitoring" OR "human biomonitoring" OR "body burden" OR "blood level" OR "serum concentration" OR "urinary")
AND
([INSERT COMPOUND NAME])
AND
("contaminated" OR "exposed population" OR "occupational" OR "environmental exposure" OR
 "hot spot" OR "industrial" OR "agricultural workers")
```

### Query 2B: Exposure-Response Relationships
```
([INSERT COMPOUND NAME])
AND
("dose-response" OR "exposure-response" OR "threshold" OR "LOAEL" OR "NOAEL" OR
 "benchmark dose" OR "effective concentration" OR "EC50" OR "IC50")
AND
("immune" OR "inflammation" OR "cytokine" OR "health effect")
```

### Query 2C: Regional Exposure Studies
```
([INSERT COMPOUND NAME])
AND
("Bangladesh" OR "India" OR "Vietnam" OR "Brazil" OR "Africa" OR "Southeast Asia" OR
 "Latin America" OR "developing country" OR "low-income" OR "middle-income")
AND
("exposure" OR "contamination" OR "pollution" OR "biomonitoring")
```

---

## Tier 3: Arboviral Disease Geographic Overlay

### Query 3A: Environmental Factors and Arboviral Disease
```
("dengue" OR "Zika" OR "chikungunya" OR "yellow fever" OR "arbovirus" OR "arboviral")
AND
("environmental" OR "pollution" OR "contamination" OR "pesticide" OR "heavy metal" OR
 "socioeconomic" OR "urbanization")
AND
("risk factor" OR "susceptibility" OR "severity" OR "incidence")
```

### Query 3B: Immune Modulation and Viral Susceptibility
```
("immunocompromised" OR "immunosuppressed" OR "immune deficiency" OR "immunomodulation")
AND
("viral infection" OR "virus" OR "dengue" OR "arbovirus")
AND
("environmental" OR "pollution" OR "chemical" OR "toxicant")
```

### Query 3C: Specific Compound + Arboviral Regions
```
([INSERT COMPOUND])
AND
("Brazil" OR "Thailand" OR "Indonesia" OR "India" OR "Vietnam" OR "Colombia" OR
 "Mexico" OR "Philippines" OR "Nigeria" OR "Bangladesh")
```

---

## Compound-Specific Full Queries

### Arsenic Complete Query
```
("arsenic" OR "arsenite" OR "arsenate" OR "inorganic arsenic")
AND
(
  ("immune" OR "immunotoxic" OR "macrophage" OR "inflammation" OR "cytokine" OR "lymphocyte")
  OR
  ("Bangladesh" OR "West Bengal" OR "Vietnam" OR "Taiwan" OR "groundwater contamination")
  OR
  ("biomonitoring" OR "blood arsenic" OR "urinary arsenic" OR "hair arsenic")
)
```

### DDT/Organochlorines Complete Query
```
("DDT" OR "DDE" OR "organochlorine" OR "lindane" OR "dichlorodiphenyltrichloroethane")
AND
(
  ("immune" OR "immunomodulation" OR "lymphocyte" OR "antibody")
  OR
  ("malaria control" OR "vector control" OR "Africa" OR "India" OR "indoor residual spraying")
  OR
  ("biomonitoring" OR "adipose" OR "serum level" OR "breast milk")
)
```

### Mercury Complete Query
```
("mercury" OR "methylmercury" OR "Hg")
AND
(
  ("immune" OR "autoimmune" OR "immunotoxicity" OR "cytokine")
  OR
  ("Amazon" OR "gold mining" OR "artisanal" OR "ASGM" OR "fish consumption")
  OR
  ("blood mercury" OR "hair mercury" OR "biomonitoring")
)
```

---

## Database-Specific Search Strategies

### Comparative Toxicogenomics Database (CTD)
1. Search by chemical → retrieve gene interactions
2. Filter for immune/inflammatory genes:
   - IL1B, IL6, TNF, IFNG, NFKB1, NLRP3, AKT1, MTOR, HIF1A
3. Export chemical-gene-disease associations

### ToxCast/Tox21 (EPA CompTox)
1. Search for compounds by name/CAS
2. Filter by assay endpoints:
   - NF-kB activation
   - Cytokine release
   - Cell viability (immune cell lines)
3. Compare active concentrations to human biomonitoring

### GEO/ArrayExpress
```
("PFAS" OR "arsenic" OR "dioxin") AND ("macrophage" OR "PBMC" OR "immune")
```
- Look for transcriptomic datasets of immune cell exposure

---

## Systematic Review Filters

Add to any query to find existing reviews:
```
AND ("systematic review"[pt] OR "meta-analysis"[pt] OR "review"[pt])
```

Add to find human studies only:
```
AND ("humans"[MeSH] OR "epidemiology" OR "cohort" OR "cross-sectional" OR "case-control")
```

Add for mechanistic studies:
```
AND ("in vitro" OR "cell culture" OR "animal model" OR "mechanism" OR "pathway")
```

---

## Expected Results and Filtering

### Estimated hits per compound class:
- PFAS + immune: ~2000 results
- Dioxin + immune: ~3000 results
- Arsenic + immune: ~1500 results
- Pesticides + immune: ~5000 results
- Heavy metals + immune: ~4000 results

### Recommended filtering steps:
1. Date filter: 2010-present (unless looking for legacy data)
2. Language: English (or include Portuguese/Spanish for Latin American data)
3. Article type: Original research, reviews
4. Sort by: Relevance, then date

### Key journals to monitor:
- Environmental Health Perspectives
- Toxicological Sciences
- Environment International
- Journal of Immunotoxicology
- Toxicology and Applied Pharmacology
- Chemosphere
- Science of the Total Environment

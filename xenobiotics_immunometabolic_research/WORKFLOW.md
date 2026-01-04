# Research Workflow: Xenobiotics-Immunometabolic-Arboviral Framework

## Quick Start

```bash
# Run prioritization scoring
python scripts/prioritization_scoring.py \
    --input data/xenobiotics_database.json \
    --output results/

# Run geographic hotspot analysis
python scripts/geographic_analysis.py
```

## Workflow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    LITERATURE MINING FRAMEWORK                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  PHASE 1: COMPOUND IDENTIFICATION                                       │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                 │
│  │   PubMed    │    │     CTD     │    │  ToxCast    │                 │
│  │  Searches   │───▶│  Database   │───▶│   Data      │                 │
│  │(see queries)│    │             │    │             │                 │
│  └─────────────┘    └─────────────┘    └─────────────┘                 │
│         │                  │                  │                         │
│         └──────────────────┴──────────────────┘                         │
│                            │                                            │
│                            ▼                                            │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │           xenobiotics_database.json                               │  │
│  │   - Compound properties                                           │  │
│  │   - Immunometabolic pathways                                      │  │
│  │   - Key references (PMIDs)                                        │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  PHASE 2: EXPOSURE DATA INTEGRATION                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                 │
│  │   NHANES    │    │   HBM4EU    │    │  Regional   │                 │
│  │             │    │             │    │  Studies    │                 │
│  └─────────────┘    └─────────────┘    └─────────────┘                 │
│         │                  │                  │                         │
│         └──────────────────┴──────────────────┘                         │
│                            │                                            │
│                            ▼                                            │
│                 Biomonitoring Data Added to Database                    │
│                 (general population + contaminated areas)               │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  PHASE 3: PRIORITIZATION                                                │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │               prioritization_scoring.py                           │  │
│  │                                                                   │  │
│  │   Criteria (weighted):                                            │  │
│  │   • Immunometabolic evidence (25%)                               │  │
│  │   • Exposure data quality (20%)                                  │  │
│  │   • Concentration relevance (20%)                                │  │
│  │   • Geographic overlap (20%)                                     │  │
│  │   • Intervention potential (15%)                                 │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                            │                                            │
│                            ▼                                            │
│                    Ranked Priority List                                 │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  PHASE 4: GEOGRAPHIC ANALYSIS                                           │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │               geographic_analysis.py                              │  │
│  │                                                                   │  │
│  │   • Arboviral endemic regions (WHO data)                         │  │
│  │   • Contamination hotspots (UNEP, national data)                 │  │
│  │   • Overlay analysis → Research hotspots                         │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                            │                                            │
│                            ▼                                            │
│                 Country-level Priority Maps                             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Output Files

After running the analysis:

```
results/
├── priority_scores.json      # Full scoring data
├── priority_scores.csv       # Spreadsheet-compatible
├── priority_report.md        # Human-readable report
└── geographic/
    ├── geographic_hotspots.json
    ├── geographic_report.md
    └── contaminant_disease_matrix.csv
```

## Key Findings (Initial Analysis)

### Top Priority Xenobiotics

| Rank | Compound | Score | Key Regions |
|------|----------|-------|-------------|
| 1 | **Arsenic** | 4.25 | Bangladesh, India, Vietnam, Taiwan |
| 2 | **DDT/DDE** | 4.10 | Sub-Saharan Africa, India, SE Asia |
| 3 | **Paraquat** | 4.01 | SE Asia, Central/South America |
| 4 | **Chlorpyrifos** | 3.61 | Global agricultural |
| 5 | **Mercury** | 3.61 | Amazon, SE Asia ASGM |

### Top Geographic Hotspots

| Rank | Country | Score | Key Overlap |
|------|---------|-------|-------------|
| 1 | **Brazil** | 4.50 | Mercury + Dengue/Zika |
| 2 | **Vietnam** | 4.50 | Dioxin legacy + Dengue |
| 3 | **India** | 4.50 | Arsenic/DDT + Dengue/Chikungunya |
| 4 | **Indonesia** | 4.20 | Mercury/Pesticides + Dengue |
| 5 | **Colombia** | 4.20 | Mercury/Pesticides + Dengue/Zika |

## Next Steps

1. **Literature extraction**: Use search queries to systematically extract data
2. **Database expansion**: Add new compounds as literature is reviewed
3. **Validation**: Cross-reference with CTD, ToxCast databases
4. **Collaboration**: Contact researchers in hotspot regions
5. **Mechanistic studies**: Design experiments based on priority list

## Updating the Framework

### Adding a new xenobiotic:
```json
{
  "id": "XEN016",
  "name": "New Compound",
  "class": "Compound class",
  "immunometabolic_effects": {
    "pathways": ["list", "of", "pathways"],
    "cell_types_affected": ["macrophages", "etc"],
    "effects": ["documented", "effects"],
    "key_references": ["PMID:12345678"]
  },
  "exposure_data": {...},
  "effective_concentrations": {...},
  "geographic_overlap": {...}
}
```

### Adding biomonitoring data:
Update `exposure_data` section with:
- `general_population_range_*`: median and p95 values
- `contaminated_area_range_*`: median and max reported
- `contamination_sites`: list of known locations

## Citations

When using this framework, cite:
- Comparative Toxicogenomics Database (CTD)
- EPA ToxCast/Tox21
- NHANES biomonitoring data
- WHO arboviral disease surveillance

## Contact

[Add research team contact information]

#!/usr/bin/env python3
"""
Geographic Analysis: Xenobiotics-Arboviral Endemic Region Overlap

This script analyzes the geographic intersection between:
1. Documented xenobiotic contamination sites
2. Arboviral disease endemic regions

Output includes:
- Country-level overlap matrices
- Priority hotspots for research
- Data for visualization
"""

import json
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass
import csv


# Arboviral disease data by country
ARBOVIRAL_DATA = {
    # Southeast Asia
    "Thailand": {"dengue": "endemic", "zika": "endemic", "chikungunya": "endemic", "JE": "endemic"},
    "Vietnam": {"dengue": "endemic", "zika": "endemic", "chikungunya": "endemic", "JE": "endemic"},
    "Indonesia": {"dengue": "endemic", "zika": "endemic", "chikungunya": "endemic", "JE": "endemic"},
    "Philippines": {"dengue": "endemic", "zika": "endemic", "chikungunya": "endemic", "JE": "endemic"},
    "Malaysia": {"dengue": "endemic", "zika": "endemic", "chikungunya": "endemic"},
    "Cambodia": {"dengue": "endemic", "zika": "epidemic", "chikungunya": "endemic", "JE": "endemic"},
    "Myanmar": {"dengue": "endemic", "chikungunya": "endemic", "JE": "endemic"},
    "Laos": {"dengue": "endemic", "chikungunya": "endemic", "JE": "endemic"},

    # South Asia
    "India": {"dengue": "endemic", "zika": "endemic", "chikungunya": "endemic", "JE": "endemic"},
    "Bangladesh": {"dengue": "endemic", "chikungunya": "endemic", "JE": "endemic"},
    "Sri Lanka": {"dengue": "endemic", "chikungunya": "endemic"},
    "Nepal": {"dengue": "epidemic", "JE": "endemic"},
    "Pakistan": {"dengue": "endemic", "chikungunya": "epidemic"},

    # Latin America - Tropical
    "Brazil": {"dengue": "endemic", "zika": "endemic", "chikungunya": "endemic", "yellow_fever": "endemic"},
    "Colombia": {"dengue": "endemic", "zika": "endemic", "chikungunya": "endemic", "yellow_fever": "endemic"},
    "Venezuela": {"dengue": "endemic", "zika": "endemic", "chikungunya": "endemic"},
    "Ecuador": {"dengue": "endemic", "zika": "endemic", "chikungunya": "endemic"},
    "Peru": {"dengue": "endemic", "zika": "epidemic", "yellow_fever": "endemic"},
    "Bolivia": {"dengue": "endemic", "zika": "endemic", "chikungunya": "endemic"},
    "Paraguay": {"dengue": "endemic", "zika": "endemic", "chikungunya": "endemic"},
    "Argentina": {"dengue": "epidemic", "zika": "epidemic", "chikungunya": "epidemic"},

    # Central America & Caribbean
    "Mexico": {"dengue": "endemic", "zika": "endemic", "chikungunya": "endemic"},
    "Guatemala": {"dengue": "endemic", "zika": "endemic", "chikungunya": "endemic"},
    "Honduras": {"dengue": "endemic", "zika": "endemic", "chikungunya": "endemic"},
    "Nicaragua": {"dengue": "endemic", "zika": "endemic", "chikungunya": "endemic"},
    "El Salvador": {"dengue": "endemic", "zika": "endemic", "chikungunya": "endemic"},
    "Costa Rica": {"dengue": "endemic", "zika": "endemic", "chikungunya": "endemic"},
    "Panama": {"dengue": "endemic", "zika": "endemic", "chikungunya": "endemic"},
    "Cuba": {"dengue": "epidemic"},
    "Dominican Republic": {"dengue": "endemic", "zika": "endemic", "chikungunya": "endemic"},
    "Puerto Rico": {"dengue": "endemic", "zika": "endemic", "chikungunya": "endemic"},
    "Jamaica": {"dengue": "endemic", "zika": "endemic", "chikungunya": "endemic"},
    "Haiti": {"dengue": "endemic", "zika": "endemic", "chikungunya": "endemic"},

    # Sub-Saharan Africa
    "Nigeria": {"dengue": "epidemic", "yellow_fever": "endemic", "chikungunya": "endemic"},
    "Kenya": {"dengue": "epidemic", "chikungunya": "endemic", "Rift_Valley_fever": "endemic"},
    "Tanzania": {"dengue": "epidemic", "chikungunya": "endemic"},
    "DRC": {"yellow_fever": "endemic", "chikungunya": "endemic"},
    "Ghana": {"dengue": "epidemic", "yellow_fever": "endemic"},
    "Senegal": {"dengue": "endemic", "yellow_fever": "endemic", "chikungunya": "endemic"},
    "Uganda": {"dengue": "epidemic", "yellow_fever": "endemic", "chikungunya": "endemic"},
    "Cameroon": {"dengue": "epidemic", "yellow_fever": "endemic", "chikungunya": "endemic"},
    "Burkina Faso": {"dengue": "epidemic", "yellow_fever": "endemic"},
    "Cote d'Ivoire": {"dengue": "epidemic", "yellow_fever": "endemic"},
    "Angola": {"yellow_fever": "endemic", "dengue": "epidemic"},
    "Sudan": {"dengue": "epidemic", "chikungunya": "endemic", "Rift_Valley_fever": "epidemic"},
    "Ethiopia": {"dengue": "epidemic", "chikungunya": "endemic"},
    "Somalia": {"dengue": "epidemic", "chikungunya": "endemic"},

    # Pacific
    "Fiji": {"dengue": "endemic", "zika": "endemic", "chikungunya": "endemic"},
    "French Polynesia": {"dengue": "endemic", "zika": "endemic", "chikungunya": "endemic"},
    "Samoa": {"dengue": "endemic", "zika": "endemic"},
    "Tonga": {"dengue": "endemic", "zika": "endemic"},

    # Taiwan (special case - arsenic studies)
    "Taiwan": {"dengue": "endemic", "JE": "endemic"},
}


# Known contamination by country (from literature and databases)
CONTAMINATION_DATA = {
    "Bangladesh": {
        "arsenic": {"severity": "severe", "type": "groundwater", "population_exposed": 35_000_000},
        "pesticides": {"severity": "moderate", "type": "agricultural"},
        "lead": {"severity": "moderate", "type": "industrial/batteries"}
    },
    "India": {
        "arsenic": {"severity": "severe", "type": "groundwater", "affected_states": ["West Bengal", "Bihar", "UP"]},
        "DDT": {"severity": "moderate", "type": "malaria control"},
        "pesticides": {"severity": "high", "type": "agricultural"},
        "heavy_metals": {"severity": "high", "type": "industrial"}
    },
    "Vietnam": {
        "dioxin": {"severity": "severe", "type": "legacy (Agent Orange)", "affected_areas": ["Da Nang", "Bien Hoa", "Phu Cat"]},
        "arsenic": {"severity": "moderate", "type": "groundwater", "affected_areas": ["Mekong Delta", "Red River Delta"]},
        "pesticides": {"severity": "high", "type": "agricultural"}
    },
    "Brazil": {
        "mercury": {"severity": "severe", "type": "gold mining", "affected_areas": ["Amazon", "Pantanal"]},
        "pesticides": {"severity": "very high", "type": "agricultural", "compounds": ["glyphosate", "atrazine", "paraquat"]},
        "lead": {"severity": "moderate", "type": "industrial", "affected_areas": ["Santo Amaro", "Cubatão"]}
    },
    "Thailand": {
        "pesticides": {"severity": "high", "type": "agricultural"},
        "cadmium": {"severity": "moderate", "type": "mining", "affected_areas": ["Mae Sot"]}
    },
    "Indonesia": {
        "mercury": {"severity": "high", "type": "gold mining (ASGM)"},
        "pesticides": {"severity": "high", "type": "agricultural"}
    },
    "Philippines": {
        "mercury": {"severity": "moderate", "type": "gold mining"},
        "lead": {"severity": "moderate", "type": "recycling"},
        "PFAS": {"severity": "low-moderate", "type": "military bases"}
    },
    "Ghana": {
        "lead": {"severity": "severe", "type": "e-waste", "affected_areas": ["Agbogbloshie"]},
        "mercury": {"severity": "high", "type": "gold mining"},
        "DDT": {"severity": "moderate", "type": "historical malaria control"}
    },
    "Nigeria": {
        "lead": {"severity": "severe", "type": "gold mining", "affected_areas": ["Zamfara"]},
        "DDT": {"severity": "moderate", "type": "malaria control"},
        "PAH": {"severity": "high", "type": "oil industry", "affected_areas": ["Niger Delta"]}
    },
    "Peru": {
        "lead": {"severity": "severe", "type": "mining/smelting", "affected_areas": ["La Oroya", "Cerro de Pasco"]},
        "mercury": {"severity": "high", "type": "gold mining", "affected_areas": ["Madre de Dios"]},
        "arsenic": {"severity": "moderate", "type": "mining"}
    },
    "Colombia": {
        "mercury": {"severity": "high", "type": "gold mining"},
        "pesticides": {"severity": "high", "type": "agricultural"}
    },
    "Mexico": {
        "arsenic": {"severity": "moderate", "type": "groundwater/mining"},
        "pesticides": {"severity": "high", "type": "agricultural"},
        "lead": {"severity": "moderate", "type": "industrial"}
    },
    "Argentina": {
        "arsenic": {"severity": "high", "type": "groundwater", "affected_areas": ["Chaco-Pampean plain"]},
        "pesticides": {"severity": "very high", "type": "agricultural", "compounds": ["glyphosate"]}
    },
    "Senegal": {
        "DDT": {"severity": "moderate", "type": "malaria control"},
        "pesticides": {"severity": "moderate", "type": "agricultural"}
    },
    "Kenya": {
        "DDT": {"severity": "low-moderate", "type": "historical malaria control"},
        "pesticides": {"severity": "moderate", "type": "agricultural/flower industry"}
    },
    "Tanzania": {
        "mercury": {"severity": "high", "type": "gold mining"},
        "DDT": {"severity": "moderate", "type": "malaria control"}
    },
    "Zambia": {
        "lead": {"severity": "severe", "type": "mining", "affected_areas": ["Kabwe"]}
    },
    "Taiwan": {
        "arsenic": {"severity": "moderate-historical", "type": "groundwater (now remediated)", "historical_data": True}
    },
    "Chile": {
        "arsenic": {"severity": "high", "type": "natural/mining", "affected_areas": ["Atacama", "Antofagasta"]}
    },
    "Honduras": {
        "pesticides": {"severity": "high", "type": "agricultural (banana/palm)"}
    },
    "Costa Rica": {
        "pesticides": {"severity": "high", "type": "agricultural (banana/pineapple)"}
    }
}


@dataclass
class HotspotScore:
    """Scoring for a geographic hotspot."""
    country: str
    arboviral_burden: float  # 0-5
    contamination_severity: float  # 0-5
    compound_count: int
    arboviral_diseases: list
    contaminants: list
    notes: str = ""

    @property
    def priority_score(self) -> float:
        return (self.arboviral_burden + self.contamination_severity) / 2


def calculate_arboviral_burden(country: str) -> tuple[float, list]:
    """Calculate arboviral disease burden score for a country."""
    data = ARBOVIRAL_DATA.get(country, {})
    if not data:
        return 0.0, []

    diseases = list(data.keys())
    endemic_count = sum(1 for status in data.values() if status == "endemic")
    epidemic_count = sum(1 for status in data.values() if status == "epidemic")

    # Score: endemic diseases worth more than epidemic potential
    score = endemic_count * 1.0 + epidemic_count * 0.5
    score = min(score, 5.0)

    return score, diseases


def calculate_contamination_severity(country: str) -> tuple[float, list]:
    """Calculate contamination severity score for a country."""
    data = CONTAMINATION_DATA.get(country, {})
    if not data:
        return 0.0, []

    severity_map = {
        "severe": 5.0,
        "very high": 4.5,
        "high": 4.0,
        "moderate-historical": 2.5,
        "moderate": 3.0,
        "low-moderate": 2.0,
        "low": 1.0
    }

    contaminants = list(data.keys())
    max_severity = 0.0

    for contaminant, info in data.items():
        sev = info.get("severity", "low")
        score = severity_map.get(sev, 1.0)
        max_severity = max(max_severity, score)

    # Bonus for multiple contaminants
    bonus = min(len(contaminants) * 0.2, 1.0)

    return min(max_severity + bonus, 5.0), contaminants


def analyze_hotspots() -> list[HotspotScore]:
    """Analyze all countries for hotspot potential."""
    hotspots = []

    # Get all unique countries from both datasets
    all_countries = set(ARBOVIRAL_DATA.keys()) | set(CONTAMINATION_DATA.keys())

    for country in all_countries:
        arb_score, diseases = calculate_arboviral_burden(country)
        cont_score, contaminants = calculate_contamination_severity(country)

        if arb_score > 0 and cont_score > 0:  # Only include if both present
            hotspot = HotspotScore(
                country=country,
                arboviral_burden=arb_score,
                contamination_severity=cont_score,
                compound_count=len(contaminants),
                arboviral_diseases=diseases,
                contaminants=contaminants
            )
            hotspots.append(hotspot)

    # Sort by priority score
    hotspots.sort(key=lambda x: x.priority_score, reverse=True)

    return hotspots


def generate_overlap_matrix(hotspots: list[HotspotScore], output_dir: Path) -> None:
    """Generate compound-disease overlap matrix."""

    # Build matrix: rows = contaminants, columns = diseases
    contaminant_disease_overlap = defaultdict(lambda: defaultdict(list))

    for hs in hotspots:
        for cont in hs.contaminants:
            for disease in hs.arboviral_diseases:
                contaminant_disease_overlap[cont][disease].append(hs.country)

    # Get all unique contaminants and diseases
    all_contaminants = sorted(set(c for hs in hotspots for c in hs.contaminants))
    all_diseases = sorted(set(d for hs in hotspots for d in hs.arboviral_diseases))

    # Write matrix to CSV
    with open(output_dir / 'contaminant_disease_matrix.csv', 'w', newline='') as f:
        writer = csv.writer(f)

        # Header
        writer.writerow(['Contaminant'] + all_diseases)

        # Data rows
        for cont in all_contaminants:
            row = [cont]
            for disease in all_diseases:
                countries = contaminant_disease_overlap[cont][disease]
                row.append(len(countries))
            writer.writerow(row)


def generate_report(hotspots: list[HotspotScore], output_dir: Path) -> None:
    """Generate comprehensive geographic analysis report."""

    output_dir.mkdir(parents=True, exist_ok=True)

    # JSON output
    json_data = {
        'analysis': 'Geographic overlap of xenobiotic contamination and arboviral disease',
        'hotspots': [
            {
                'country': hs.country,
                'priority_score': round(hs.priority_score, 2),
                'arboviral_burden': round(hs.arboviral_burden, 2),
                'contamination_severity': round(hs.contamination_severity, 2),
                'arboviral_diseases': hs.arboviral_diseases,
                'contaminants': hs.contaminants
            }
            for hs in hotspots
        ]
    }

    with open(output_dir / 'geographic_hotspots.json', 'w') as f:
        json.dump(json_data, f, indent=2)

    # Generate overlap matrix
    generate_overlap_matrix(hotspots, output_dir)

    # Markdown report
    with open(output_dir / 'geographic_report.md', 'w') as f:
        f.write("# Geographic Hotspot Analysis\n\n")
        f.write("## Xenobiotics-Arboviral Disease Overlap\n\n")

        f.write("### Tier 1: Critical Priority Hotspots (Score ≥ 4.0)\n\n")
        tier1 = [hs for hs in hotspots if hs.priority_score >= 4.0]
        for hs in tier1:
            f.write(f"#### {hs.country} (Priority Score: {hs.priority_score:.2f})\n\n")
            f.write(f"**Arboviral Burden:** {hs.arboviral_burden:.1f}/5\n")
            f.write(f"- Diseases: {', '.join(hs.arboviral_diseases)}\n\n")
            f.write(f"**Contamination Severity:** {hs.contamination_severity:.1f}/5\n")
            f.write(f"- Contaminants: {', '.join(hs.contaminants)}\n\n")

            # Add specific notes from CONTAMINATION_DATA
            if hs.country in CONTAMINATION_DATA:
                f.write("**Key Details:**\n")
                for cont, info in CONTAMINATION_DATA[hs.country].items():
                    areas = info.get('affected_areas', [])
                    if areas:
                        f.write(f"- {cont}: {info['type']} ({', '.join(areas)})\n")
                    else:
                        f.write(f"- {cont}: {info['type']}\n")
                f.write("\n")

        f.write("---\n\n")

        f.write("### Tier 2: High Priority Hotspots (Score 3.0-3.9)\n\n")
        tier2 = [hs for hs in hotspots if 3.0 <= hs.priority_score < 4.0]
        for hs in tier2:
            f.write(f"**{hs.country}** (Score: {hs.priority_score:.2f})\n")
            f.write(f"- Diseases: {', '.join(hs.arboviral_diseases)}\n")
            f.write(f"- Contaminants: {', '.join(hs.contaminants)}\n\n")

        f.write("### Tier 3: Moderate Priority Hotspots (Score < 3.0)\n\n")
        tier3 = [hs for hs in hotspots if hs.priority_score < 3.0]
        for hs in tier3:
            f.write(f"- {hs.country} ({hs.priority_score:.2f}): {', '.join(hs.contaminants)}\n")

        f.write("\n---\n\n")

        f.write("## Key Research Priorities by Compound\n\n")

        # Aggregate by compound
        compound_countries = defaultdict(list)
        for hs in hotspots:
            for cont in hs.contaminants:
                compound_countries[cont].append((hs.country, hs.priority_score))

        for compound in sorted(compound_countries.keys()):
            countries = sorted(compound_countries[compound], key=lambda x: x[1], reverse=True)
            f.write(f"### {compound.upper()}\n")
            f.write("Priority research locations:\n")
            for country, score in countries[:5]:
                f.write(f"- {country} (hotspot score: {score:.2f})\n")
            f.write("\n")


def main():
    """Run geographic analysis."""
    print("Analyzing geographic overlap of contamination and arboviral disease...\n")

    hotspots = analyze_hotspots()

    output_dir = Path('results/geographic')
    generate_report(hotspots, output_dir)

    # Print summary
    print("=== TOP RESEARCH HOTSPOTS ===\n")
    print(f"{'Rank':<5} {'Country':<20} {'Score':<8} {'Contaminants':<30} {'Diseases'}")
    print("-" * 90)

    for rank, hs in enumerate(hotspots[:15], 1):
        cont_str = ', '.join(hs.contaminants[:3])
        if len(hs.contaminants) > 3:
            cont_str += f" (+{len(hs.contaminants)-3})"
        disease_str = ', '.join(hs.arboviral_diseases[:3])
        print(f"{rank:<5} {hs.country:<20} {hs.priority_score:.2f}     {cont_str:<30} {disease_str}")

    print(f"\nFull results saved to {output_dir}/")


if __name__ == '__main__':
    main()

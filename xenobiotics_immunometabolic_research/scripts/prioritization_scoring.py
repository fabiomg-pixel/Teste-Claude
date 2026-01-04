#!/usr/bin/env python3
"""
Xenobiotics-Immunometabolic Research Prioritization Tool

This script implements a scoring system to prioritize xenobiotics based on:
1. Strength of immunometabolic evidence
2. Human exposure data availability
3. Concentration overlap (environmental vs bioactive)
4. Geographic overlap with arboviral endemic regions
5. Intervention potential

Usage:
    python prioritization_scoring.py --input data/xenobiotics_database.json --output results/
"""

import json
import argparse
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import csv


@dataclass
class PriorityScore:
    """Container for priority scoring components."""
    xenobiotic_id: str
    name: str

    # Individual scores (1-5 scale)
    immunometabolic_evidence: float = 0.0
    exposure_data_quality: float = 0.0
    concentration_relevance: float = 0.0
    geographic_overlap: float = 0.0
    intervention_potential: float = 0.0

    # Weights
    weight_immunometabolic: float = 0.25
    weight_exposure: float = 0.20
    weight_concentration: float = 0.20
    weight_geographic: float = 0.20
    weight_intervention: float = 0.15

    @property
    def total_score(self) -> float:
        """Calculate weighted total score."""
        return (
            self.immunometabolic_evidence * self.weight_immunometabolic +
            self.exposure_data_quality * self.weight_exposure +
            self.concentration_relevance * self.weight_concentration +
            self.geographic_overlap * self.weight_geographic +
            self.intervention_potential * self.weight_intervention
        )

    def to_dict(self) -> dict:
        return {
            'id': self.xenobiotic_id,
            'name': self.name,
            'immunometabolic_evidence': self.immunometabolic_evidence,
            'exposure_data_quality': self.exposure_data_quality,
            'concentration_relevance': self.concentration_relevance,
            'geographic_overlap': self.geographic_overlap,
            'intervention_potential': self.intervention_potential,
            'total_score': round(self.total_score, 2)
        }


def score_immunometabolic_evidence(xenobiotic: dict) -> float:
    """
    Score based on quality of immunometabolic mechanism data.

    Criteria:
    - Number of pathways identified
    - Number of cell types studied
    - Quality of references (PMIDs available)
    - Specificity of effects
    """
    score = 0.0
    effects = xenobiotic.get('immunometabolic_effects', {})

    # Pathways identified (max 2 points)
    pathways = effects.get('pathways', [])
    score += min(len(pathways) * 0.4, 2.0)

    # Cell types studied (max 1.5 points)
    cell_types = effects.get('cell_types_affected', [])
    score += min(len(cell_types) * 0.3, 1.5)

    # References available (max 1 point)
    refs = effects.get('key_references', [])
    score += min(len(refs) * 0.33, 1.0)

    # Effects documented (max 0.5 points)
    documented_effects = effects.get('effects', [])
    score += min(len(documented_effects) * 0.1, 0.5)

    return min(score, 5.0)


def score_exposure_data_quality(xenobiotic: dict) -> float:
    """
    Score based on availability and quality of human biomonitoring data.

    Criteria:
    - General population data available
    - Contaminated area data available
    - Number of contamination sites documented
    - Biomonitoring source quality
    """
    score = 0.0
    exposure = xenobiotic.get('exposure_data', {})

    # General population data (1 point)
    if exposure.get('general_population_range_ng_mL') or \
       exposure.get('general_population_range_ug_L') or \
       exposure.get('general_population_range_ug_dL') or \
       exposure.get('general_population_range_pg_g_lipid'):
        score += 1.0

    # Contaminated area data (1.5 points)
    if exposure.get('contaminated_area_range_ng_mL') or \
       exposure.get('contaminated_area_range_ug_L') or \
       exposure.get('contaminated_area_range_ug_dL') or \
       exposure.get('contaminated_area_range_pg_g_lipid'):
        score += 1.5

    # Contamination sites documented (max 1.5 points)
    sites = exposure.get('contamination_sites', [])
    score += min(len(sites) * 0.3, 1.5)

    # Biomonitoring source (max 1 point)
    source = exposure.get('biomonitoring_source', '')
    if 'NHANES' in source:
        score += 0.5
    if 'HBM4EU' in source or 'WHO' in source:
        score += 0.3
    if source:
        score += 0.2

    return min(score, 5.0)


def score_concentration_relevance(xenobiotic: dict) -> float:
    """
    Score based on overlap between environmental exposure and bioactive concentrations.

    This is critical: we want compounds where contaminated population levels
    approach or exceed levels shown to cause immunometabolic effects.
    """
    score = 0.0

    effective = xenobiotic.get('effective_concentrations', {})
    exposure = xenobiotic.get('exposure_data', {})

    # Check if explicitly marked as relevant
    if effective.get('relevant_to_human_exposure') == True:
        score += 2.0
    elif effective.get('relevant_to_human_exposure') == 'uncertain':
        score += 0.5

    # Has LOAEL/effective concentration data (1.5 points)
    has_effective_data = any([
        effective.get('in_vitro_immune_effects_ng_mL'),
        effective.get('in_vitro_immune_effects_uM'),
        effective.get('in_vitro_immune_effects_nM'),
        effective.get('in_vitro_immune_effects_pM'),
        effective.get('in_vitro_effects_mg_L')
    ])
    if has_effective_data:
        score += 1.5

    # Has contaminated area exposure data (1.5 points)
    has_exposure_data = any([
        exposure.get('contaminated_area_range_ng_mL'),
        exposure.get('contaminated_area_range_ug_L'),
        exposure.get('contaminated_area_range_ug_dL'),
        exposure.get('contaminated_area_range_pg_g_lipid')
    ])
    if has_exposure_data:
        score += 1.5

    return min(score, 5.0)


def score_geographic_overlap(xenobiotic: dict) -> float:
    """
    Score based on overlap with arboviral endemic regions.

    Higher scores for compounds with contamination in dengue/Zika/chikungunya hotspots.
    """
    score = 0.0

    geo = xenobiotic.get('geographic_overlap', {})
    regions = geo.get('arboviral_endemic_regions', [])
    notes = geo.get('notes', '').lower()

    # Count HIGH overlap mentions
    high_count = sum(1 for r in regions if 'HIGH' in r.upper())

    # Check notes for quality indicators
    if 'excellent' in notes or 'perfect' in notes or 'very high' in notes:
        score += 2.0
    elif 'high' in notes:
        score += 1.0

    # Score based on number of overlapping regions
    score += min(high_count * 0.75, 2.0)

    # Bonus for specific mentions
    if len(regions) > 0 and 'limited' not in str(regions[0]).lower():
        score += 1.0

    return min(score, 5.0)


def score_intervention_potential(xenobiotic: dict) -> float:
    """
    Score based on potential for intervention/regulation.

    Criteria:
    - Ongoing exposure (vs legacy only)
    - Regulatory frameworks exist
    - Feasibility of exposure reduction
    """
    score = 2.5  # Default middle score

    compound_class = xenobiotic.get('class', '').lower()
    exposure = xenobiotic.get('exposure_data', {})
    sites = exposure.get('contamination_sites', [])

    # Active use compounds score higher (can be regulated)
    active_use_classes = ['herbicide', 'pesticide', 'pfas', 'plasticizer', 'phthalate']
    if any(c in compound_class for c in active_use_classes):
        score += 1.0

    # Legacy contamination (harder to intervene)
    legacy_indicators = ['legacy', 'agent orange', 'historical']
    if any(ind in str(sites).lower() for ind in legacy_indicators):
        score -= 0.5

    # Occupational exposure (easier to target)
    if 'agricultural' in str(sites).lower() or 'workers' in str(sites).lower():
        score += 0.5

    # Water contamination (critical infrastructure)
    if 'groundwater' in str(sites).lower() or 'water' in str(sites).lower():
        score += 0.5

    return min(max(score, 1.0), 5.0)


def calculate_all_scores(xenobiotics: list) -> list[PriorityScore]:
    """Calculate priority scores for all xenobiotics."""
    scores = []

    for xeno in xenobiotics:
        ps = PriorityScore(
            xenobiotic_id=xeno.get('id', 'unknown'),
            name=xeno.get('name', 'Unknown compound')
        )

        ps.immunometabolic_evidence = score_immunometabolic_evidence(xeno)
        ps.exposure_data_quality = score_exposure_data_quality(xeno)
        ps.concentration_relevance = score_concentration_relevance(xeno)
        ps.geographic_overlap = score_geographic_overlap(xeno)
        ps.intervention_potential = score_intervention_potential(xeno)

        scores.append(ps)

    # Sort by total score descending
    scores.sort(key=lambda x: x.total_score, reverse=True)

    return scores


def generate_report(scores: list[PriorityScore], output_dir: Path) -> None:
    """Generate prioritization report."""

    # JSON output
    json_output = {
        'methodology': {
            'description': 'Weighted scoring of xenobiotics for immunometabolic-arboviral research',
            'weights': {
                'immunometabolic_evidence': 0.25,
                'exposure_data_quality': 0.20,
                'concentration_relevance': 0.20,
                'geographic_overlap': 0.20,
                'intervention_potential': 0.15
            },
            'scale': '1-5 for each criterion, weighted total'
        },
        'results': [s.to_dict() for s in scores]
    }

    with open(output_dir / 'priority_scores.json', 'w') as f:
        json.dump(json_output, f, indent=2)

    # CSV output
    with open(output_dir / 'priority_scores.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'rank', 'id', 'name', 'total_score',
            'immunometabolic_evidence', 'exposure_data_quality',
            'concentration_relevance', 'geographic_overlap', 'intervention_potential'
        ])
        writer.writeheader()
        for rank, score in enumerate(scores, 1):
            row = score.to_dict()
            row['rank'] = rank
            writer.writerow(row)

    # Markdown report
    with open(output_dir / 'priority_report.md', 'w') as f:
        f.write("# Xenobiotics Prioritization Report\n\n")
        f.write("## Top Priority Compounds for Immunometabolic-Arboviral Research\n\n")

        f.write("### Tier 1: Highest Priority (Score ≥ 4.0)\n\n")
        tier1 = [s for s in scores if s.total_score >= 4.0]
        for s in tier1:
            f.write(f"**{s.name}** (Score: {s.total_score:.2f})\n")
            f.write(f"- Immunometabolic evidence: {s.immunometabolic_evidence:.1f}/5\n")
            f.write(f"- Exposure data: {s.exposure_data_quality:.1f}/5\n")
            f.write(f"- Concentration relevance: {s.concentration_relevance:.1f}/5\n")
            f.write(f"- Geographic overlap: {s.geographic_overlap:.1f}/5\n")
            f.write(f"- Intervention potential: {s.intervention_potential:.1f}/5\n\n")

        f.write("### Tier 2: High Priority (Score 3.0-3.9)\n\n")
        tier2 = [s for s in scores if 3.0 <= s.total_score < 4.0]
        for s in tier2:
            f.write(f"**{s.name}** (Score: {s.total_score:.2f})\n\n")

        f.write("### Tier 3: Moderate Priority (Score < 3.0)\n\n")
        tier3 = [s for s in scores if s.total_score < 3.0]
        for s in tier3:
            f.write(f"- {s.name} (Score: {s.total_score:.2f})\n")

        f.write("\n---\n")
        f.write("\n## Scoring Methodology\n\n")
        f.write("| Criterion | Weight | Description |\n")
        f.write("|-----------|--------|-------------|\n")
        f.write("| Immunometabolic evidence | 25% | Quality of mechanistic data |\n")
        f.write("| Exposure data quality | 20% | Biomonitoring data availability |\n")
        f.write("| Concentration relevance | 20% | Overlap of exposure with bioactive levels |\n")
        f.write("| Geographic overlap | 20% | Contamination in arboviral regions |\n")
        f.write("| Intervention potential | 15% | Feasibility of exposure reduction |\n")


def main():
    parser = argparse.ArgumentParser(description='Prioritize xenobiotics for research')
    parser.add_argument('--input', '-i', type=Path, default=Path('data/xenobiotics_database.json'),
                        help='Input database JSON file')
    parser.add_argument('--output', '-o', type=Path, default=Path('results'),
                        help='Output directory for results')
    args = parser.parse_args()

    # Load database
    with open(args.input) as f:
        db = json.load(f)

    xenobiotics = db.get('xenobiotics', [])
    print(f"Loaded {len(xenobiotics)} xenobiotics from database")

    # Calculate scores
    scores = calculate_all_scores(xenobiotics)

    # Create output directory
    args.output.mkdir(parents=True, exist_ok=True)

    # Generate reports
    generate_report(scores, args.output)

    # Print summary
    print("\n=== PRIORITIZATION RESULTS ===\n")
    print(f"{'Rank':<5} {'Compound':<40} {'Score':<8}")
    print("-" * 55)
    for rank, s in enumerate(scores[:10], 1):
        print(f"{rank:<5} {s.name:<40} {s.total_score:.2f}")

    print(f"\nFull results saved to {args.output}/")


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Script para identificacao de integrinas em proteomas usando HMMER.

Este script automatiza a busca de dominios de integrinas em arquivos FASTA
de proteomas usando perfis HMM do Pfam.

Uso:
    python analyze_integrins.py --proteome <arquivo.faa> --output <diretorio>

Autor: Analise Bioinformatica
Data: 2026-01-12
"""

import argparse
import subprocess
import os
import sys
from pathlib import Path


def check_hmmer_installation():
    """Verifica se o HMMER esta instalado."""
    try:
        result = subprocess.run(['hmmsearch', '-h'], capture_output=True, text=True)
        if result.returncode == 0:
            print("[OK] HMMER encontrado")
            return True
    except FileNotFoundError:
        pass
    print("[ERRO] HMMER nao encontrado. Instale com: apt-get install hmmer")
    return False


def run_hmmsearch(hmm_file, proteome_file, output_dir, evalue=1e-5):
    """
    Executa hmmsearch para buscar dominios de integrinas.

    Args:
        hmm_file: Caminho para o arquivo de perfis HMM
        proteome_file: Caminho para o arquivo FASTA do proteoma
        output_dir: Diretorio para salvar os resultados
        evalue: Threshold de E-value (padrao: 1e-5)

    Returns:
        Tupla com caminhos dos arquivos de saida (tblout, domtblout, output)
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    tblout = output_dir / "integrin_hits.tbl"
    domtblout = output_dir / "integrin_domains.tbl"
    output = output_dir / "integrin_search_output.txt"

    cmd = [
        'hmmsearch',
        '--tblout', str(tblout),
        '--domtblout', str(domtblout),
        '-E', str(evalue),
        str(hmm_file),
        str(proteome_file)
    ]

    print(f"[INFO] Executando hmmsearch...")
    print(f"       Comando: {' '.join(cmd)}")

    with open(output, 'w') as f:
        result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True)

    if result.returncode != 0:
        print(f"[ERRO] hmmsearch falhou: {result.stderr}")
        return None

    print(f"[OK] Busca concluida")
    return str(tblout), str(domtblout), str(output)


def parse_hmmer_tblout(tblout_file):
    """
    Faz o parsing do arquivo tblout do HMMER.

    Args:
        tblout_file: Caminho para o arquivo tblout

    Returns:
        Lista de dicionarios com informacoes dos hits
    """
    hits = []
    with open(tblout_file, 'r') as f:
        for line in f:
            if line.startswith('#'):
                continue
            fields = line.split()
            if len(fields) >= 9:
                hit = {
                    'target_name': fields[0],
                    'query_name': fields[2],
                    'query_accession': fields[3],
                    'evalue': float(fields[4]),
                    'score': float(fields[5]),
                    'bias': float(fields[6]),
                    'description': ' '.join(fields[18:]) if len(fields) > 18 else ''
                }
                hits.append(hit)
    return hits


def generate_report(hits, output_file):
    """
    Gera um relatorio resumido dos hits encontrados.

    Args:
        hits: Lista de hits do HMMER
        output_file: Caminho para salvar o relatorio
    """
    # Agrupa hits por tipo de dominio
    alpha_hits = [h for h in hits if 'alpha' in h['query_name'].lower()]
    beta_hits = [h for h in hits if 'beta' in h['query_name'].lower()]

    # Remove duplicatas (mesmo target pode ter multiplos dominios)
    alpha_targets = list(set(h['target_name'] for h in alpha_hits))
    beta_targets = list(set(h['target_name'] for h in beta_hits))

    report = []
    report.append("=" * 60)
    report.append("RELATORIO DE IDENTIFICACAO DE INTEGRINAS")
    report.append("=" * 60)
    report.append("")
    report.append(f"Total de hits encontrados: {len(hits)}")
    report.append(f"Subunidades alfa identificadas: {len(alpha_targets)}")
    report.append(f"Subunidades beta identificadas: {len(beta_targets)}")
    report.append("")
    report.append("-" * 60)
    report.append("SUBUNIDADES ALFA:")
    report.append("-" * 60)

    for hit in alpha_hits:
        report.append(f"  {hit['target_name']}")
        report.append(f"    Dominio: {hit['query_name']}")
        report.append(f"    E-value: {hit['evalue']:.2e}")
        report.append(f"    Score: {hit['score']:.1f}")
        report.append(f"    Descricao: {hit['description']}")
        report.append("")

    report.append("-" * 60)
    report.append("SUBUNIDADES BETA:")
    report.append("-" * 60)

    for hit in beta_hits:
        report.append(f"  {hit['target_name']}")
        report.append(f"    Dominio: {hit['query_name']}")
        report.append(f"    E-value: {hit['evalue']:.2e}")
        report.append(f"    Score: {hit['score']:.1f}")
        report.append(f"    Descricao: {hit['description']}")
        report.append("")

    report.append("=" * 60)

    report_text = '\n'.join(report)

    with open(output_file, 'w') as f:
        f.write(report_text)

    print(report_text)
    return report_text


def extract_integrin_sequences(proteome_file, hit_ids, output_file):
    """
    Extrai as sequencias de integrinas do proteoma.

    Args:
        proteome_file: Caminho para o arquivo FASTA do proteoma
        hit_ids: Lista de IDs dos hits
        output_file: Caminho para salvar as sequencias extraidas
    """
    from Bio import SeqIO

    sequences = []
    for record in SeqIO.parse(proteome_file, "fasta"):
        if any(hit_id in record.id for hit_id in hit_ids):
            sequences.append(record)

    SeqIO.write(sequences, output_file, "fasta")
    print(f"[OK] {len(sequences)} sequencias extraidas para {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Identificacao de integrinas em proteomas usando HMMER"
    )
    parser.add_argument(
        '--proteome', '-p',
        required=True,
        help='Arquivo FASTA do proteoma'
    )
    parser.add_argument(
        '--hmm', '-m',
        default='hmm_profiles/integrin_profiles.hmm',
        help='Arquivo de perfis HMM (default: hmm_profiles/integrin_profiles.hmm)'
    )
    parser.add_argument(
        '--output', '-o',
        default='results',
        help='Diretorio de saida (default: results)'
    )
    parser.add_argument(
        '--evalue', '-e',
        type=float,
        default=1e-5,
        help='Threshold de E-value (default: 1e-5)'
    )

    args = parser.parse_args()

    # Verifica instalacao do HMMER
    if not check_hmmer_installation():
        sys.exit(1)

    # Verifica arquivos de entrada
    if not os.path.exists(args.proteome):
        print(f"[ERRO] Proteoma nao encontrado: {args.proteome}")
        sys.exit(1)

    if not os.path.exists(args.hmm):
        print(f"[ERRO] Arquivo HMM nao encontrado: {args.hmm}")
        sys.exit(1)

    # Executa a busca
    result = run_hmmsearch(args.hmm, args.proteome, args.output, args.evalue)

    if result is None:
        sys.exit(1)

    tblout, domtblout, output = result

    # Faz parsing dos resultados
    hits = parse_hmmer_tblout(tblout)

    # Gera relatorio
    report_file = os.path.join(args.output, 'integrin_report.txt')
    generate_report(hits, report_file)

    print(f"\n[INFO] Analise concluida!")
    print(f"       Resultados salvos em: {args.output}")


if __name__ == '__main__':
    main()

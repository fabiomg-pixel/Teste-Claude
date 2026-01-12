# Analise de Integrinas em Aedes aegypti

Este diretorio contem uma analise bioinformatica para identificar integrinas previstas no genoma de *Aedes aegypti* usando HMMER.

## Estrutura do Diretorio

```
integrin_analysis/
├── README.md
├── data/
│   └── Aedes_aegypti_proteome.faa    # Proteoma de referencia
├── hmm_profiles/
│   ├── Integrin_alpha.sto            # Alinhamento do dominio alfa
│   ├── Integrin_alpha.hmm            # Perfil HMM do dominio alfa
│   ├── Integrin_beta.sto             # Alinhamento do dominio beta
│   ├── Integrin_beta.hmm             # Perfil HMM do dominio beta
│   ├── Integrin_beta_tail.sto        # Alinhamento da cauda beta
│   ├── Integrin_beta_tail.hmm        # Perfil HMM da cauda beta
│   └── integrin_profiles.hmm*        # Perfis concatenados + indices
├── results/
│   ├── integrin_hits.tbl             # Tabela de hits por sequencia
│   ├── integrin_domains.tbl          # Tabela de hits por dominio
│   ├── integrin_search_output.txt    # Saida completa do hmmsearch
│   ├── integrin_summary_report.md    # Relatorio resumido
│   └── aedes_integrins_identified.txt # Lista das integrinas
└── scripts/
    └── analyze_integrins.py          # Script para analise automatizada
```

## Resultados Principais

### Integrinas Identificadas

| Tipo | Quantidade | Proteinas |
|------|------------|-----------|
| Subunidades Alfa | 5 | alphaPS1, alphaPS2, alphaPS3, alpha-4, alphaPS5 |
| Subunidades Beta | 2 | betaPS, betanu |

### E-values

Todos os hits apresentaram E-values altamente significativos (< 1e-35), indicando alta confianca na identificacao.

## Como Reproduzir

### Requisitos

- HMMER 3.4 ou superior
- Python 3.8+ (opcional, para o script)

### Instalacao do HMMER

```bash
# Ubuntu/Debian
sudo apt-get install hmmer

# macOS
brew install hmmer

# Conda
conda install -c bioconda hmmer
```

### Executar a Analise

```bash
# Usando hmmsearch diretamente
cd integrin_analysis
hmmsearch --tblout results/integrin_hits.tbl \
          --domtblout results/integrin_domains.tbl \
          -E 1e-5 \
          hmm_profiles/integrin_profiles.hmm \
          data/Aedes_aegypti_proteome.faa \
          > results/integrin_search_output.txt

# Usando o script Python
python scripts/analyze_integrins.py \
    --proteome data/Aedes_aegypti_proteome.faa \
    --hmm hmm_profiles/integrin_profiles.hmm \
    --output results \
    --evalue 1e-5
```

## Perfis HMM Utilizados

Os perfis foram construidos a partir de alinhamentos multiplos de sequencias de integrinas de:

- *Aedes aegypti*
- *Drosophila melanogaster*
- *Homo sapiens*

### Dominios

1. **Integrin_alpha (PF01839)**: Repeticoes FG-GAP que formam a estrutura beta-propeller
2. **Integrin_beta (PF00362)**: Dominio vWA-like para heterodimerizacao
3. **Integrin_B_tail (PF07965)**: Cauda citoplasmatica com motivos NPxY

## Download do Proteoma Completo

Para analise com o proteoma completo de *Aedes aegypti*, baixe do NCBI:

```bash
# AaegL5.0 - versao mais recente do genoma
curl -O https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/002/204/515/GCF_002204515.2_AaegL5.0/GCF_002204515.2_AaegL5.0_protein.faa.gz
gunzip GCF_002204515.2_AaegL5.0_protein.faa.gz
```

## Referencias

1. Brown NH. (2000) Cell-cell adhesion via the ECM: integrin genetics in fly and worm. Matrix Biol.
2. Hynes RO. (2002) Integrins: bidirectional, allosteric signaling machines. Cell.
3. El-Gebali S, et al. (2019) The Pfam protein families database in 2019. Nucleic Acids Res.
4. Matthews BJ, et al. (2018) Improved reference genome of Aedes aegypti informs arbovirus vector control. Nature.

## Licenca

Este projeto e parte de uma analise bioinformatica educacional.

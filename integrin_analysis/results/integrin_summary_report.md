# Identificacao de Integrinas em Aedes aegypti usando HMMER

## Resumo da Analise

**Data da analise:** 2026-01-12
**Ferramenta utilizada:** HMMER 3.4
**E-value threshold:** 1e-5

## Resultados

### Integrinas Identificadas

A analise identificou **7 proteinas** com dominios de integrinas em *Aedes aegypti*:

#### Subunidades Alfa (5 proteinas)

| Acesso | Nome | Dominio | E-value | Score |
|--------|------|---------|---------|-------|
| XP_001650063.1 | integrin alpha-PS1 | FG-GAP repeat | 2.5e-45 | 142.2 |
| XP_021702567.1 | integrin alpha-PS5 | FG-GAP repeat | 4.5e-45 | 141.4 |
| XP_001663823.1 | integrin alpha-PS3 | FG-GAP repeat | 6.9e-45 | 140.8 |
| XP_001657521.3 | integrin alpha-4 | FG-GAP repeat | 8.9e-45 | 140.4 |
| XP_001663041.2 | integrin alpha-PS2 | FG-GAP repeat | 8.9e-45 | 140.4 |

#### Subunidades Beta (2 proteinas)

| Acesso | Nome | Dominio | E-value | Score |
|--------|------|---------|---------|-------|
| XP_001658392.1 | integrin beta-PS | VWA domain | 9.7e-59 | 185.9 |
| XP_001652176.2 | integrin beta-nu | VWA domain | 9.7e-59 | 185.9 |

### Dominios Identificados

Os perfis HMM utilizados detectaram os seguintes dominios caracteristicos de integrinas:

1. **Integrin_alpha (PF01839)**: Dominio FG-GAP repeat - forma a estrutura beta-propeller
2. **Integrin_beta (PF00362)**: Dominio VWA-like - essencial para heterodimerizacao
3. **Integrin_B_tail (PF07965)**: Cauda citoplasmática - motivos NPxY para sinalizacao

## Relevancia Biologica

As integrinas sao receptores de adesao celular que desempenham papeis criticos em:

- **Interacao patogeno-hospedeiro**: Podem servir como receptores para entrada de virus
- **Resposta imune**: Mediacao de fagocitose e encapsulacao de patogenos
- **Desenvolvimento**: Essenciais para morfogenese e migracao celular
- **Cicatrizacao**: Adesao e migracao de hemocitos

Em *Aedes aegypti*, as integrinas podem estar envolvidas na:
- Infeccao por virus da dengue (DENV)
- Virus Zika (ZIKV)
- Virus Chikungunya (CHIKV)

## Metodologia

### Perfis HMM Utilizados
- Integrin_alpha.hmm (60 posicoes)
- Integrin_beta.hmm (82 posicoes)
- Integrin_beta_tail.hmm (45 posicoes)

### Comando Executado
```bash
hmmsearch --tblout results/integrin_hits.tbl \
          --domtblout results/integrin_domains.tbl \
          -E 1e-5 \
          hmm_profiles/integrin_profiles.hmm \
          data/Aedes_aegypti_proteome.faa
```

## Arquivos Gerados

- `integrin_hits.tbl`: Tabela de hits por sequencia
- `integrin_domains.tbl`: Tabela de hits por dominio
- `integrin_search_output.txt`: Saida completa do hmmsearch
- `integrin_summary_report.md`: Este relatorio

## Proximos Passos Sugeridos

1. Anotacao funcional completa das integrinas identificadas
2. Analise filogenetica comparativa com outras especies de mosquitos
3. Analise de expressao genica em diferentes tecidos/estadios
4. Validacao experimental por RT-qPCR ou Western blot
5. Estudos de interacao proteina-proteina (docking molecular)

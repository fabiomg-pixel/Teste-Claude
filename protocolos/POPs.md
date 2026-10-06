# Índice de POPs e Livros de Registro
## LUCHM / IBCCF / UFRJ

---

## Entomologia de Vetores — Insetário de *Anopheles*

- [x] [POP-ANO-001 — Criação e manutenção de colônia de *Anopheles stephensi*](POP-ANO-001_Criacao_Anopheles_stephensi.md) — Versão 1.0 | Out/2026
- [x] [Livro de Registro da Criação — Colônia de *A. stephensi*](REGISTRO_ANO_Criacao_LivroDeRegistro.md) — Registro por coorte, acompanhamento diário e painel de colônia | Versão 1.0 | Out/2026
- [x] [POP-ANO-002 — Alimentação sanguínea de *A. stephensi* sobre camundongo anestesiado](POP-ANO-002_Alimentacao_Sanguinea_Camundongo_Anestesiado.md) — Procedimento sob protocolo CEUA | Versão 1.0 | Out/2026
- [x] [Livro de Registro e Controle de Espaço — Insetário](REGISTRO_ANO_Insetario_ControleEspaco.md) — Capacidade, alocação física, condições ambientais, contenção e auditoria mensal | Versão 1.0 | Out/2026

### Manuais Técnicos complementares
- [ ] Manual Técnico — Criação de *A. stephensi* (pendente)
- [ ] Manual Técnico — Repasto sanguíneo em hospedeiro vertebrado (pendente)

---

## Dependências entre documentos

```
POP-ANO-001 (criação) ──► REGISTRO_ANO_Criacao (seções A, B, D, E)
      │
      └── Etapa 7 ──────► POP-ANO-002 (repasto) ──► REGISTRO_ANO_Criacao (seção C)
                                │
                                └── CEUA nº ______ (condição de execução)

Todos ─────────────────────► REGISTRO_ANO_Insetario (espaço, ambiente, contenção)
```

---

## Campos a preencher antes do primeiro uso

| Documento | Campo pendente |
|---|---|
| POP-ANO-001 | Responsável técnico; aprovador; registro de treinamento (§12) |
| POP-ANO-002 | **Nº e validade do protocolo CEUA**; equipe aprovada; registro de treinamento (§13) |
| REGISTRO_ANO_Criacao | Nº do livro; responsável técnico; geração (F) atual da colônia |
| REGISTRO_ANO_Insetario | Sala; área útil; **capacidade declarada (A.2)**; horário do fotoperíodo; contatos de emergência |

---

## Pendências de produção

- [ ] Converter os quatro documentos em DOCX pela skill `lab-protocol-docs` (design visual
      padronizado, caixas de advertência, cabeçalhos de etapa, campos preenchíveis com linha de
      escrita) e validar com `validate.py`.

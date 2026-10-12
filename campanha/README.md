# O Oitavo Canto — campanha de D&D 5e em Aldemar

Campanha solo mestrada pela Claude, jogada por texto, em português. Este diretório é a memória inteira do jogo: mundo, trama, regras, estado e painel visual.

**Painel visual (artefato):** https://claude.ai/artifact/RtVpxN9EybeLwnQnvMYdqJ

## Como retomar uma sessão

Abra uma sessão da Claude Code neste repositório e diga qualquer coisa de jogo ("vamos continuar", uma ação do personagem, "recapitula"). O `CLAUDE.md` na raiz instrui a Mestra a ler o estado e continuar de onde parou. Funciona com qualquer modelo.

## Estrutura

| Pasta / arquivo | O que é | Jogador pode ler? |
|---|---|---|
| `mundo/00-visao-geral.md` | O mundo em uma página: o Veio, as Vozes, a Cicatriz, a Febre Pálida, tom, calendário | sim |
| `mundo/01-geografia.md` | Continente e a Marca de Brumal, lugar por lugar | sim |
| `mundo/02-historia.md` | Linha do tempo, o que cada camada da sociedade sabe | sim |
| `mundo/03-faccoes.md` | Coroa, Colégio, Ordem da Brasa, druidas, Guilda, culto, Ssuraki | sim |
| `mundo/04-cosmologia-e-magia.md` | As Sete Vozes, zonas do Veio, Marcas de Ressonância, itens | sim |
| `mundo/05-npcs.md` | Quem é quem na Marca, com voz e motivação | sim |
| `mundo/06-bestiario.md` | Criaturas do Coro e da região | sim (sabe-se lá o que vai enfrentar) |
| `trama/segredos-do-mestre.md` | **A verdade, os três atos, agendas ocultas** | **não** |
| `trama/rastreador-de-pistas.md` | Pistas descobertas e aliados conquistados | **não** |
| `sistema/regras.md` | Adaptações de D&D 5e para jogo solo por texto | sim |
| `sistema/procedimentos-do-mestre.md` | Manual de operação da Mestra | sim (nada secreto, só método) |
| `sistema/personagens-pre-gerados.md` | Quatro fichas de nível 3 | sim |
| `sistema/companheiros.md` | Fichas de sidekicks | sim |
| `estado/estado.json` | Estado vivo: personagem, tempo, local, cena, missões, jornal, NPCs, mapa, rolagens, combate | sim |
| `estado/rolagens.log` | Registro de todas as rolagens (criado no primeiro `--log`) | sim |
| `sessoes/sessao-NN.md` | Crônica de cada sessão, com "Onde paramos" | sim |
| `dashboard/template.html` | Template do painel | sim |
| `dashboard/index.html` | Painel construído (abra no navegador ou veja o artefato) | sim |
| `ferramentas/dado.py` | Rolador de dados com aleatoriedade criptográfica | sim |
| `ferramentas/atualizar_dashboard.py` | Valida o estado e reconstrói o painel | sim |

## Ferramentas

```bash
python3 campanha/ferramentas/dado.py 1d20+5 --rotulo "Ataque" --cd 15 --log
python3 campanha/ferramentas/dado.py ini "Dalva:1" "Lobos:2"
python3 campanha/ferramentas/atualizar_dashboard.py --check
python3 campanha/ferramentas/atualizar_dashboard.py
```

## Licença das regras

Mecânicas baseadas no System Reference Document 5.1 da Wizards of the Coast, sob Creative Commons Attribution 4.0. Mundo, trama e textos são originais desta campanha.

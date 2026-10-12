# Sistema de Regras — "O Oitavo Canto"

Base: **Dungeons & Dragons 5ª edição** (regras de 2014; o SRD 5.1 é a referência aberta). Tudo em português do Brasil. Este documento registra as adaptações para jogo por texto com um jogador. O que não está aqui funciona como no livro.

## 1. Formato de jogo

- **Um jogador**, um personagem principal (PJ). Companheiros (NPCs com regras de *sidekick*) acompanham o grupo e são controlados pelo Mestre com direção geral do jogador.
- **O Mestre** é a Claude. Narra, interpreta todos os NPCs, aplica as regras, rola os dados e mantém o estado da campanha e o painel visual.
- **Nível inicial: 3.** Jogo solo em nível 1 é letal demais. Progressão por **marcos** (eventos da história), não por pontos de experiência.

## 2. Como funciona um turno de jogo

1. O Mestre descreve a cena e, se útil, sugere de duas a quatro ações possíveis. **O jogador nunca está limitado às sugestões.**
2. O jogador declara o que faz, em texto livre. Pode falar como o personagem (entre aspas) ou descrever.
3. Perguntas sobre a cena ("o que vejo?", "quanto tempo levo?") não gastam tempo nem turno.
4. Se a ação tem chance real de falhar e consequência interessante, o Mestre pede um teste e rola.
5. O Mestre narra o resultado e o novo estado.

**Cabeçalho de cena**: toda mudança de local ou de tempo abre com uma linha assim:
`📍 Vila Candeia, Cais Velho · 24 de Vindima · crepúsculo · ⏳ 7 dias para a Noite das Peregrinas`

## 3. Dados

- **Quem rola**: o Mestre, usando a ferramenta `ferramentas/dado.py`, que usa aleatoriedade criptográfica. Toda rolagem é mostrada ao jogador em bloco de código: expressão, dados obtidos, modificadores, total e resultado.
- O jogador pode pedir para rolar os próprios dados físicos e informar o resultado. Sistema de honra. Diga isso uma vez e vale para a campanha.
- **Vantagem/desvantagem**: 2d20, maior/menor. Nunca se acumulam.
- **Crítico**: 20 natural dobra os dados de dano. 1 natural em ataque é falha automática e o Mestre pode adicionar uma complicação pequena (nunca "você derruba a arma" sem graça; algo que mova a cena).

## 4. Testes e dificuldades

| Dificuldade | CD |
|---|---|
| Fácil | 10 |
| Moderada | 13 |
| Difícil | 15 |
| Muito difícil | 18 |
| Heroica | 20 |
| Quase impossível | 25 |

- **Falha para frente**: uma falha nunca é "nada acontece". Custa tempo, barulho, um recurso, ou revela algo ruim.
- **Provas reduzem CDs sociais**: cada prova concreta apresentada a um NPC reduz a CD de Persuasão/Intimidação em 2 (mínimo 10).
- **Testes de grupo** só quando faz sentido (furtividade com companheiros).

## 5. Combate

- **Iniciativa**: cada PJ e companheiro rola; inimigos rolam por grupo (um valor para todos os lobos, outro para o chefe).
- **Teatro da mente** por padrão. Para combates importantes, o painel mostra uma **grade tática** com posições.
- **PV dos inimigos** são descritos (ileso, ferido, machucado, quase caindo) a menos que o jogador tenha razão para saber números.
- **Capangas**: criaturas de ND 1/4 ou menos morrem ao chegar a 0 PV sem rolagem extra e podem fugir em teste de moral (o Mestre rola 1d20; 10 ou menos = fogem) quando metade do grupo cai.
- **Descansos**: curto = 1 hora; longo = 8 horas, requer lugar razoavelmente seguro. Em Zona Forte, veja `mundo/04`.

## 6. Morte e segurança

- 0 PV: testes de resistência contra a morte, como no livro.
- **Sorte do Andarilho**: 1 uso por ato. Quando o PJ fosse morrer, em vez disso cai a 1 PV, estável, e algo improvável acontece (uma mariposa pousa na ferida, a flecha atinge o medalhão). Recarrega no início de cada ato.
- **Inspiração**: concedida por interpretação boa, ideia criativa ou escolha difícil fiel ao personagem. Gasta-se para ter vantagem em uma rolagem. Máximo 1 guardada.
- Companheiros podem morrer de verdade. O mundo tem peso.

## 7. Mecânicas da campanha

- **Marcas de Ressonância (0-5)**: contaminação pelo Coro. Tabela completa em `mundo/04-cosmologia-e-magia.md`.
- **Zonas Ressoantes**: magia desafinada, Tabela de Ressonância (1d10).
- **Zonas Surdas**: nenhuma magia. Só no Ato III.
- **Relógio do Festival**: 7 dias. Cada dia tem eventos fixos. Viajar entre lugares da Marca custa horas (1 légua = 1 hora a pé, meia hora a cavalo ou de barco a favor).

## 8. Progressão por marcos

| Nível | Marco |
|---|---|
| 3 | Início |
| 4 | Destruir o Ninho da Mina **ou** convencer a Castelã com provas |
| 5 | Fim da Noite das Peregrinas |
| 6 | Chegar a Alvaréns com a verdade |
| 7 | Expor Alcântara |
| 8 | Chegar à Muralha de Inverno |
| 9-12 | Ato III: um nível por grande feito na Cicatriz |

Ao subir de nível: PV sobem pela média (ou rola-se, se o jogador preferir), e o jogador escolhe as opções da classe em conversa com o Mestre.

## 9. Companheiros (sidekicks)

Fichas em `sistema/companheiros.md`. Três moldes: **Guerreiro**, **Perito**, **Conjurador**. O jogador dá direção geral ("Bento, fica no barco", "Cássia, cura quem precisar"); o Mestre decide os detalhes. Companheiros ganham nível junto com o PJ.

## 10. Glossário PT-BR

| Inglês | Português usado |
|---|---|
| Ability check / saving throw | teste de habilidade / teste de resistência |
| Armor Class (AC) | Classe de Armadura (CA) |
| Hit Points (HP) | Pontos de Vida (PV) |
| Difficulty Class (DC) | Classe de Dificuldade (CD) |
| Proficiency bonus | bônus de proficiência |
| Strength, Dexterity, Constitution, Intelligence, Wisdom, Charisma | Força (FOR), Destreza (DES), Constituição (CON), Inteligência (INT), Sabedoria (SAB), Carisma (CAR) |
| Skills | perícias: Acrobacia, Adestrar Animais, Arcanismo, Atletismo, Atuação, Enganação, Furtividade, História, Intimidação, Intuição, Investigação, Medicina, Natureza, Percepção, Persuasão, Prestidigitação, Religião, Sobrevivência |
| Spell slot | espaço de magia |
| Cantrip | truque |
| Short/long rest | descanso curto/longo |
| Advantage/disadvantage | vantagem/desvantagem |
| Hit dice | dados de vida |
| Action / bonus action / reaction | ação / ação bônus / reação |
| Conditions | condições: agarrado, amedrontado, atordoado, caído, cego, enfeitiçado, envenenado, exausto, impedido, incapacitado, inconsciente, invisível, paralisado, petrificado, surdo |

## 11. O que o jogador pode fazer a qualquer momento

- Pedir um **resumo** da situação, das missões ou dos NPCs.
- Pedir para ver a **ficha** ou o **painel**.
- Pedir **recapitulação** da sessão anterior.
- Dizer "**pausa**" para conversar fora do personagem (regras, ritmo, tom).
- Pedir para **trocar o ritmo** (mais combate, mais investigação, mais conversa).

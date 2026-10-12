# Procedimentos do Mestre

Guia operacional para a Claude mestrar "O Oitavo Canto". Vale para qualquer modelo que assuma a cadeira (Fable, Opus, Sonnet). Leia junto com `CLAUDE.md` na raiz do repositório.

## 0. Ao iniciar uma sessão

1. Leia `campanha/estado/estado.json` inteiro. É a verdade atual: personagem, companheiros, local, data, relógio, missões, NPCs conhecidos, lugares descobertos, últimas rolagens.
2. Leia o último arquivo em `campanha/sessoes/`. Termina com "Onde paramos".
3. Leia `campanha/trama/segredos-do-mestre.md` e `campanha/trama/rastreador-de-pistas.md`. Nunca cite o conteúdo deles ao jogador.
4. Consulte `campanha/mundo/` conforme a cena exigir. Não é preciso reler tudo.
5. Abra a sessão com uma **recapitulação** de 3 a 6 linhas, o cabeçalho de cena e uma pergunta: "O que você faz?"

## 1. O loop de cada resposta

1. Interprete a ação. Se for pergunta, responda sem avançar o tempo.
2. Decida se há teste. Escolha perícia e CD (tabela em `regras.md`). Se não há chance de falha ou a falha é chata, não role: narre.
3. **Role sempre com a ferramenta**, nunca de cabeça:
   ```bash
   python3 campanha/ferramentas/dado.py 1d20+5 --rotulo "Percepção de Dalva" --log
   ```
   Mostre o bloco de resultado ao jogador.
4. Narre. Sucesso com cor, falha com consequência. Dê voz distinta a cada NPC.
5. Atualize o estado em memória (PV, itens, pistas, relações, hora do dia).
6. Feche com cabeçalho de cena, se mudou, e de duas a quatro opções sugeridas. Lembre que o jogador é livre.

## 2. Ritmo e tom

- Respostas entre 150 e 400 palavras em cenas normais. Mais curtas em combate (uma rodada por resposta, no máximo duas). Mais longas apenas em revelações.
- Segunda pessoa ("você"), presente. Português do Brasil.
- Sensorial: um detalhe de som, um de cheiro, um de luz por cena. Candeia cheira a cera. A Mina cheira a cobre e flor doce. O Pântano a lama e peixe.
- Falas de NPC entre aspas, com nome em negrito na primeira vez que aparece na cena.
- Humor vem das pessoas. Horror vem da calma dos doentes. Nunca descreva gore gratuito.
- Não faça o jogador de bobo. Se ele tem uma ideia boa, funciona ou quase funciona.
- O jogador é cientista de formação. Recompense raciocínio investigativo (mapear casos, isolar variáveis, dissecar uma mariposa) com pistas reais. Dentro da ficção, use a linguagem do mundo: "história natural", "humores", "o Veio", nunca jargão moderno.

## 3. Combate em texto

1. Role iniciativa com a ferramenta. Mostre a ordem.
2. A cada rodada: descreva o campo em uma frase, resolva os inimigos, pergunte ao jogador.
3. Para combates com mais de quatro combatentes ou terreno relevante, preencha `combate.grade` no estado e republique o painel para mostrar a grade tática.
4. PV dos inimigos em palavras. Do PJ e companheiros, em números.
5. Termine o combate com um parágrafo de respiração: ferimentos, saque, o que a cena mudou.

## 4. Persistência: quando salvar

Salve (estado + sessão + painel + git) nestes momentos:
- fim de cena ou mudança de local;
- fim de combate;
- descanso;
- pista importante descoberta ou marco de missão;
- a cada cinco respostas, no máximo, se nada disso ocorreu;
- sempre ao encerrar a sessão.

Procedimento de salvamento:
```bash
# 1. editar campanha/estado/estado.json (python3 -c ... ou editor)
# 2. acrescentar ao jornal e à sessão em campanha/sessoes/sessao-NN.md
python3 campanha/ferramentas/atualizar_dashboard.py          # 3. reconstrói dashboard/index.html
# 4. republicar o artefato (ferramenta Artifact, url em CLAUDE.md) com file_path=campanha/dashboard/index.html
git add campanha && git commit -m "Sessão NN: <resumo curto>" && git push -u origin <branch>
```
Na primeira republicação de cada sessão, faça antes `Artifact read` na URL registrada. Depois disso, publique direto.

## 5. O que registrar no estado

- `tempo`: data, período do dia, `dias_para_festival`.
- `local`: onde o grupo está. `lugares[].estado`: `desconhecido` (não aparece no mapa), `conhecido` (ouviu falar), `visitado`, `atual`.
- `cena`: título, modo (`exploracao`, `social`, `combate`, `descanso`, `viagem`), resumo de 2-3 linhas.
- `personagem` e `companheiros`: PV, condições, espaços de magia, itens, Marcas, Inspiração, Sorte do Andarilho.
- `missoes`: objetivos com `feito`. Adicione objetivos conforme o jogador os descobre, nunca antes.
- `npcs`: só os que o jogador já conheceu. `atitude`: `aliado`, `amigavel`, `neutro`, `desconfiado`, `hostil`, `desconhecido`.
- `jornal`: uma entrada por cena relevante, em voz de crônica, 2-4 linhas, sem spoilers.
- `rolagens`: mantenha as últimas 12.
- `combate`: `ativo`, `rodada`, `ordem` (nome, iniciativa, pv, tipo, condicoes), `grade` opcional.

## 6. O relógio

A tabela de pulsos diários está em `trama/segredos-do-mestre.md`. Quando o dia muda, o pulso acontece **em cena** se o jogador estiver em Candeia, ou chega como notícia se não estiver. Atualize `dias_para_festival`. Mostre o relógio no cabeçalho sempre.

## 7. Pistas

Use o rastreador. Se o jogador trava, não entregue a resposta: entregue uma pista de outra cadeia por meio de um evento (um NPC procura o grupo, uma carta, um doente novo com um detalhe diferente). Três pistas por conclusão é o mínimo; se o jogador consumiu as três e ainda não concluiu, pode ser hora de um NPC conectar os pontos em voz alta.

## 8. Elementos visuais

- O **painel** (artefato) é o elemento visual principal: mapa com névoa de guerra, ficha, rastreador de combate, jornal, NPCs. Mantenha-o fiel ao estado.
- No chat, use o cabeçalho de cena, blocos de código para rolagens e, quando ajudar, mini-mapas ASCII para posicionamento rápido.
- **Ilustrações geradas** (ElevenLabs, Gamma, Canva) gastam créditos do jogador. Só gere se ele autorizar explicitamente. Se autorizar, uma por cena-chave, e anexe a URL em `cena.imagem` depois de subir como ativo do artefato.

## 9. Segurança e consentimento

- O jogador pode dizer "pausa" a qualquer hora para falar fora do personagem.
- Nada de violência sexual, tortura detalhada ou crueldade com crianças em cena. Inês morre fora de cena, e a notícia chega com peso, sem detalhe.
- O jogador decide o destino do personagem em morte: aceita a morte, usa a Sorte do Andarilho, ou negocia uma saída narrativa que custe algo.

## 10. Troca de personagem ou de modelo

- O jogador pode trocar de personagem entre sessões. O antigo vira NPC.
- Qualquer modelo que assuma a cadeira lê este arquivo e o `CLAUDE.md`. Não há dependência de memória de sessão: tudo está no repositório.

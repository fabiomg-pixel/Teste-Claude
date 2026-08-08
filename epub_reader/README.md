# Leitor de EPUB com companheiro de leitura

Um leitor de e-books com as comodidades de um Kindle ou do Google Play Livros
— paginação, temas, tipografia ajustável, sumário, destaques, notas,
marcadores, busca, progresso e tempo restante — mais uma coisa que nenhum dos
dois tem: **uma conversa com a LLM que só conhece o livro até onde você leu**.

Você pode perguntar “o que aconteceu até aqui?”, “quem é essa pessoa mesmo?”,
“o que significa este trecho?” ou “que guerra é essa que eles citam?” sem
correr o risco de receber de volta o final do livro.

---

## A fronteira anti-spoiler

O ponto central do projeto. O livro é fatiado em **blocos** (parágrafos,
títulos, itens de lista), numerados de 0 a N-1 na ordem de leitura. A posição
do leitor é um índice de bloco, e a *fronteira* é o bloco mais avançado que
ele já alcançou.

Tudo o que o modelo recebe é montado **exclusivamente** a partir dos blocos
antes da fronteira:

| Fonte | O que é | Recorte |
|---|---|---|
| Memória | Um resumo por capítulo, gerado sob demanda e guardado em cache | O capítulo em que você está é resumido só até o seu bloco atual |
| Trechos | Busca BM25 sobre o texto lido, para a pergunta feita | Blocos com índice ≤ fronteira |
| Leitura recente | Os últimos ~6 mil caracteres lidos, na íntegra | Blocos com índice ≤ fronteira |

Isso é uma barreira **estrutural**, não uma promessa: o texto posterior não
existe no pedido enviado ao modelo. O servidor ainda limita a fronteira pedida
pelo cliente ao que o progresso registrado comprova
(`_boundary()` em `app.py`), então nem um cliente adulterado consegue pedir
contexto além do lido.

Sobre essa base vem a camada de comportamento, no prompt do sistema: o modelo
pode reconhecer a obra pelo treinamento, e é instruído a não revelar,
insinuar nem antecipar nada do que vem depois — inclusive o clássico “isso vai
fazer sentido mais adiante”, que já é spoiler estrutural. Conhecimento externo
é bem-vindo para conceitos, história, ciência e referências; é vedado para o
enredo desta obra.

O teste `test_contexto_nao_passa_da_fronteira` verifica, bloco a bloco, que
nada além da fronteira aparece no que se manda ao modelo.

---

## Duas formas de usar

| | `app.py` (servidor) | `leitor-celular.html` (página solta) |
|---|---|---|
| Onde roda | Flask + SQLite na sua máquina | Inteiramente no navegador, inclusive no Android |
| Conversa | Integrada, em streaming, com resumos por capítulo | Monta o texto da pergunta para você colar no app do Claude |
| Instalação | `pip install -r requirements.txt` | Nenhuma — é um arquivo HTML |
| Anti-spoiler | Recorte no servidor, limitado pelo progresso registrado | Mesmo recorte, feito no aparelho |

O arquivo `leitor-celular.html` é autossuficiente: abre EPUB (descompacta com
`DecompressionStream`), pagina, guarda livro e anotações no navegador e monta o
mesmo contexto anti-spoiler. Ele não fala com nenhum servidor — daí o
copiar-e-colar em vez da conversa integrada.

## Como rodar

```bash
cd epub_reader
pip install -r requirements.txt

export ANTHROPIC_API_KEY="sua-chave"     # opcional: sem ela, só a leitura funciona
python app.py                            # http://localhost:5001
```

Adicione um `.epub` pela biblioteca (botão ou arrastando) e comece a ler. Os
arquivos ficam em `epub_reader/data/` — nada sai da sua máquina exceto o que
você envia ao modelo ao conversar.

### Variáveis de ambiente

| Variável | Padrão | Para quê |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Habilita a conversa |
| `EPUB_LLM_MODEL` | `claude-opus-5` | Modelo da conversa |
| `EPUB_SUMMARY_MODEL` | igual ao acima | Modelo dos resumos de capítulo (use um menor para baratear) |
| `EPUB_LLM_EFFORT` | `medium` | `low`/`medium`/`high`/`xhigh`/`max` |
| `EPUB_DATA_DIR` | `epub_reader/data` | Onde ficam livros e banco |
| `PORT` | `5001` | Porta do servidor |

### Testes

```bash
cd epub_reader
python -m unittest test_leitor -v
```

Nove testes cobrindo o parser, a API de leitura, a busca, o caminho da
conversa (com um cliente falso, sem gastar API) e a fronteira anti-spoiler.

---

## O que o leitor faz

**Leitura**
- Paginação em colunas (uma ou duas), ou rolagem contínua
- Temas claro, sépia, escuro e noturno
- Tamanho do texto, entrelinha, largura da coluna, fonte (serifada/sem
  serifa/mono) e alinhamento
- Sumário navegável (EPUB 3 `nav` ou EPUB 2 NCX), links internos funcionando
- Progresso salvo, tempo restante estimado (com WPM ajustado ao seu ritmo)
- Busca dentro do livro — por padrão só no que já foi lido, com opção de
  buscar no livro inteiro
- Destaques em quatro cores, notas, marcadores
- Atalhos: `←`/`→` ou espaço (páginas), `s` (sumário), `c` (conversa),
  `b` (marcador), `a` (aparência), `/` (busca), `f` (modo imersivo), `Esc`

**Conversa**
- Pergunta livre sobre o que já foi lido
- Botões de modo: **Recapitular**, **Quem é quem**, **Refletir**, **Contexto**
- Selecione um trecho no texto → “Perguntar” leva a seleção para a conversa
- Modo estrito: responde só com base no texto, sem conhecimento externo
- Respostas em streaming, com as passagens usadas como fontes clicáveis que
  levam de volta ao ponto do livro
- Histórico por livro, guardado localmente

---

## Estrutura

```
epub_reader/
├── app.py            # rotas Flask (biblioteca, leitura, anotações, conversa SSE)
├── epub_parser.py    # EPUB → capítulos sanitizados + blocos numerados + sumário
├── store.py          # SQLite (progresso, anotações, conversa, resumos) + JSON do livro
├── retrieval.py      # BM25 e busca literal, sempre com recorte por fronteira
├── assistant.py      # prompts, memória por capítulo, montagem do contexto, streaming
├── test_leitor.py    # testes de fumaça
├── templates/        # library.html, reader.html
└── static/           # css/ e js/ (sem build, sem dependências de front-end)
```

### Notas de implementação

- **Sanitização**: o HTML de cada capítulo é filtrado por lista de permissão
  (`script`, `style`, `iframe` e afins caem fora), o CSS do livro é descartado
  para que a tipografia do leitor valha sempre, e links e imagens são
  reescritos para rotas internas.
- **Memória incremental**: os resumos são gerados capítulo a capítulo, sob
  demanda, e guardados em cache por `(livro, capítulo, bloco final)`. O
  capítulo em curso é resumido de novo quando você avança — o cache antigo
  continua válido para a posição antiga.
- **Cache de prompt**: o contexto vai num bloco de `system` com
  `cache_control`, então uma conversa com várias perguntas na mesma posição
  reaproveita o prefixo.
- **Custo**: cada capítulo novo custa um resumo (uma chamada curta). Se isso
  pesar, aponte `EPUB_SUMMARY_MODEL` para um modelo menor.

## Limitações conhecidas

- Um leitor por instalação: não há contas nem autenticação. Não exponha o
  servidor na internet como está.
- DRM não é suportado (nem contornado): só EPUBs livres de proteção.
- Destaques são localizados pelo texto dentro do bloco; se a mesma frase
  aparecer duas vezes no mesmo parágrafo, a primeira ocorrência é marcada.
- O modelo conhece o livro pelo resumo e pelos trechos recuperados, não pelo
  texto inteiro — para perguntas muito específicas sobre detalhes de capítulos
  distantes, cite alguma palavra do trecho para ajudar a busca.

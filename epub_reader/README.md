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

## Três formas de usar

| | `app.py` (servidor) | `leitor-celular.html` (página solta) | `android/` (APK) |
|---|---|---|---|
| Onde roda | Flask + SQLite na sua máquina | Qualquer navegador, inclusive o do Android | Android 8 ou mais novo |
| Conversa | Integrada, com resumos por capítulo | Monta o texto para você colar no app do Claude | Integrada, com a sua chave no aparelho |
| Instalação | `pip install -r requirements.txt` | Nenhuma — é um arquivo HTML (`python pagina.py`) | Instalar o APK |
| Anti-spoiler | Recorte no servidor, limitado pelo progresso | Mesmo recorte, feito no aparelho | Mesmo recorte, feito no aparelho |
| Sincronia | é o servidor | com o servidor, se você ligar | com o servidor, se você ligar |

`leitor-celular.html` é autossuficiente: abre EPUB (descompacta com
`DecompressionStream`), pagina, guarda livro e anotações no navegador e monta o
mesmo contexto anti-spoiler. Sozinho ele não fala com servidor nenhum — daí o
copiar-e-colar.

O APK (veja [`android/`](../android/)) é uma casca de WebView em volta desse
mesmo arquivo: a página detecta a ponte nativa e troca o copiar-e-colar por
uma conversa em streaming, com a chamada à API feita em Java. Uma cópia só do
leitor serve aos três caminhos.

## O arquivo solto (iPhone, iPad, qualquer navegador)

No iOS não existe equivalente do APK — instalar um aplicativo fora da App Store
pede conta de desenvolvedor. O que existe é a página, e ela pode virar um
arquivo só:

```bash
cd epub_reader
python pagina.py leitor-iphone.html
```

São ~113 KB, e o arquivo não depende de mais nada.

O servidor também entrega o mesmo arquivo em `/leitor-iphone.html`, já como
download.

`leitor-celular.html` é um **fragmento** de propósito — é ele que vai publicado
como artifact, e lá o `<head>` quem escreve é o publicador. Para as outras três
bocas (o `/celular`, o asset do APK e este arquivo), `pagina.py` junta o
fragmento com `moldura-celular.html`, que traz o que falta:

| Sem a moldura | O que acontece |
|---|---|
| sem `<!doctype html>` | o navegador entra em modo *quirks* — não é o modo em que o leitor foi desenhado |
| sem `<meta charset>` | num `file://` não há cabeçalho HTTP dizendo que é UTF-8, e os acentos viram lixo |
| sem `<meta viewport>` | o Safari desenha a página com 980px de largura e encolhe tudo |
| sem as metas da Apple | *Adicionar à Tela de Início* não dá tela cheia nem ícone |

O ícone vai embutido em `data:` justamente para o arquivo continuar valendo
sozinho, aberto de onde for. O Gradle usa a mesma moldura, então os três
caminhos servem um documento idêntico.

**O que se perde abrindo o arquivo direto (`file://`)**: nessa origem o Safari
não deixa a página guardar nada, então o livro vale enquanto a aba está aberta e
a estante amanhece vazia — a própria página avisa isso quando detecta o caso.
Para a estante ficar (e para sincronizar), o arquivo precisa vir de um endereço
`http(s)`: o `/celular` do seu servidor. Abrir o arquivo solto serve para ler
agora, em qualquer aparelho, sem depender de nada.

## Sincronizar entre aparelhos

O servidor guarda o estado de leitura e os arquivos; cada aparelho manda o que
tem e recebe **a mescla** de volta — nunca uma substituição.

```bash
cd epub_reader
python app.py
```

Ele imprime o que os outros aparelhos precisam:

```
Leitor:      http://localhost:5001/
No celular:  http://<este-computador>:5001/celular
Token de sincronização: xxxxxxxxxxxxxxxxxxxxxx
```

Para deixar o servidor de pé no Mac sem depender de um terminal aberto, veja
[**Manter no ar no Mac**](#manter-no-ar-no-mac), logo abaixo.

Depois, em cada aparelho, abra a estante do leitor → **Sincronizar entre
aparelhos** → cole o endereço e o token. A partir daí:

- **Android**: no aplicativo (o APK), ou no Chrome pelo endereço `/celular`.
- **Mac**: `http://localhost:5001/celular` (ou o leitor completo em `/`).
- **iPhone**: abra `/celular` no Safari e use *Compartilhar → Adicionar à Tela
  de Início*. Vira um app com ícone e tela cheia, e a limpeza que o iOS faz em
  dados de sites deixa de importar, porque o estado volta do servidor.

Para alcançar o Mac de fora de casa sem abrir porta nenhuma na internet, o
[Tailscale](https://tailscale.com) é o caminho mais simples: instale nos três
aparelhos e use o endereço `100.x.y.z` ou o nome MagicDNS da máquina. Se quiser
HTTPS de verdade (e com ele o `crypto.subtle` do navegador), `tailscale cert`
resolve — mas não é necessário: o leitor calcula a impressão digital em
JavaScript puro quando a origem não é segura.

### Na nuvem (o jeito que não depende de deixar máquina ligada)

Depender do Mac aceso é o defeito do arranjo caseiro: o iPhone só sincroniza
quando acha o servidor, e um laptop fechado não serve ninguém. Na nuvem o
servidor fica de pé sozinho, com HTTPS de verdade, e os três aparelhos falam
com o mesmo endereço.

**Antes de subir, uma coisa tem de existir: uma porta.** Fora de casa o
endereço é público, e até esta versão só `/api/sync/*` pedia credencial —
todo o resto (a biblioteca, apagar um livro, e a conversa, que gasta a sua
chave da API) estava aberto a quem descobrisse a URL. Por isso o servidor
agora tem senha: veja [A porta de entrada](#a-porta-de-entrada), logo abaixo.

```bash
cd epub_reader
fly launch --no-deploy --copy-config
fly volumes create dados --size 3
fly secrets set EPUB_SENHA='uma senha sua' ANTHROPIC_API_KEY='sk-ant-...'
fly deploy
```

De baixo para cima: o `launch` cria o app a partir do `fly.toml` que já está
aqui (recuse Postgres e Redis, se ele oferecer — este leitor usa SQLite no
volume), o `volumes` cria o disco que sobrevive ao deploy, e o `secrets`
guarda a senha e a chave fora do repositório. Rode de dentro de
`epub_reader/`: a raiz do repositório tem outro projeto.

> Ao colar, note que estes blocos não têm comentários no fim das linhas de
> propósito: o zsh do macOS **não** trata `#` como comentário no prompt, então
> um `comando # explicação` colado vira `comando` com argumentos a mais.

O `fly.toml` já vem com o que importa: volume em `/data`, `force_https`,
health check em `/saude` e **`auto_stop_machines = "suspend"`** — a máquina
dorme quando ninguém está lendo e acorda no primeiro pedido, que é o certo
para um leitor pessoal, ocioso quase o dia inteiro. O preço é alguns segundos
na primeira página depois de um tempo parado.

Não consegui conferir os preços atuais do Fly (o ambiente onde este texto foi
escrito não alcança o site deles), então confira na página de preços: a conta
é uma máquina `shared-cpu-1x` de 512 MB, que dorme, mais alguns GB de volume.

No iPhone: abra o endereço, digite a senha uma vez, e *Compartilhar →
Adicionar à Tela de Início*. Na estante, ligue **Sincronizar entre aparelhos**
com o mesmo endereço e o token (`fly ssh console -C 'cat /data/token-sync.txt'`).

Outros caminhos, se preferir: qualquer VPS pequeno (Hetzner, DigitalOcean)
com o mesmo Dockerfile e um systemd; ou um Raspberry Pi em casa, que é
máquina ligada de novo, mas custa centavos de luz.

#### A porta de entrada

| | |
|---|---|
| `EPUB_SENHA` | a senha. **Sem ela não há porta** — é assim que o uso local continua sem atrito |
| `EPUB_EXIGIR_SENHA=1` | o servidor **se recusa a subir** sem senha. Vai no `fly.toml`, para que esquecer derrube o deploy em vez de deixá-lo aberto |
| `EPUB_ATRAS_DE_PROXY=1` | confia no `X-Forwarded-Proto`/`For` do proxy: sem isso o cookie não sai `Secure` e o freio contaria todo mundo como um IP só |
| `EPUB_SECRET` | assina o cookie; se não existir, é gerada e guardada em `/data` — para as sessões não caírem a cada deploy |

O cookie vale 30 dias, sai `HttpOnly`, `Secure` e `SameSite=Lax`, e oito erros
de senha no mesmo IP custam cinco minutos de espera. A sincronização continua
entrando pelo token `Bearer`, e não pelo cookie: o aplicativo do Android fala
com `/api/sync/*` sem navegador.

### Manter no ar no Mac

Se ainda preferir a casa: `python app.py` num terminal serve para
experimentar, mas morre quando você fecha a janela. Para o Mac servir sozinho:

```bash
cd epub_reader
./instalar-no-mac.sh
```

O instalador cria um ambiente Python próprio (`.venv`), instala as
dependências e registra um **LaunchAgent** em
`~/Library/LaunchAgents/br.leitor.semspoiler.plist`. Com `RunAtLoad` o
servidor sobe quando você faz login; com `KeepAlive`, o launchd o levanta de
novo se ele cair. No fim ele imprime o endereço e o token que o iPhone pede.

| | |
|---|---|
| Livros e anotações | `~/Library/Application Support/leitor-sem-spoiler` |
| Registro | `~/Library/Logs/leitor-sem-spoiler.log` |
| Ver se está de pé | `launchctl list \| grep semspoiler` |
| Reiniciar | `launchctl kickstart -k gui/$(id -u)/br.leitor.semspoiler` |
| Desligar e apagar | `./instalar-no-mac.sh --remover` (não encosta nos livros) |
| Ver o que ele faria | `./instalar-no-mac.sh --ensaio` |

A chave da API entra por `ANTHROPIC_API_KEY` no ambiente ou por uma pergunta
na hora, e fica guardada no plist — que é escrito com modo `600` e, ao
reinstalar, tem a chave anterior aproveitada. Rodar o instalador de novo
atualiza tudo sem perder nada; é o jeito de aplicar uma versão nova do código.

Duas coisas que o instalador não resolve por você:

- **Um Mac dormindo não serve ninguém.** Em *Ajustes → Bateria → Opções*,
  ligue «Impedir que o Mac durma automaticamente» (na tomada). Quem quiser
  garantia extra: `caffeinate -s`.
- **O firewall do macOS** pode perguntar se aceita conexões de entrada na
  primeira vez. É preciso responder *Permitir*, senão o iPhone não chega.

### Como a mescla decide

| Campo | Regra | Por quê |
|---|---|---|
| `fronteira` | o **maior** dos dois | só cresce; é ela que sustenta o anti-spoiler, e não pode retroceder |
| `posição` | a mais recente pelo relógio | quem leu por último manda |
| destaques e notas | união por id, com lápides | apagar num aparelho apaga em todos, e nada ressuscita |

Se você estiver lendo quando chega uma posição mais adiantada de outro
aparelho, o leitor **não** arranca a página: mostra um aviso tocável
("em outro aparelho você parou em…"), como faz o Kindle.

O livro é identificado pela impressão digital do arquivo (tamanho + SHA-256 dos
extremos), então o mesmo EPUB em dois aparelhos casa sozinho, sem depender de
metadados.

### Sobre a numeração dos blocos

Posição e destaques são índices de bloco, então o servidor e o navegador
precisam numerar os blocos **exatamente igual**. Por isso o parser do servidor
usa o `html5lib`: ele implementa o algoritmo de análise do HTML5, o mesmo do
navegador. Com o `html.parser` da biblioteca padrão, um `<p>` sem fechar —
comum em EPUBs — desloca todos os blocos seguintes, e a posição vinda do
celular cairia no lugar errado no Mac. O `test_sincronia_navegador.py` e o
utilitário de comparação existem para pegar esse tipo de regressão.

### Segurança

O token é a única chave: quem o tiver e alcançar o endereço lê e escreve toda a
sua biblioteca. Numa rede Tailscale isso é razoável — só os seus aparelhos
alcançam a máquina. Não exponha esse servidor na internet aberta como está: não
há usuários, limite de tentativas nem HTTPS próprio.

## Como rodar

```bash
cd epub_reader
pip install -r requirements.txt

export ANTHROPIC_API_KEY="sua-chave"
python app.py
```

A chave é opcional: sem ela o leitor funciona, só não conversa. O servidor
sobe em http://localhost:5001.

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
| `EPUB_SYNC_TOKEN` | gerado e guardado em `data/token-sync.txt` | Token da sincronização |
| `EPUB_SENHA` | vazia (sem porta) | Senha do servidor — obrigatória fora da sua máquina |
| `EPUB_EXIGIR_SENHA` | desligada | Recusa subir sem `EPUB_SENHA`; ligue na nuvem |
| `EPUB_ATRAS_DE_PROXY` | desligada | Ligue quando houver um proxy HTTPS na frente |
| `EPUB_SECRET` | gerada em `data/chave-sessao.txt` | Assina o cookie de sessão |
| `PORT` | `5001` | Porta do servidor |

### Testes

```bash
cd epub_reader
python -m unittest test_leitor test_sync test_porta -v
```

42 testes cobrindo o parser, a API de leitura, a busca, o caminho da conversa
(com um cliente falso, sem gastar API), a fronteira anti-spoiler e as regras de
mescla da sincronização, e a porta de entrada (senha, freio, o que fica
aberto e o que não).

Há ainda um teste de ponta a ponta que sobe o servidor e dirige **dois
aparelhos** (dois navegadores isolados) sincronizando de verdade — precisa do
Playwright:

```bash
pip install playwright && playwright install chromium
python test_sincronia_navegador.py
```

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
├── pagina.py         # monta o leitor de arquivo único como documento completo
├── porta.py          # senha, cookie de sessão e freio de tentativas
├── instalar-no-mac.sh    # LaunchAgent: o servidor sobe no login e se mantém
├── Dockerfile, fly.toml  # o mesmo leitor, na nuvem
├── moldura-celular.html  # doctype, charset, viewport e as metas de tela cheia
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

- Um leitor por instalação: há uma senha só, não contas. Serve para uma
  pessoa; não serve para dividir a biblioteca com alguém dando a mesma senha.
- Um livro que o celular envia pela sincronização fica disponível para os
  outros aparelhos, mas não entra na biblioteca do servidor (a de `/`). O
  caminho contrário — pôr pelo navegador e receber no celular — funciona.
- DRM não é suportado (nem contornado): só EPUBs livres de proteção.
- Destaques são localizados pelo texto dentro do bloco; se a mesma frase
  aparecer duas vezes no mesmo parágrafo, a primeira ocorrência é marcada.
- O modelo conhece o livro pelo resumo e pelos trechos recuperados, não pelo
  texto inteiro — para perguntas muito específicas sobre detalhes de capítulos
  distantes, cite alguma palavra do trecho para ajudar a busca.

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
| Conversa | Integrada, com resumos por capítulo | Integrada, com a sua chave no navegador (copiar-e-colar como reserva) | Integrada, com a sua chave no aparelho |
| Instalação | `python3 -m pip install -r requirements.txt` | Nenhuma — é um arquivo HTML (`python3 pagina.py`) | Instalar o APK |
| Anti-spoiler | Recorte no servidor, limitado pelo progresso | Mesmo recorte, feito no aparelho | Mesmo recorte, feito no aparelho |
| Sincronia | é o servidor | repositório privado do GitHub, ou o seu servidor | idem |

`leitor-celular.html` é autossuficiente: abre EPUB (descompacta com
`DecompressionStream`), pagina, guarda livro e anotações no navegador e monta o
mesmo contexto anti-spoiler.

### A conversa, sem copiar e colar

Cole uma chave da API da Anthropic (`sk-ant-…`) no painel da chave 🔑 e a
conversa acontece dentro do leitor, em streaming. A chave fica só naquele
aparelho; a chamada sai do seu navegador direto para `api.anthropic.com`, sem
passar por servidor meu nenhum. O uso é cobrado na sua conta da Anthropic.

Isso exige o cabeçalho `anthropic-dangerous-direct-browser-access: true` — sem
ele a API recusa todo pedido vindo de um navegador. O nome assusta de propósito,
e com razão: ele só se defende quando a chave é de quem está usando a página,
como aqui. Embutir a *sua* chave numa página que outros abrem seria o
anti-padrão que o nome denuncia.

São dois transportes para a mesma conversa — o Java do APK e o `fetch` do
navegador — atrás de um único motor, então a tela, o histórico, a marcação e o
tratamento de erro existem uma vez só. No artifact publicado não há transporte
nenhum: o CSP bloqueia a chamada, e lá vale o copiar-e-colar, que continua
inteiro como reserva em todos os casos.

O modelo padrão é o `claude-opus-5`; Sonnet 5 e Haiku 4.5 ficam a um toque. Se um
modelo recusar o pedido completo (a página pede raciocínio adaptativo, para ter o
que mostrar enquanto a resposta não vem), o leitor desce para o pedido mínimo,
responde, e lembra da escolha — em vez de deixar a conversa morta.

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
python3 pagina.py leitor-iphone.html
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

Há dois caminhos, e o primeiro não pede máquina ligada em casa nenhuma.

### Um repositório privado do GitHub (recomendado)

O repositório é a verdade; o navegador é cache. Os livros e a posição de leitura
ficam lá, e qualquer aparelho ligado ao mesmo repositório vê a mesma estante, a
mesma página e os mesmos destaques.

1. Em [github.com/new](https://github.com/new), crie um repositório **privado**.
   Não precisa marcar *Add a README*: um repositório sem commit nenhum não tem
   ramo para escrever, e o leitor faz o primeiro commit ele mesmo ao ligar.
2. Em **Settings → Developer settings → Personal access tokens → Fine-grained
   tokens**, gere um token com acesso **só a esse repositório** e a permissão
   **Contents: read and write**. Nada mais.
3. No leitor, em cada aparelho: estante → **Sincronizar entre aparelhos** →
   escreva `usuario/nome-do-repositorio` (a URL inteira, colada do navegador,
   também serve) e cole o token → **Ligar ao repositório**.

O acesso é conferido na hora: nome errado, token sem permissão ou token expirado
dão uma mensagem que diz o que fazer, e nada é guardado. Se o repositório estiver
vazio, o leitor cria o `LEIA-ME.md` e segue — em vez de mandar você ao site fazer
um commit à mão, de celular. Se o token expirar
depois, a sincronização de fundo **não** falha calada — aparece o aviso e a
estante passa a mostrar «token recusado — religue».

O token fica só no aparelho, no armazenamento do navegador. Ele não vai para o
repositório, nem para o servidor, nem para lugar nenhum: as chamadas saem do seu
navegador direto para `api.github.com`.

Dentro do repositório:

```
LEIA-ME.md                  o primeiro commit, se o repositório nasceu vazio
livros/<impressão>.epub     o arquivo, como você o abriu
estado/<impressão>.json     posição, fronteira, destaques
indice.json                 título e autor de cada um, para a estante
                            desenhar sem baixar livro nenhum
```

A impressão digital vem dos bytes do EPUB, então o mesmo arquivo importado em
dois aparelhos casa sozinho. A escrita usa a API de dados do git (blobs,
árvores, commits) e não a de conteúdo — esta última pára em 1 MB, e um romance
passa disso. Um commit leva estado e índice juntos: ou entra tudo, ou nada.

Dois aparelhos gravando ao mesmo tempo não se atropelam. O commit nasce sobre a
versão que foi lida; se o ramo andou nesse meio-tempo, o GitHub recusa o
`PATCH`, e o leitor relê, refaz a mescla e repete. É o mesmo controle de
concorrência de um `git push`.

### Um servidor seu, rodando na sua casa

O servidor guarda o estado de leitura e os arquivos; cada aparelho manda o que
tem e recebe **a mescla** de volta — nunca uma substituição.

```bash
cd epub_reader
python3 app.py
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

#### Hospedagem gratuita, de disco efêmero

Os planos gratuitos que não pedem cartão costumam vir com disco efêmero: o que
o servidor grava some a cada deploy e a cada vez que o serviço acorda. Para
quase todo aplicativo isso é impeditivo. Aqui não é — **o servidor não é o dono
dos dados**. Cada aparelho tem o livro inteiro e o estado completo, e a mescla
é comutativa e sem perda, então o primeiro aparelho que sincronizar depois de
um reset repovoa o servidor sozinho.

Isso é medido, não suposto — `test_disco_efemero.py` apaga a pasta de dados
inteira com o servidor no ar, sobe tudo do zero e confere que o livro, o
arquivo, a fronteira e os destaques voltam, e que um aparelho novo, só com
endereço e token, recebe a biblioteca completa depois do reset:

```bash
cd epub_reader
python3 test_disco_efemero.py
```

Duas coisas **não** se reconstroem, e são exatamente as que quebram calado:

| Se nascer do disco | O que acontece a cada reinício |
|---|---|
| `EPUB_SYNC_TOKEN` | um token novo: todos os aparelhos passam a levar 401, sem explicação |
| `EPUB_SECRET` | uma chave nova: todo mundo é deslogado quando o serviço acorda |

Por isso, ligue `EPUB_DISCO_EFEMERO=1`: com ela o servidor **se recusa a subir**
sem os dois definidos no ambiente. Para gerar os três valores:

```bash
cd epub_reader
python3 segredos.py
```

Depois é a mesma imagem de sempre, em qualquer hospedagem que aceite um
Dockerfile. O que ela precisa saber:

| Variável | Valor |
|---|---|
| `EPUB_SENHA` | a senha do navegador |
| `EPUB_SYNC_TOKEN` | o token dos aparelhos |
| `EPUB_SECRET` | assina o cookie |
| `EPUB_EXIGIR_SENHA` | `1` |
| `EPUB_DISCO_EFEMERO` | `1` |
| `EPUB_ATRAS_DE_PROXY` | `1` |

A porta não precisa ser configurada: a imagem escuta na `$PORT` que a
hospedagem injetar, e cai em 8080 se não houver nenhuma.

O preço de um serviço que dorme é a espera na primeira página depois de um
tempo parado. O leitor lida com isso: em erro de rede ou 5xx ele tenta de novo,
com espera crescente, mostrando «acordando o servidor…» — um 401 ou 400, que
são definitivos, ele não repete.

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

Se ainda preferir a casa: `python3 app.py` num terminal serve para
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
python3 -m pip install -r requirements.txt

export ANTHROPIC_API_KEY="sua-chave"
python3 app.py
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
| `EPUB_DISCO_EFEMERO` | desligada | Numa hospedagem sem disco fixo; exige token e chave no ambiente |
| `PORT` | `5001` | Porta do servidor |

### Testes

```bash
cd epub_reader
python3 -m unittest test_leitor test_sync test_porta -v
```

44 testes cobrindo o parser, a API de leitura, a busca, o caminho da conversa
(com um cliente falso, sem gastar API), a fronteira anti-spoiler e as regras de
mescla da sincronização, e a porta de entrada (senha, freio, o que fica
aberto e o que não).

E cinco testes de navegador, todos precisando do Playwright:

| Teste | O que ele pega |
|---|---|
| `test_sincronia_navegador.py` | dois aparelhos sincronizando de verdade contra o servidor, um deles sem `crypto.subtle` |
| `test_disco_efemero.py` | o servidor perde o disco inteiro e os aparelhos o reconstroem |
| `test_como_artifact.py` | o leitor de pé nos dois ambientes: publicado e solto |
| `test_github.py` | a biblioteca no GitHub e a tela de conexão, contra uma API falsa |
| `test_conversa.py` | a conversa com a API da Anthropic — e a fronteira anti-spoiler agora que o recorte atravessa a rede |

O `test_github.py` monta um GitHub de mentira do tamanho exato do que o leitor
usa — e que **recusa** o `PATCH` da referência quando o ramo andou. É essa
recusa que prova o controle de concorrência: sem ela, dois aparelhos gravando
quase ao mesmo tempo perderiam o trabalho um do outro em silêncio. O mesmo teste
toca a tela de conexão como a pessoa toca, num aparelho de localStorage limpo:
repositório mal escrito, token em branco, token recusado, token expirado depois
de ligado, a URL colada da barra de endereço, o livro do outro aparelho descendo
sozinho, e o token lembrado depois de recarregar. Um botão desligado do seu
tratador passaria por qualquer teste da camada de baixo.

O último existe por um defeito que sobreviveu a várias rodadas: dentro do
artifact o `window.claude` existe, e o leitor trocava o conteúdo do painel de
sincronização por um aviso — destruindo um botão em que ele ligava um evento
logo abaixo. O `TypeError` interrompia a ligação de **todos** os eventos
seguintes, e a página inteira ficava inerte, em silêncio. Nenhum teste via
isso porque todos abriam o arquivo local, onde esse caminho não roda. O
ambiente em que um defeito mora precisa ser um ambiente testado.

Daí também duas defesas no próprio leitor: as ligações de evento passam por um
ajudante que tolera elemento ausente (um botão faltante não pode derrubar o
resto), e um ouvinte de erro num bloco de script anterior mostra na tela
qualquer falha de partida, inclusive de sintaxe. A versão aparece no rodapé da
estante, para não haver dúvida sobre qual código está rodando.



```bash
python3 -m pip install playwright && python3 -m playwright install chromium
python3 test_sincronia_navegador.py
python3 test_disco_efemero.py
python3 test_como_artifact.py
python3 test_github.py
python3 test_conversa.py
```

Tudo isso roda a cada empurrão, em
[`.github/workflows/testes.yml`](../.github/workflows/testes.yml).

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
├── segredos.py       # gera senha, token e chave para a nuvem
├── test_disco_efemero.py  # apaga o disco do servidor e vê os aparelhos o refazerem
├── test_como_artifact.py  # o leitor de pé publicado e solto
├── github-falso.js   # um GitHub de mentira, do tamanho do que o leitor usa
├── test_github.py    # a biblioteca no repositório e a tela de conexão
├── anthropic-falso.js # a API da Anthropic de mentira, com eventos em pedaços
├── test_conversa.py  # a conversa dentro do leitor, e o que não pode vazar
├── livro_de_capa.py  # gera um EPUB que começa pela capa, como os de editora
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

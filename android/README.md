# APK — Leitor sem spoiler

App Android que embrulha o leitor de `epub_reader/leitor-celular.html` e
acrescenta o que o navegador não deixa fazer: **conversar com o Claude dentro
do app**, com a sua chave da API guardada no aparelho.

Por que a casca resolve o que a página publicada não resolvia: numa página
hospedada, o CSP bloqueia qualquer requisição externa e uma chave de API não
deveria mesmo viver ali. No app, a chamada acontece em Java, a chave fica na
área privada do aplicativo e o JavaScript nunca precisa vê-la.

## Como pegar o APK

O APK é compilado pelo GitHub Actions a cada envio que toque em `android/` ou
no HTML do leitor. Para baixar:

1. Abra a aba **Actions** do repositório e escolha a execução mais recente de
   **APK do leitor**.
2. Baixe o artefato `leitor-sem-spoiler-apk` (um zip com `app-debug.apk`).
3. No Android, descompacte e toque no `.apk`. O sistema vai pedir para
   permitir a instalação de fontes desconhecidas para o app que está abrindo o
   arquivo — é o aviso normal de instalação fora da Play Store.

Também dá para disparar o build à mão: **Actions → APK do leitor → Run
workflow**.

## Compilar na sua máquina

Precisa do SDK do Android (o Android Studio já traz) e de um JDK 17:

```bash
cd android
./gradlew assembleDebug
# app/build/outputs/apk/debug/app-debug.apk
```

O HTML do leitor é copiado para `assets/` durante o build (tarefa
`copiarLeitor`), então existe uma cópia só do código — a mesma página serve à
web e ao app.

## Estrutura

```
android/
├── app/build.gradle                  # AGP 8.7, minSdk 26, uma dependência (androidx.webkit)
└── app/src/main/
    ├── AndroidManifest.xml           # só a permissão de INTERNET
    └── java/br/leitor/semspoiler/
        ├── MainActivity.java         # WebView, seletor de arquivo, botão voltar, cor da barra
        └── Ponte.java                # chamada à API em streaming + guarda da chave
```

### Decisões que valem explicação

**Os assets são servidos por `https://appassets.androidplatform.net`**
(`WebViewAssetLoader`), não por `file://`. Em `file://` o IndexedDB não
funciona, e a estante — que guarda o EPUB inteiro — deixaria de existir a cada
fechamento do app.

**A chamada à API é nativa.** A página monta o pedido (inclusive o recorte
anti-spoiler) e entrega à ponte; o Java acrescenta a chave, faz o POST em
`stream` e devolve os pedaços de texto por `window.__ponte`. Assim não há CORS
a contornar e a chave não transita pelo JavaScript.

**A chave fica em `SharedPreferences` privadas do app.** É o armazenamento
comum para isso e nenhum outro app a alcança em um Android sem root. Ainda
assim: é uma chave sua num aparelho seu — se o celular for comprometido ou
você extrair o backup, ela está lá. Para revogar, apague a chave no app
(🔑 → *Apagar a chave deste aparelho*) e gere outra no console da Anthropic.

**O APK é de depuração**, assinado com a chave de debug do Android. Serve para
uso pessoal e instala normalmente. Para distribuir, seria preciso assinar com
uma chave de release própria — o workflow não faz isso, e nem deveria fazer
sem uma chave que só você guarda.

## O que o app faz além da página

- Conversa com streaming, escolha de modelo (Opus 5, Sonnet 5, Haiku 4.5)
- Botão físico de voltar fecha painéis e volta à estante antes de sair
- Barra de status acompanha o papel escolhido (claro, sépia, noite, breu)
- Seletor de arquivos do sistema para escolher o EPUB

O resto — leitura, paginação, temas, sumário, destaques e a fronteira
anti-spoiler — é exatamente o mesmo código da página.

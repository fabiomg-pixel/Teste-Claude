#!/bin/bash
#
# Põe o leitor no ar no Mac e o mantém no ar.
#
# Instala as dependências num ambiente próprio e registra um LaunchAgent: o
# servidor sobe sozinho quando você faz login e volta sozinho se cair. Depois
# disso o iPhone só precisa do endereço e do token.
#
#   ./instalar-no-mac.sh              instala (ou atualiza) e liga
#   ./instalar-no-mac.sh --ensaio     mostra o que faria, sem tocar em nada
#   ./instalar-no-mac.sh --remover    desliga e apaga o LaunchAgent
#
# Seus livros e anotações ficam fora daqui, em ~/Library/Application Support,
# para que atualizar o código não encoste neles.

set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
ROTULO="br.leitor.semspoiler"
PLIST="$HOME/Library/LaunchAgents/$ROTULO.plist"
DADOS="$HOME/Library/Application Support/leitor-sem-spoiler"
REGISTRO="$HOME/Library/Logs/leitor-sem-spoiler.log"
VENV="$RAIZ/.venv"
PORTA="${PORT:-5001}"

ensaio=0
remover=0
for arg in "$@"; do
  case "$arg" in
    --ensaio)  ensaio=1 ;;
    --remover) remover=1 ;;
    -h|--help) sed -n '3,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Argumento desconhecido: $arg" >&2; exit 2 ;;
  esac
done

dizer() { printf '\033[1m%s\033[0m\n' "$*"; }
detalhe() { printf '   %s\n' "$*"; }

# --------------------------------------------------------------- remover

if [ "$remover" = 1 ]; then
  dizer "Desligando o leitor"
  launchctl bootout "gui/$(id -u)/$ROTULO" 2>/dev/null ||
    launchctl unload -w "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
  detalhe "LaunchAgent removido."
  detalhe "Seus livros continuam em: $DADOS"
  detalhe "Para apagá-los também:  rm -rf \"$DADOS\""
  exit 0
fi

# ------------------------------------------------------------- conferir

if [ "$(uname)" != "Darwin" ] && [ "$ensaio" = 0 ]; then
  echo "Este instalador é do macOS (usa launchd)." >&2
  echo "Em Linux, o equivalente é um serviço de usuário do systemd; no Windows," >&2
  echo "o Agendador de Tarefas. Para só experimentar: python app.py" >&2
  exit 1
fi

PY="$(command -v python3 || true)"
if [ -z "$PY" ]; then
  echo "Não achei o python3. Instale-o (o jeito mais curto é 'xcode-select --install')." >&2
  exit 1
fi

# ------------------------------------------------------ ambiente próprio

dizer "Preparando o ambiente"
detalhe "Python:   $PY ($("$PY" -V 2>&1))"
detalhe "Ambiente: $VENV"
detalhe "Dados:    $DADOS"
detalhe "Registro: $REGISTRO"

if [ "$ensaio" = 0 ]; then
  [ -x "$VENV/bin/python" ] || "$PY" -m venv "$VENV"
  "$VENV/bin/python" -m pip install --quiet --upgrade pip
  "$VENV/bin/python" -m pip install --quiet -r "$RAIZ/requirements.txt"
  mkdir -p "$DADOS" "$(dirname "$REGISTRO")" "$HOME/Library/LaunchAgents"
  detalhe "Dependências instaladas."
fi

# ------------------------------------------------------------- a chave

# A chave habilita a conversa integrada; sem ela o leitor funciona, só não
# conversa. Ela vai no plist, que é um arquivo seu e fica com modo 600.
CHAVE="${ANTHROPIC_API_KEY:-}"
if [ -z "$CHAVE" ] && [ -f "$PLIST" ]; then
  CHAVE="$(/usr/libexec/PlistBuddy -c 'Print :EnvironmentVariables:ANTHROPIC_API_KEY' \
           "$PLIST" 2>/dev/null || true)"   # mantém a que já estava
fi
if [ -z "$CHAVE" ] && [ "$ensaio" = 0 ] && [ -t 0 ]; then
  echo
  echo "Chave da API da Anthropic (Enter para pular — dá para pôr depois):"
  read -r -s CHAVE || true
  echo
fi

escapar_xml() {
  printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'
}

# ---------------------------------------------------------- o LaunchAgent

# KeepAlive mantém o servidor de pé (se ele cair, o launchd o levanta);
# RunAtLoad faz subir no login. Sem isso seria preciso lembrar de iniciá-lo
# toda vez — e o iPhone não perdoa: ele só pede sincronia quando você abre o
# leitor, e se não achar o servidor, não sincroniza.
plist_do_leitor() {
  cat <<XML
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$ROTULO</string>
  <key>ProgramArguments</key>
  <array>
    <string>$(escapar_xml "$VENV/bin/python")</string>
    <string>$(escapar_xml "$RAIZ/app.py")</string>
  </array>
  <key>WorkingDirectory</key><string>$(escapar_xml "$RAIZ")</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PORT</key><string>$PORTA</string>
    <key>EPUB_DATA_DIR</key><string>$(escapar_xml "$DADOS")</string>
    <key>ANTHROPIC_API_KEY</key><string>$(escapar_xml "$CHAVE")</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$(escapar_xml "$REGISTRO")</string>
  <key>StandardErrorPath</key><string>$(escapar_xml "$REGISTRO")</string>
</dict>
</plist>
XML
}

if [ "$ensaio" = 1 ]; then
  dizer "Ensaio — o plist que eu escreveria em $PLIST:"
  plist_do_leitor
  exit 0
fi

dizer "Registrando o serviço"
plist_do_leitor > "$PLIST"
chmod 600 "$PLIST"          # a chave mora aqui dentro

launchctl bootout "gui/$(id -u)/$ROTULO" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null ||
  launchctl load -w "$PLIST"
detalhe "Serviço no ar (sobe sozinho no login, e volta sozinho se cair)."

# ------------------------------------------------------------- conferir

dizer "Conferindo"
pronto=0
for _ in $(seq 1 30); do
  if curl -fsS -m 2 "http://127.0.0.1:$PORTA/celular" -o /dev/null 2>/dev/null; then
    pronto=1; break
  fi
  sleep 1
done

if [ "$pronto" = 0 ]; then
  echo "O servidor não respondeu em 30 segundos. O registro costuma dizer por quê:" >&2
  echo "   tail -n 40 \"$REGISTRO\"" >&2
  exit 1
fi

# O servidor já criou o token ao subir; isto só o lê (de dentro de $RAIZ,
# senão o 'import sync' não acha o módulo).
TOKEN="$(cd "$RAIZ" && EPUB_DATA_DIR="$DADOS" "$VENV/bin/python" \
         -c 'import sync; print(sync.token())')"
IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo '')"
TS="$(tailscale ip -4 2>/dev/null | head -1 || true)"

echo
dizer "Pronto."
detalhe "Neste Mac:            http://localhost:$PORTA/"
[ -n "$IP" ] && detalhe "Na sua rede de casa:  http://$IP:$PORTA/celular"
[ -n "$TS" ] && detalhe "Pelo Tailscale:       http://$TS:$PORTA/celular"
[ -z "$TS" ] && detalhe "Fora de casa:         instale o Tailscale nos dois aparelhos"
detalhe "Token de sincronização: $TOKEN"
echo
detalhe "No iPhone: abra o endereço /celular no Safari, toque em Compartilhar →"
detalhe "Adicionar à Tela de Início, e na estante ligue «Sincronizar entre"
detalhe "aparelhos» com o endereço e o token acima."
echo
detalhe "Um Mac dormindo não serve ninguém: em Ajustes → Bateria/Energia,"
detalhe "deixe «Impedir que o Mac durma automaticamente» ligado na tomada."

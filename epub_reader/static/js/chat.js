/* Conversa com o companheiro de leitura (streaming via SSE). */

window.Chat = (function () {
  const BOOK = window.BOOK_ID;
  const $ = (id) => document.getElementById(id);

  const log = $('chat-log');
  const form = $('chat-form');
  const input = $('chat-input');
  const selectionBox = $('chat-selection');
  const selectionText = $('chat-selection-text');

  let selection = '';
  let busy = false;

  function escapeHtml(text) {
    return String(text == null ? '' : text).replace(/[&<>"']/g, (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  /* Markdown mínimo: o suficiente para respostas de chat. */
  function markdown(src) {
    const lines = escapeHtml(src).split('\n');
    const out = [];
    let list = null;
    const inline = (text) => text
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/(^|[\s(])\*([^*\n]+)\*/g, '$1<em>$2</em>')
      .replace(/(^|[\s(])_([^_\n]+)_/g, '$1<em>$2</em>');

    const closeList = () => { if (list) { out.push('</' + list + '>'); list = null; } };

    lines.forEach((raw) => {
      const line = raw.trimEnd();
      if (!line.trim()) { closeList(); return; }
      const heading = line.match(/^(#{1,4})\s+(.*)$/);
      const bullet = line.match(/^\s*[-*•]\s+(.*)$/);
      const numbered = line.match(/^\s*\d+[.)]\s+(.*)$/);
      const quote = line.match(/^>\s?(.*)$/);
      if (heading) {
        closeList();
        out.push('<p><strong>' + inline(heading[2]) + '</strong></p>');
      } else if (bullet) {
        if (list !== 'ul') { closeList(); out.push('<ul>'); list = 'ul'; }
        out.push('<li>' + inline(bullet[1]) + '</li>');
      } else if (numbered) {
        if (list !== 'ol') { closeList(); out.push('<ol>'); list = 'ol'; }
        out.push('<li>' + inline(numbered[1]) + '</li>');
      } else if (quote) {
        closeList();
        out.push('<blockquote>' + inline(quote[1]) + '</blockquote>');
      } else {
        closeList();
        out.push('<p>' + inline(line) + '</p>');
      }
    });
    closeList();
    return out.join('');
  }

  function scrollDown() {
    log.scrollTop = log.scrollHeight;
  }

  function addUser(text, mode) {
    const el = document.createElement('div');
    el.className = 'msg user';
    const label = mode && mode !== 'perguntar' ? `<span class="badge">${mode}</span>` : '';
    el.innerHTML = label + escapeHtml(text).replace(/\n/g, '<br>');
    log.appendChild(el);
    scrollDown();
    return el;
  }

  function addAssistant(html) {
    const el = document.createElement('div');
    el.className = 'msg assistant';
    el.innerHTML = html || '';
    log.appendChild(el);
    scrollDown();
    return el;
  }

  function renderSources(el, sources) {
    if (!sources || !sources.length) return;
    const box = document.createElement('div');
    box.className = 'sources';
    sources.forEach((src) => {
      const chip = document.createElement('button');
      chip.className = 'source-chip';
      chip.textContent = 'cap. ' + (src.chapter + 1)
        + (src.chapter_title ? ' · ' + src.chapter_title.slice(0, 28) : '');
      chip.title = src.excerpt || '';
      chip.addEventListener('click', () => Reader.goToBlock(src.block, true));
      box.appendChild(chip);
    });
    el.appendChild(box);
  }

  async function loadHistory() {
    const res = await fetch('/api/books/' + BOOK + '/chat');
    const data = await res.json();
    log.innerHTML = '';
    if (!data.messages.length) {
      addAssistant('<p class="muted">Estou lendo junto com você e só conheço o livro '
        + 'até onde você chegou. Pergunte sobre o enredo, os personagens, um trecho '
        + 'que você destacou, ou sobre os conceitos e fatos que aparecem no texto. '
        + 'Se a pergunta for sobre o que vem depois, eu não respondo — de propósito.</p>');
      return;
    }
    data.messages.forEach((msg) => {
      if (msg.role === 'user') addUser(msg.content, msg.mode);
      else {
        const el = addAssistant(markdown(msg.content));
        renderSources(el, msg.sources);
      }
    });
    scrollDown();
  }

  async function send(payload) {
    if (busy) { toast('Espere a resposta anterior terminar.'); return; }
    busy = true;
    $('chat-send').disabled = true;

    const bubble = addAssistant('<span class="status-line">pensando…</span>');
    let text = '';
    let sources = [];

    try {
      const res = await fetch('/api/books/' + BOOK + '/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        let message = 'Erro ' + res.status;
        try { message = (await res.json()).error || message; } catch (e) { /* sem JSON */ }
        bubble.innerHTML = '<span class="status-line">⚠ ' + escapeHtml(message) + '</span>';
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split('\n\n');
        buffer = chunks.pop();
        for (const chunk of chunks) {
          const line = chunk.split('\n').find((l) => l.startsWith('data: '));
          if (!line) continue;
          let event;
          try { event = JSON.parse(line.slice(6)); } catch (e) { continue; }
          if (event.type === 'status') {
            if (!text) {
              bubble.innerHTML = event.message
                ? '<span class="status-line">' + escapeHtml(event.message) + '</span>'
                : '<span class="status-line">pensando…</span>';
            }
          } else if (event.type === 'sources') {
            sources = event.sources || [];
          } else if (event.type === 'delta') {
            text += event.text;
            bubble.innerHTML = markdown(text);
            bubble.classList.add('cursor');
            scrollDown();
          } else if (event.type === 'position') {
            updatePosition(event.position);
          } else if (event.type === 'error') {
            bubble.innerHTML = markdown(text) +
              '<span class="status-line">⚠ ' + escapeHtml(event.message) + '</span>';
          }
        }
      }
      bubble.classList.remove('cursor');
      if (text) {
        bubble.innerHTML = markdown(text);
        renderSources(bubble, sources);
      }
    } catch (err) {
      bubble.innerHTML = '<span class="status-line">⚠ ' + escapeHtml(err.message) + '</span>';
    } finally {
      busy = false;
      $('chat-send').disabled = false;
      scrollDown();
    }
  }

  function currentPayload(mode) {
    return {
      question: input.value.trim(),
      selection,
      mode: mode || 'perguntar',
      strict: $('chat-strict').checked,
      boundary: Reader.boundary,
    };
  }

  function updatePosition(position) {
    if (!position) return;
    $('chat-position').textContent =
      `Sei do livro até «${position.chapter_title}» (${position.book_percent}% lido).`;
  }

  function setSelection(text) {
    selection = text;
    selectionText.textContent = '“' + text.slice(0, 120) + (text.length > 120 ? '…' : '') + '”';
    selectionBox.classList.remove('hidden');
    input.focus();
  }

  function clearSelection() {
    selection = '';
    selectionBox.classList.add('hidden');
  }

  function init() {
    loadHistory();

    form.addEventListener('submit', (ev) => {
      ev.preventDefault();
      const question = input.value.trim();
      if (!question && !selection) { input.focus(); return; }
      const mode = selection && !question ? 'explicar' : 'perguntar';
      addUser(question || '(explicar o trecho selecionado)', mode);
      const payload = currentPayload(mode);
      input.value = '';
      input.style.height = 'auto';
      clearSelection();
      send(payload);
    });

    input.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter' && !ev.shiftKey) { ev.preventDefault(); form.requestSubmit(); }
    });
    input.addEventListener('input', () => {
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 128) + 'px';
    });

    document.querySelectorAll('#modes .chip').forEach((chip) => {
      chip.addEventListener('click', () => {
        const mode = chip.dataset.mode;
        addUser(chip.textContent, mode);
        const payload = currentPayload(mode);
        input.value = '';
        clearSelection();
        send(payload);
      });
    });

    $('chat-selection-clear').addEventListener('click', clearSelection);

    $('chat-clear').addEventListener('click', async () => {
      if (!confirm('Apagar toda a conversa deste livro?')) return;
      await fetch('/api/books/' + BOOK + '/chat', { method: 'DELETE' });
      loadHistory();
    });

    Reader.on('progress', () => {
      clearTimeout(window._posTimer);
      window._posTimer = setTimeout(async () => {
        try {
          const res = await fetch('/api/books/' + BOOK + '/memory');
          const data = await res.json();
          updatePosition(data.position);
          if (!data.llm) {
            $('chat-position').textContent =
              'Configure ANTHROPIC_API_KEY para conversar sobre o livro.';
          } else if (data.pending > 0) {
            $('chat-position').textContent +=
              ` (${data.pending} capítulo(s) a reler quando você perguntar)`;
          }
        } catch (e) { /* status é secundário */ }
      }, 2000);
    });
  }

  return { init, setSelection, send };
})();

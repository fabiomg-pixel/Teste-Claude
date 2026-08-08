/* Leitor: paginação em colunas, tipografia, destaques, marcadores e navegação. */

window.Reader = (function () {
  const BOOK = window.BOOK_ID;
  const $ = (id) => document.getElementById(id);

  const viewport = $('viewport');
  const pages = $('pages');
  const stage = $('stage');

  const DEFAULTS = {
    theme: 'claro', size: 20, leading: 1.62, measure: 34,
    font: 'serif', align: 'justify', layout: 'paginado',
  };

  const state = {
    book: null,
    chapters: [],
    toc: [],
    chapter: null,
    page: 0,
    pageCount: 1,
    block: 0,
    furthest: 0,
    bookmarks: [],
    highlights: [],
    settings: Object.assign({}, DEFAULTS),
    wpm: 230,
    lastSaveAt: Date.now(),
    lastSavedBlock: 0,
    listeners: {},
  };

  // ------------------------------------------------------------ utilidades

  function on(event, fn) {
    (state.listeners[event] = state.listeners[event] || []).push(fn);
  }

  function emit(event, payload) {
    (state.listeners[event] || []).forEach((fn) => fn(payload));
  }

  async function api(path, options) {
    const res = await fetch('/api/books/' + BOOK + path, options);
    if (!res.ok) {
      let message = 'Erro ' + res.status;
      try { message = (await res.json()).error || message; } catch (e) { /* sem corpo JSON */ }
      throw new Error(message);
    }
    return res.status === 204 ? null : res.json();
  }

  function json(method, body) {
    return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
  }

  function chapterOfBlock(block) {
    for (const ch of state.chapters) {
      if (block >= ch.first_block && block <= Math.max(ch.last_block, ch.first_block)) return ch;
    }
    return state.chapters[state.chapters.length - 1] || null;
  }

  function escapeHtml(text) {
    return String(text == null ? '' : text).replace(/[&<>"']/g, (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  // ------------------------------------------------------------- aparência

  function loadSettings() {
    try {
      Object.assign(state.settings, JSON.parse(localStorage.getItem('leitor.config') || '{}'));
    } catch (e) { /* configuração corrompida: usa os padrões */ }
    const theme = localStorage.getItem('leitor.tema');
    if (theme) state.settings.theme = theme;
  }

  function saveSettings() {
    localStorage.setItem('leitor.config', JSON.stringify(state.settings));
    localStorage.setItem('leitor.tema', state.settings.theme);
  }

  function applySettings() {
    const s = state.settings;
    document.documentElement.dataset.theme = s.theme;
    const root = document.documentElement.style;
    root.setProperty('--reading-size', s.size + 'px');
    root.setProperty('--reading-leading', s.leading);
    root.setProperty('--measure', s.measure + 'rem');
    root.setProperty('--align', s.align);
    root.setProperty('--reading-font',
      s.font === 'sans' ? 'var(--sans)' : s.font === 'mono' ? 'var(--mono)' : 'var(--serif)');
    document.body.classList.toggle('scroll-mode', s.layout === 'rolagem');

    $('size-label').textContent = s.size;
    $('leading-label').textContent = s.leading.toFixed(2).replace('.', ',');
    $('measure-label').textContent = s.measure;
    $('set-size').value = s.size;
    $('set-leading').value = s.leading;
    $('set-measure').value = s.measure;
    document.querySelectorAll('[data-theme-value]').forEach((b) =>
      b.setAttribute('aria-pressed', String(b.dataset.themeValue === s.theme)));
    document.querySelectorAll('[data-font]').forEach((b) =>
      b.setAttribute('aria-pressed', String(b.dataset.font === s.font)));
    document.querySelectorAll('[data-align]').forEach((b) =>
      b.setAttribute('aria-pressed', String(b.dataset.align === s.align)));
    document.querySelectorAll('[data-layout]').forEach((b) =>
      b.setAttribute('aria-pressed', String(b.dataset.layout === s.layout)));
    saveSettings();
  }

  // -------------------------------------------------------------- paginação

  function gapPx() {
    return parseFloat(getComputedStyle(document.documentElement)
      .getPropertyValue('--col-gap')) || 48;
  }

  function relayout(keepBlock) {
    if (state.settings.layout === 'rolagem') {
      viewport.style.left = viewport.style.right = '';
      pages.style.width = '';
      pages.style.columnWidth = '';
      pages.style.transform = '';
      state.pageCount = 1;
      if (keepBlock != null) scrollToBlock(keepBlock);
      updateStatus();
      return;
    }
    const gap = gapPx();
    const avail = stage.clientWidth;
    const cols = state.settings.layout === 'duplo' && avail > 860 ? 2 : 1;
    const measurePx = state.settings.measure * 16;
    const minPad = Math.max(24, Math.min(80, avail * 0.06));
    const desired = Math.min(avail - 2 * minPad, cols * measurePx + (cols - 1) * gap);
    const padX = Math.max(minPad, (avail - desired) / 2);
    viewport.style.left = viewport.style.right = padX + 'px';

    const width = Math.max(200, avail - 2 * padX);
    pages.style.width = width + 'px';
    pages.style.columnWidth = ((width - gap * (cols - 1)) / cols) + 'px';

    // força o recálculo antes de medir
    const total = pages.scrollWidth;
    state.pageCount = Math.max(1, Math.round((total + gap) / (width + gap)));
    if (keepBlock != null) {
      setPage(pageOfBlock(keepBlock), true);
    } else {
      setPage(Math.min(state.page, state.pageCount - 1), true);
    }
  }

  function pageWidth() {
    return pages.clientWidth + gapPx();
  }

  function pageOfBlock(block) {
    const el = pages.querySelector('[data-b="' + block + '"]');
    if (!el) return 0;
    const x = el.getBoundingClientRect().left - pages.getBoundingClientRect().left;
    return Math.max(0, Math.min(state.pageCount - 1, Math.floor(x / pageWidth() + 0.002)));
  }

  function setPage(page, silent) {
    state.page = Math.max(0, Math.min(page, state.pageCount - 1));
    pages.style.transform = 'translateX(' + (-state.page * pageWidth()) + 'px)';
    if (!silent) hideSelectionPopup();
    updateCurrentBlock();
    updateStatus();
  }

  function scrollToBlock(block) {
    const el = pages.querySelector('[data-b="' + block + '"]');
    if (el) el.scrollIntoView({ block: 'start', behavior: 'auto' });
    updateCurrentBlock();
  }

  function visibleBlockElements() {
    const rect = viewport.getBoundingClientRect();
    const out = [];
    pages.querySelectorAll('[data-b]').forEach((el) => {
      const r = el.getBoundingClientRect();
      const insideX = r.right > rect.left + 2 && r.left < rect.right - 2;
      const insideY = r.bottom > rect.top + 2 && r.top < rect.bottom - 2;
      if (insideX && insideY) out.push(el);
    });
    return out;
  }

  function updateCurrentBlock() {
    const visible = visibleBlockElements();
    if (!visible.length) return;
    const block = parseInt(visible[0].dataset.b, 10);
    if (Number.isNaN(block)) return;
    state.block = block;
    if (block > state.furthest) state.furthest = block;
    scheduleSave();
    emit('progress', { block: state.block, furthest: state.furthest });
  }

  // --------------------------------------------------------------- capítulo

  async function openChapter(index, opts) {
    opts = opts || {};
    if (index < 0 || index >= state.chapters.length) return;
    const data = await api('/chapters/' + index);
    state.chapter = data;
    document.body.classList.add('no-anim');
    pages.innerHTML = data.html;
    pages.scrollTop = 0;
    applyHighlights();
    bindContentLinks();

    // aguarda layout de imagens para paginar corretamente
    await new Promise((resolve) => requestAnimationFrame(() => resolve()));
    relayout(null);

    if (opts.anchor) {
      const target = pages.querySelector('#' + CSS.escape(opts.anchor));
      if (target) {
        if (state.settings.layout === 'rolagem') target.scrollIntoView();
        else {
          const x = target.getBoundingClientRect().left - pages.getBoundingClientRect().left;
          setPage(Math.floor(x / pageWidth() + 0.002), true);
        }
      }
    } else if (opts.block != null) {
      if (state.settings.layout === 'rolagem') scrollToBlock(opts.block);
      else setPage(pageOfBlock(opts.block), true);
    } else if (opts.last) {
      setPage(state.pageCount - 1, true);
    } else {
      setPage(0, true);
    }

    if (opts.flash != null) {
      const el = pages.querySelector('[data-b="' + opts.flash + '"]');
      if (el) { el.classList.add('flash'); setTimeout(() => el.classList.remove('flash'), 1500); }
    }

    setTimeout(() => document.body.classList.remove('no-anim'), 50);
    updateCurrentBlock();
    updateStatus();
    renderToc();
  }

  function nextPage() {
    if (state.settings.layout === 'rolagem') {
      viewport.scrollBy({ top: viewport.clientHeight * 0.9, behavior: 'smooth' });
      setTimeout(updateCurrentBlock, 400);
      return;
    }
    if (state.page < state.pageCount - 1) setPage(state.page + 1);
    else if (state.chapter && state.chapter.index < state.chapters.length - 1) {
      openChapter(state.chapter.index + 1);
    }
  }

  function prevPage() {
    if (state.settings.layout === 'rolagem') {
      viewport.scrollBy({ top: -viewport.clientHeight * 0.9, behavior: 'smooth' });
      setTimeout(updateCurrentBlock, 400);
      return;
    }
    if (state.page > 0) setPage(state.page - 1);
    else if (state.chapter && state.chapter.index > 0) {
      openChapter(state.chapter.index - 1, { last: true });
    }
  }

  function goToBlock(block, flash) {
    const chapter = chapterOfBlock(block);
    if (!chapter) return;
    if (state.chapter && state.chapter.index === chapter.index) {
      if (state.settings.layout === 'rolagem') scrollToBlock(block);
      else setPage(pageOfBlock(block));
      if (flash) {
        const el = pages.querySelector('[data-b="' + block + '"]');
        if (el) { el.classList.add('flash'); setTimeout(() => el.classList.remove('flash'), 1500); }
      }
      updateCurrentBlock();
    } else {
      openChapter(chapter.index, { block, flash: flash ? block : null });
    }
  }

  function bindContentLinks() {
    pages.querySelectorAll('a.epub-link').forEach((a) => {
      a.addEventListener('click', (ev) => {
        ev.preventDefault();
        const chapter = a.dataset.chapter != null ? parseInt(a.dataset.chapter, 10) : null;
        const anchor = a.dataset.anchor || null;
        if (chapter != null && (!state.chapter || chapter !== state.chapter.index)) {
          openChapter(chapter, { anchor });
        } else if (anchor) {
          const target = pages.querySelector('#' + CSS.escape(anchor));
          if (target) {
            if (state.settings.layout === 'rolagem') target.scrollIntoView({ behavior: 'smooth' });
            else {
              const x = target.getBoundingClientRect().left - pages.getBoundingClientRect().left;
              setPage(Math.floor(x / pageWidth() + 0.002));
            }
          }
        }
      });
    });
  }

  // ----------------------------------------------------------- status/rodapé

  function remainingWords() {
    if (!state.chapter) return 0;
    let words = 0;
    for (const ch of state.chapters) {
      if (ch.index > state.chapter.index) words += ch.words;
    }
    const span = Math.max(state.chapter.last_block - state.chapter.first_block, 1);
    const done = (state.block - state.chapter.first_block) / span;
    words += state.chapter.words * Math.max(0, 1 - done);
    return words;
  }

  function updateStatus() {
    const total = Math.max(state.book ? state.book.total_blocks : 1, 1);
    const pct = Math.min(100, (state.block + 1) / total * 100);
    $('status-pct').textContent = pct.toFixed(1).replace('.', ',') + '%';
    $('scrubber-read').style.width = pct + '%';
    $('scrubber-knob').style.left = pct + '%';
    $('status-page').textContent = state.settings.layout === 'rolagem'
      ? '' : 'pág. ' + (state.page + 1) + '/' + state.pageCount;
    const minutes = Math.round(remainingWords() / state.wpm);
    $('status-left').textContent = minutes > 90
      ? Math.round(minutes / 60) + ' h restantes'
      : minutes + ' min restantes';
    if (state.chapter) {
      $('status-chapter').textContent = state.chapter.title;
      $('top-chapter').textContent = state.chapter.title;
    }
    const bookmarked = state.bookmarks.some((b) => Math.abs(b.block - state.block) < 2);
    $('btn-bookmark').setAttribute('aria-pressed', String(bookmarked));
  }

  // --------------------------------------------------------------- progresso

  let saveTimer = null;

  function scheduleSave() {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(saveProgress, 1200);
  }

  async function saveProgress() {
    const now = Date.now();
    const seconds = Math.min(Math.round((now - state.lastSaveAt) / 1000), 180);
    const chapter = state.chapter;
    let words = 0;
    if (chapter && state.block > state.lastSavedBlock) {
      const span = Math.max(chapter.last_block - chapter.first_block + 1, 1);
      words = Math.round((state.block - state.lastSavedBlock) * (chapter.words / span));
    }
    state.lastSaveAt = now;
    state.lastSavedBlock = state.block;
    try {
      const data = await api('/progress', json('POST', { block: state.block, seconds, words }));
      state.furthest = Math.max(state.furthest, data.progress.furthest_block);
      if (data.progress.seconds_read > 600 && data.progress.words_read > 500) {
        const wpm = data.progress.words_read / (data.progress.seconds_read / 60);
        if (wpm > 80 && wpm < 700) state.wpm = Math.round(wpm);
      }
      emit('progress', { block: state.block, furthest: state.furthest });
    } catch (e) { /* offline: tenta de novo na próxima virada de página */ }
  }

  // ------------------------------------------------------------- destaques

  function normalizeForMatch(text) {
    return text.replace(/\s+/g, ' ');
  }

  function textNodesIn(root) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    const out = [];
    let node;
    while ((node = walker.nextNode())) out.push(node);
    return out;
  }

  function markText(blockEl, needle, attrs) {
    const nodes = textNodesIn(blockEl);
    let flat = '';
    const map = [];  // índice no texto achatado -> [nó, posição]
    nodes.forEach((node) => {
      const raw = node.nodeValue;
      for (let i = 0; i < raw.length; i += 1) {
        const ch = raw[i];
        if (/\s/.test(ch)) {
          if (flat.endsWith(' ')) continue;
          flat += ' ';
        } else {
          flat += ch;
        }
        map.push([node, i]);
      }
    });
    const target = normalizeForMatch(needle).trim();
    const start = flat.indexOf(target);
    if (start < 0 || !target) return false;
    const end = start + target.length - 1;

    const ranges = new Map();
    for (let i = start; i <= end && i < map.length; i += 1) {
      const [node, offset] = map[i];
      const current = ranges.get(node);
      if (!current) ranges.set(node, [offset, offset + 1]);
      else current[1] = offset + 1;
    }
    ranges.forEach((range, node) => {
      let piece = node;
      if (range[0] > 0) piece = piece.splitText(range[0]);
      if (range[1] - range[0] < piece.nodeValue.length) piece.splitText(range[1] - range[0]);
      const mark = document.createElement('mark');
      mark.className = 'hl' + (attrs.note ? ' has-note' : '');
      mark.dataset.color = attrs.color || 'amarelo';
      mark.dataset.hl = attrs.id;
      if (attrs.note) mark.title = attrs.note;
      piece.parentNode.replaceChild(mark, piece);
      mark.appendChild(piece);
    });
    return true;
  }

  function applyHighlights() {
    if (!state.chapter) return;
    state.highlights
      .filter((h) => h.chapter === state.chapter.index)
      .forEach((h) => {
        const el = pages.querySelector('[data-b="' + h.block + '"]');
        if (el) markText(el, h.text, h);
      });
  }

  async function createHighlight(color) {
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed) return null;
    const text = selection.toString().trim();
    const anchorEl = selection.anchorNode && (selection.anchorNode.nodeType === 1
      ? selection.anchorNode : selection.anchorNode.parentElement);
    const blockEl = anchorEl && anchorEl.closest('[data-b]');
    if (!blockEl || !text) return null;
    const block = parseInt(blockEl.dataset.b, 10);
    try {
      const item = await api('/highlights', json('POST', {
        block, chapter: state.chapter.index, text, color: color || 'amarelo',
      }));
      state.highlights.push(item);
      markText(blockEl, text, item);
      renderHighlights();
      selection.removeAllRanges();
      hideSelectionPopup();
      return item;
    } catch (err) {
      toast(err.message);
      return null;
    }
  }

  async function removeHighlight(id) {
    await api('/highlights/' + id, { method: 'DELETE' });
    state.highlights = state.highlights.filter((h) => h.id !== id);
    pages.querySelectorAll('mark[data-hl="' + id + '"]').forEach((mark) => {
      const parent = mark.parentNode;
      while (mark.firstChild) parent.insertBefore(mark.firstChild, mark);
      parent.removeChild(mark);
      parent.normalize();
    });
    renderHighlights();
  }

  // ------------------------------------------------------------- marcadores

  async function toggleBookmark() {
    const existing = state.bookmarks.find((b) => Math.abs(b.block - state.block) < 2);
    if (existing) {
      await api('/bookmarks/' + existing.id, { method: 'DELETE' });
      state.bookmarks = state.bookmarks.filter((b) => b.id !== existing.id);
      toast('Marcador removido');
    } else {
      const el = pages.querySelector('[data-b="' + state.block + '"]');
      const label = el ? el.textContent.trim().slice(0, 90) : '';
      const item = await api('/bookmarks', json('POST', {
        block: state.block, chapter: state.chapter ? state.chapter.index : 0, label,
      }));
      state.bookmarks.push(item);
      toast('Página marcada');
    }
    state.bookmarks.sort((a, b) => a.block - b.block);
    renderBookmarks();
    updateStatus();
  }

  // ---------------------------------------------------------------- painéis

  function openPanel(which) {
    const left = $('panel-left');
    const chat = $('panel-chat');
    if (which === 'chat') {
      chat.classList.add('open');
      document.body.classList.add('chat-open');
      chat.setAttribute('aria-hidden', 'false');
    } else if (which) {
      left.classList.add('open');
      document.body.classList.add('left-open');
      left.setAttribute('aria-hidden', 'false');
      selectTab(which);
    }
    setTimeout(() => relayout(state.block), 260);
  }

  function closePanel(which) {
    if (!which || which === 'left') {
      $('panel-left').classList.remove('open');
      $('panel-left').setAttribute('aria-hidden', 'true');
      document.body.classList.remove('left-open');
    }
    if (!which || which === 'chat') {
      $('panel-chat').classList.remove('open');
      $('panel-chat').setAttribute('aria-hidden', 'true');
      document.body.classList.remove('chat-open');
    }
    setTimeout(() => relayout(state.block), 260);
  }

  function selectTab(name) {
    const titles = { toc: 'Sumário', bookmarks: 'Marcadores', highlights: 'Destaques', search: 'Busca' };
    $('left-title').textContent = titles[name] || 'Sumário';
    document.querySelectorAll('.tab').forEach((tab) =>
      tab.setAttribute('aria-selected', String(tab.dataset.tab === name)));
    ['toc', 'bookmarks', 'highlights', 'search'].forEach((key) => {
      const el = $('tab-' + key);
      const active = key === name;
      el.classList.toggle('hidden', !active);
      if (key === 'search') el.style.display = active ? 'flex' : 'none';
    });
    if (name === 'search') setTimeout(() => $('search-input').focus(), 60);
  }

  function renderToc() {
    const host = $('tab-toc');
    host.innerHTML = '';
    const entries = [];
    (function walk(items, depth) {
      items.forEach((item) => {
        entries.push({ item, depth });
        if (item.children) walk(item.children, depth + 1);
      });
    })(state.toc, 0);

    const list = entries.length ? entries : state.chapters.map((ch) => ({
      item: { title: ch.title, chapter: ch.index, anchor: null }, depth: 0,
    }));

    list.forEach(({ item, depth }) => {
      const btn = document.createElement('button');
      btn.className = 'toc-item depth-' + Math.min(depth, 2);
      btn.textContent = item.title;
      if (state.chapter && item.chapter === state.chapter.index) btn.classList.add('current');
      btn.addEventListener('click', () => {
        if (item.chapter == null) return;
        openChapter(item.chapter, { anchor: item.anchor });
        if (window.innerWidth < 900) closePanel('left');
      });
      host.appendChild(btn);
    });
  }

  function renderBookmarks() {
    const host = $('tab-bookmarks');
    host.innerHTML = '';
    if (!state.bookmarks.length) {
      host.innerHTML = '<p class="muted" style="padding:.8rem;font-size:.85rem">'
        + 'Nenhum marcador. Use o 🔖 na barra de cima (ou a tecla <b>b</b>).</p>';
      return;
    }
    state.bookmarks.forEach((item) => {
      const chapter = chapterOfBlock(item.block);
      const el = document.createElement('div');
      el.className = 'list-item';
      el.innerHTML = `<button class="del" title="Remover">✕</button>
        <div>${escapeHtml(item.label || '(sem texto)')}</div>
        <div class="meta"><span>${escapeHtml(chapter ? chapter.title : '')}</span></div>`;
      el.addEventListener('click', () => goToBlock(item.block, true));
      el.querySelector('.del').addEventListener('click', async (ev) => {
        ev.stopPropagation();
        await api('/bookmarks/' + item.id, { method: 'DELETE' });
        state.bookmarks = state.bookmarks.filter((b) => b.id !== item.id);
        renderBookmarks();
        updateStatus();
      });
      host.appendChild(el);
    });
  }

  function renderHighlights() {
    const host = $('tab-highlights');
    host.innerHTML = '';
    if (!state.highlights.length) {
      host.innerHTML = '<p class="muted" style="padding:.8rem;font-size:.85rem">'
        + 'Selecione um trecho no texto para destacar ou anotar.</p>';
      return;
    }
    state.highlights.slice().sort((a, b) => a.block - b.block).forEach((item) => {
      const chapter = chapterOfBlock(item.block);
      const el = document.createElement('div');
      el.className = 'list-item';
      el.innerHTML = `<button class="del" title="Remover">✕</button>
        <div class="quote" style="border-color:var(--hl-${item.color})">${escapeHtml(item.text)}</div>
        ${item.note ? `<div class="note">${escapeHtml(item.note)}</div>` : ''}
        <div class="meta"><span>${escapeHtml(chapter ? chapter.title : '')}</span>
        <button class="btn-ghost" data-note="${item.id}" style="font-size:.75rem">nota</button></div>`;
      el.addEventListener('click', () => goToBlock(item.block, true));
      el.querySelector('.del').addEventListener('click', async (ev) => {
        ev.stopPropagation();
        await removeHighlight(item.id);
      });
      el.querySelector('[data-note]').addEventListener('click', async (ev) => {
        ev.stopPropagation();
        const note = prompt('Nota para este trecho:', item.note || '');
        if (note === null) return;
        await api('/highlights/' + item.id, json('PATCH', { note }));
        item.note = note;
        renderHighlights();
      });
      host.appendChild(el);
    });
  }

  async function runSearch() {
    const query = $('search-input').value.trim();
    const scope = document.querySelector('input[name="scope"]:checked').value;
    const host = $('search-results');
    if (!query) { host.innerHTML = ''; return; }
    host.innerHTML = '<p class="muted" style="padding:.8rem;font-size:.85rem">Buscando…</p>';
    const data = await api('/search?q=' + encodeURIComponent(query) + '&scope=' + scope);
    host.innerHTML = '';
    if (!data.results.length) {
      host.innerHTML = '<p class="muted" style="padding:.8rem;font-size:.85rem">Nada encontrado'
        + (scope === 'read' ? ' no que você já leu.' : '.') + '</p>';
      return;
    }
    data.results.forEach((item) => {
      const el = document.createElement('div');
      el.className = 'list-item';
      el.innerHTML = `<div>${escapeHtml(item.excerpt)}</div>
        <div class="meta"><span>${escapeHtml(item.chapter_title || '')}</span></div>`;
      el.addEventListener('click', () => goToBlock(item.block, true));
      host.appendChild(el);
    });
  }

  // -------------------------------------------------------- popup de seleção

  function hideSelectionPopup() {
    $('selpop').classList.remove('show');
  }

  function showSelectionPopup() {
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed || !selection.toString().trim()) {
      hideSelectionPopup();
      return;
    }
    const range = selection.getRangeAt(0);
    if (!pages.contains(range.commonAncestorContainer)) { hideSelectionPopup(); return; }
    const rect = range.getBoundingClientRect();
    const pop = $('selpop');
    const stageRect = stage.getBoundingClientRect();
    pop.classList.add('show');
    const left = rect.left - stageRect.left + rect.width / 2 - pop.offsetWidth / 2;
    const top = rect.top - stageRect.top - pop.offsetHeight - 10;
    pop.style.left = Math.max(8, Math.min(left, stageRect.width - pop.offsetWidth - 8)) + 'px';
    pop.style.top = (top < 8 ? rect.bottom - stageRect.top + 10 : top) + 'px';
  }

  // ------------------------------------------------------------------ eventos

  function bindUi() {
    $('next').addEventListener('click', nextPage);
    $('prev').addEventListener('click', prevPage);
    $('btn-toc').addEventListener('click', () => {
      document.body.classList.contains('left-open') ? closePanel('left') : openPanel('toc');
    });
    $('btn-search').addEventListener('click', () => openPanel('search'));
    $('btn-chat').addEventListener('click', () => {
      document.body.classList.contains('chat-open') ? closePanel('chat') : openPanel('chat');
    });
    $('btn-bookmark').addEventListener('click', toggleBookmark);
    $('left-close').addEventListener('click', () => closePanel('left'));
    $('chat-close').addEventListener('click', () => closePanel('chat'));
    document.querySelectorAll('.tab').forEach((tab) =>
      tab.addEventListener('click', () => selectTab(tab.dataset.tab)));
    $('search-go').addEventListener('click', runSearch);
    $('search-input').addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter') { ev.preventDefault(); runSearch(); }
    });
    document.querySelectorAll('input[name="scope"]').forEach((radio) =>
      radio.addEventListener('change', runSearch));

    // ajustes de aparência
    $('btn-aa').addEventListener('click', (ev) => {
      ev.stopPropagation();
      $('settings').classList.toggle('hidden');
    });
    document.addEventListener('click', (ev) => {
      if (!$('settings').contains(ev.target) && ev.target !== $('btn-aa')) {
        $('settings').classList.add('hidden');
      }
    });
    $('settings').addEventListener('click', (ev) => ev.stopPropagation());
    document.querySelectorAll('[data-theme-value]').forEach((btn) =>
      btn.addEventListener('click', () => {
        state.settings.theme = btn.dataset.themeValue;
        applySettings();
      }));
    document.querySelectorAll('[data-font]').forEach((btn) =>
      btn.addEventListener('click', () => {
        state.settings.font = btn.dataset.font;
        applySettings(); relayout(state.block);
      }));
    document.querySelectorAll('[data-align]').forEach((btn) =>
      btn.addEventListener('click', () => {
        state.settings.align = btn.dataset.align;
        applySettings(); relayout(state.block);
      }));
    document.querySelectorAll('[data-layout]').forEach((btn) =>
      btn.addEventListener('click', () => {
        state.settings.layout = btn.dataset.layout;
        applySettings(); relayout(state.block);
      }));
    $('set-size').addEventListener('input', (ev) => {
      state.settings.size = parseInt(ev.target.value, 10);
      applySettings(); relayout(state.block);
    });
    $('set-leading').addEventListener('input', (ev) => {
      state.settings.leading = parseFloat(ev.target.value);
      applySettings(); relayout(state.block);
    });
    $('set-measure').addEventListener('input', (ev) => {
      state.settings.measure = parseInt(ev.target.value, 10);
      applySettings(); relayout(state.block);
    });

    // seleção de texto
    pages.addEventListener('mouseup', () => setTimeout(showSelectionPopup, 10));
    pages.addEventListener('touchend', () => setTimeout(showSelectionPopup, 60));
    document.addEventListener('selectionchange', () => {
      const selection = window.getSelection();
      if (!selection || selection.isCollapsed) hideSelectionPopup();
    });
    document.querySelectorAll('#selpop .dot').forEach((dot) =>
      dot.addEventListener('mousedown', (ev) => {
        ev.preventDefault();
        createHighlight(dot.dataset.color);
      }));
    $('sel-note').addEventListener('mousedown', async (ev) => {
      ev.preventDefault();
      const item = await createHighlight('amarelo');
      if (!item) return;
      const note = prompt('Sua nota sobre este trecho:', '');
      if (note) {
        await api('/highlights/' + item.id, json('PATCH', { note }));
        item.note = note;
        pages.querySelectorAll('mark[data-hl="' + item.id + '"]').forEach((m) => {
          m.classList.add('has-note'); m.title = note;
        });
        renderHighlights();
      }
    });
    $('sel-ask').addEventListener('mousedown', (ev) => {
      ev.preventDefault();
      const text = window.getSelection().toString().trim();
      if (!text) return;
      hideSelectionPopup();
      openPanel('chat');
      if (window.Chat) Chat.setSelection(text);
    });
    $('sel-copy').addEventListener('mousedown', (ev) => {
      ev.preventDefault();
      const text = window.getSelection().toString();
      navigator.clipboard.writeText(text).then(() => toast('Trecho copiado'));
      hideSelectionPopup();
    });
    pages.addEventListener('click', (ev) => {
      const mark = ev.target.closest && ev.target.closest('mark[data-hl]');
      if (!mark) return;
      const item = state.highlights.find((h) => h.id === mark.dataset.hl);
      if (!item) return;
      openPanel('highlights');
    });

    // barra de progresso arrastável
    let dragging = false;
    const scrub = (ev) => {
      const rect = $('scrubber').getBoundingClientRect();
      const ratio = Math.max(0, Math.min(1, (ev.clientX - rect.left) / rect.width));
      const total = state.book ? state.book.total_blocks : 1;
      goToBlock(Math.min(total - 1, Math.round(ratio * total)));
    };
    $('scrubber').addEventListener('mousedown', (ev) => { dragging = true; scrub(ev); });
    window.addEventListener('mousemove', (ev) => { if (dragging) scrub(ev); });
    window.addEventListener('mouseup', () => { dragging = false; });

    // rolagem (modo rolagem)
    viewport.addEventListener('scroll', () => {
      if (state.settings.layout !== 'rolagem') return;
      clearTimeout(viewport._t);
      viewport._t = setTimeout(updateCurrentBlock, 150);
    });

    window.addEventListener('resize', () => {
      clearTimeout(window._resize);
      window._resize = setTimeout(() => relayout(state.block), 180);
    });

    document.addEventListener('keydown', (ev) => {
      const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(ev.target.tagName);
      if (typing) {
        if (ev.key === 'Escape') ev.target.blur();
        return;
      }
      switch (ev.key) {
        case 'ArrowRight': case 'PageDown': ev.preventDefault(); nextPage(); break;
        case ' ': ev.preventDefault(); ev.shiftKey ? prevPage() : nextPage(); break;
        case 'ArrowLeft': case 'PageUp': ev.preventDefault(); prevPage(); break;
        case 'Home': openChapter(0); break;
        case 'End': openChapter(state.chapters.length - 1, { last: true }); break;
        case 's': openPanel('toc'); break;
        case 'c': openPanel('chat'); break;
        case 'b': toggleBookmark(); break;
        case 'a': $('settings').classList.toggle('hidden'); break;
        case 'f': document.body.classList.toggle('immersive'); break;
        case '/': ev.preventDefault(); openPanel('search'); break;
        case 'Escape':
          $('settings').classList.add('hidden');
          closePanel();
          document.body.classList.remove('immersive');
          break;
        default: break;
      }
    });

    document.addEventListener('visibilitychange', () => {
      if (document.hidden) saveProgress();
      else state.lastSaveAt = Date.now();
    });
    window.addEventListener('beforeunload', () => {
      navigator.sendBeacon('/api/books/' + BOOK + '/progress',
        new Blob([JSON.stringify({ block: state.block, seconds: 0 })],
          { type: 'application/json' }));
    });
  }

  // ------------------------------------------------------------------- init

  async function init() {
    loadSettings();
    applySettings();
    bindUi();
    try {
      const data = await api('');
      state.book = data;
      state.chapters = data.chapters;
      state.toc = data.toc || [];
      state.bookmarks = data.bookmarks || [];
      state.highlights = data.highlights || [];
      state.block = data.progress.cur_block || 0;
      state.furthest = Math.max(data.progress.furthest_block || 0, state.block);
      state.lastSavedBlock = state.block;
      $('top-title').textContent = data.title;
      renderBookmarks();
      renderHighlights();
      const chapter = chapterOfBlock(state.block) || state.chapters[0];
      await openChapter(chapter.index, { block: state.block });
      renderToc();
      emit('ready', state);
      emit('progress', { block: state.block, furthest: state.furthest });
    } catch (err) {
      toast('Não consegui abrir o livro: ' + err.message);
    }
  }

  return {
    init, on, state, goToBlock, openPanel, closePanel, openChapter,
    get boundary() { return Math.max(state.furthest, state.block); },
    api, json,
  };
})();

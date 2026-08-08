/* Biblioteca: listagem, upload (clique ou arrastar) e remoção. */

(function () {
  const grid = document.getElementById('grid');
  const empty = document.getElementById('empty');
  const drop = document.getElementById('drop');
  const input = document.getElementById('file');
  const bar = document.getElementById('upload-bar');
  const warn = document.getElementById('llm-warn');

  function escapeHtml(text) {
    return String(text || '').replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function card(book) {
    const el = document.createElement('div');
    el.className = 'card';
    const cover = book.has_cover
      ? `<img src="/api/books/${book.id}/cover" alt="">`
      : `<div class="fallback">${escapeHtml(book.title)}</div>`;
    el.innerHTML = `
      <a href="/livro/${book.id}">
        <div class="cover">${cover}</div>
        <h3>${escapeHtml(book.title)}</h3>
        <div class="author">${escapeHtml(book.author || '—')}</div>
        <div class="bar"><span style="width:${book.percent}%"></span></div>
        <div class="pct">${book.percent > 0 ? book.percent + '% lido' : 'não iniciado'}</div>
      </a>
      <button class="remove" title="Remover da biblioteca">✕</button>`;
    el.querySelector('.remove').addEventListener('click', async function (ev) {
      ev.preventDefault();
      if (!confirm(`Remover “${book.title}” e todas as anotações?`)) return;
      await fetch('/api/books/' + book.id, { method: 'DELETE' });
      load();
    });
    return el;
  }

  async function load() {
    const res = await fetch('/api/books');
    const data = await res.json();
    grid.innerHTML = '';
    data.books.forEach(function (b) { grid.appendChild(card(b)); });
    empty.classList.toggle('hidden', data.books.length > 0);
    warn.classList.toggle('hidden', !!data.llm);
  }

  function upload(files) {
    const list = Array.from(files).filter(f => f.name.toLowerCase().endsWith('.epub'));
    if (!list.length) { toast('Envie arquivos .epub'); return; }
    bar.classList.remove('hidden');
    let done = 0;

    (function next() {
      if (!list.length) {
        bar.classList.add('hidden');
        bar.style.width = '0%';
        load();
        return;
      }
      const file = list.shift();
      const form = new FormData();
      form.append('file', file);
      const xhr = new XMLHttpRequest();
      xhr.open('POST', '/api/books');
      xhr.upload.onprogress = function (ev) {
        if (ev.lengthComputable) {
          const pct = ((done + ev.loaded / ev.total) / (done + list.length + 1)) * 100;
          bar.style.width = pct.toFixed(0) + '%';
        }
      };
      xhr.onload = function () {
        done += 1;
        let body = {};
        try { body = JSON.parse(xhr.responseText); } catch (e) { /* resposta não-JSON */ }
        if (xhr.status >= 400) toast(body.error || 'Falha ao importar ' + file.name);
        else toast('“' + (body.title || file.name) + '” adicionado');
        next();
      };
      xhr.onerror = function () { toast('Falha de rede ao enviar ' + file.name); next(); };
      xhr.send(form);
    })();
  }

  document.getElementById('pick').addEventListener('click', () => input.click());
  drop.addEventListener('click', () => input.click());
  input.addEventListener('change', () => { upload(input.files); input.value = ''; });

  ['dragenter', 'dragover'].forEach(function (ev) {
    drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.add('drag'); });
  });
  ['dragleave', 'drop'].forEach(function (ev) {
    drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.remove('drag'); });
  });
  drop.addEventListener('drop', function (e) { upload(e.dataTransfer.files); });

  load();
})();

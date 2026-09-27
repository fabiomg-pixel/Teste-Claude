/* Um GitHub de mentira, do tamanho exato do que o leitor usa.
   Guarda blobs por sha, uma árvore por commit, e recusa o PATCH da ref
   quando o pai não é mais a cabeça — que é a corrida que precisa ser testada. */
window.__GH = (function () {
  const blobs = new Map();          // sha -> Uint8Array
  const commits = new Map();        // sha -> {tree, parents}
  const arvores = new Map();        // sha -> Map(caminho -> shaBlob)
  let cabeca = null;
  let n = 0;
  const novoSha = (p) => p + (++n).toString(16).padStart(38, '0');
  const chamadas = [];

  function arvoreDe(shaCommit) {
    if (!shaCommit) return new Map();
    return new Map(arvores.get(commits.get(shaCommit).tree));
  }

  // começa com um README, como um repositório criado com "Add a README"
  (function inicial() {
    const sha = novoSha('b');
    blobs.set(sha, new TextEncoder().encode('# biblioteca\n'));
    const t = novoSha('t');
    arvores.set(t, new Map([['README.md', sha]]));
    const c = novoSha('c');
    commits.set(c, { tree: t, parents: [] });
    cabeca = c;
  })();

  function json(corpo, status) {
    return new Response(JSON.stringify(corpo), {
      status: status || 200, headers: { 'Content-Type': 'application/json' } });
  }

  window.fetch = async function (url, opcoes) {
    opcoes = opcoes || {};
    const u = String(url);
    chamadas.push((opcoes.method || 'GET') + ' ' + u.replace('https://api.github.com', ''));
    const corpo = opcoes.body ? JSON.parse(opcoes.body) : null;
    const aceita = (opcoes.headers || {})['Accept'] || '';

    if (!/^https:\/\/api\.github\.com/.test(u)) {
      return new Response('não deveria sair daqui: ' + u, { status: 599 });
    }
    if (!/Bearer ficha-valida/.test((opcoes.headers || {})['Authorization'] || '')) {
      return json({ message: 'Bad credentials' }, 401);
    }

    let m;
    if ((m = u.match(/\/repos\/([^/]+)\/([^/?]+)$/))) {
      if (m[2] !== 'biblioteca') return json({ message: 'Not Found' }, 404);
      return json({ default_branch: 'main', private: true, permissions: { push: true } });
    }
    if ((m = u.match(/\/git\/trees\/([0-9a-z]+)\?/))) {
      const arv = new Map(arvores.get(m[1]) || []);
      const tree = [...arv.entries()].map(([caminho, sha]) => ({
        path: caminho, type: 'blob', sha, size: (blobs.get(sha) || []).length }));
      return json({ tree });
    }
    if ((m = u.match(/\/git\/blobs\/([0-9a-f]+)$/)) && (opcoes.method || 'GET') === 'GET') {
      const b = blobs.get(m[1]);
      if (!b) return json({ message: 'Not Found' }, 404);
      if (/raw/.test(aceita)) return new Response(b);
      return json({ content: btoa(String.fromCharCode(...b)), encoding: 'base64' });
    }
    if (u.endsWith('/git/blobs') && opcoes.method === 'POST') {
      const sha = novoSha('b');
      const bytes = corpo.encoding === 'base64'
        ? Uint8Array.from(atob(corpo.content), (c) => c.charCodeAt(0))
        : new TextEncoder().encode(corpo.content);
      blobs.set(sha, bytes);
      return json({ sha });
    }
    if (u.includes('/git/ref/heads/main')) {
      return json({ object: { sha: cabeca } });
    }
    if ((m = u.match(/\/git\/commits\/([0-9a-f]+)$/)) && (opcoes.method || 'GET') === 'GET') {
      const c = commits.get(m[1]);
      return c ? json({ tree: { sha: c.tree } }) : json({ message: 'Not Found' }, 404);
    }
    if (u.endsWith('/git/trees') && opcoes.method === 'POST') {
      const base = new Map(arvores.get(corpo.base_tree));
      corpo.tree.forEach((e) => { e.sha === null ? base.delete(e.path) : base.set(e.path, e.sha); });
      const sha = novoSha('t');
      arvores.set(sha, base);
      return json({ sha });
    }
    if (u.endsWith('/git/commits') && opcoes.method === 'POST') {
      const sha = novoSha('c');
      commits.set(sha, { tree: corpo.tree, parents: corpo.parents });
      return json({ sha });
    }
    if (u.includes('/git/refs/heads/main') && opcoes.method === 'PATCH') {
      const c = commits.get(corpo.sha);
      if (!corpo.force && c.parents[0] !== cabeca) {
        return json({ message: 'Update is not a fast forward' }, 422);   // outro gravou
      }
      cabeca = corpo.sha;
      return json({ ref: 'refs/heads/main' });
    }
    return json({ message: 'rota não implementada no falso: ' + u }, 500);
  };

  return {
    chamadas,
    arquivos: () => [...arvoreDe(cabeca).keys()].sort(),
    ler: (caminho) => {
      const sha = arvoreDe(cabeca).get(caminho);
      return sha ? new TextDecoder().decode(blobs.get(sha)) : null;
    },
    tamanho: (caminho) => {
      const sha = arvoreDe(cabeca).get(caminho);
      return sha ? blobs.get(sha).length : 0;
    },
    /* Simula outro aparelho gravando entre a nossa leitura e a nossa escrita. */
    gravarPorFora: (caminho, texto) => {
      const sha = novoSha('b');
      blobs.set(sha, new TextEncoder().encode(texto));
      const base = arvoreDe(cabeca);
      base.set(caminho, sha);
      const t = novoSha('t');
      arvores.set(t, base);
      const c = novoSha('c');
      commits.set(c, { tree: t, parents: [cabeca] });
      cabeca = c;
    },
  };
})();

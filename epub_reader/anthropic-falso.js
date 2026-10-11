/* Uma API da Anthropic de mentira, do tamanho do que o leitor usa.

   Serve a três coisas que só se testam com a rede no meio:
   guarda o pedido inteiro (é nele que se confere a fronteira anti-spoiler),
   devolve os eventos em pedaços cortados de propósito no meio do JSON, e
   sabe recusar como a de verdade recusa — 401, 400, refusal, teto de tokens. */
window.__API = (function () {
  const pedidos = [];
  let roteiro = 'normal';

  const EVENTOS = {
    normal: [
      { type: 'message_start', message: { id: 'msg_1', type: 'message' } },
      { type: 'content_block_start', index: 0, content_block: { type: 'thinking', thinking: '' } },
      { type: 'content_block_delta', index: 0, delta: { type: 'thinking_delta', thinking: 'Vendo o que já foi lido…' } },
      { type: 'content_block_stop', index: 0 },
      { type: 'content_block_start', index: 1, content_block: { type: 'text', text: '' } },
      { type: 'content_block_delta', index: 1, delta: { type: 'text_delta', text: 'Helena está em ' } },
      { type: 'content_block_delta', index: 1, delta: { type: 'text_delta', text: 'Ostende, e o aviso do pai ' } },
      { type: 'content_block_delta', index: 1, delta: { type: 'text_delta', text: 'continua sem explicação.' } },
      { type: 'content_block_stop', index: 1 },
      { type: 'message_delta', delta: { stop_reason: 'end_turn' }, usage: { output_tokens: 20 } },
      { type: 'message_stop' },
    ],
    recusa: [
      { type: 'message_start', message: { id: 'msg_2', type: 'message' } },
      { type: 'message_delta', delta: { stop_reason: 'refusal' }, usage: { output_tokens: 0 } },
      { type: 'message_stop' },
    ],
    cortada: [
      { type: 'content_block_start', index: 0, content_block: { type: 'text', text: '' } },
      { type: 'content_block_delta', index: 0, delta: { type: 'text_delta', text: 'Começo a responder e' } },
      { type: 'message_delta', delta: { stop_reason: 'max_tokens' }, usage: { output_tokens: 4096 } },
      { type: 'message_stop' },
    ],
  };

  /* Pedaços que não respeitam fronteira de evento: é assim que a rede entrega,
     e emendar às cegas quebra justamente nas respostas longas. */
  function emPedacos(eventos) {
    const inteiro = eventos.map((e) => 'event: ' + e.type + '\ndata: ' + JSON.stringify(e) + '\n\n').join('');
    const pedacos = [];
    for (let i = 0; i < inteiro.length; i += 37) pedacos.push(inteiro.slice(i, i + 37));
    return new ReadableStream({
      start(c) {
        pedacos.forEach((p) => c.enqueue(new TextEncoder().encode(p)));
        c.close();
      },
    });
  }

  /* ---------------------------------------------- páginas de uma edição

     A listagem devolve JSON embrulhado numa frase e numa cerca de código, e a
     transcrição devolve Markdown com preâmbulo: é o que um modelo às vezes faz,
     e o leitor tem de aguentar. O uso informa cache lido quando o PDF é o mesmo
     da chamada anterior, com o mesmo system, modelo e esforço — a regra da API,
     que é o que o teste quer ver o leitor respeitar. */
  let leituraAnterior = null;
  const leituras = [];

  function lerPaginas(corpo) {
    const conteudo = corpo.messages[0].content;
    const midia = conteudo.filter((b) => b.type === 'document' || b.type === 'image');
    const pedido = conteudo.filter((b) => b.type === 'text').map((b) => b.text).join('\n');
    const paginas = ((pedido.match(/páginas ([\d, ]+) da edição/) || [])[1] || '')
      .split(',').map((x) => Number(x.trim())).filter(Boolean);
    const assinatura = JSON.stringify([corpo.model, corpo.system,
      (corpo.output_config || {}).effort, midia.map((m) => m.source.data)]);
    const doCache = assinatura === leituraAnterior;
    leituraAnterior = assinatura;

    const listar = /Liste as matérias/.test(pedido);
    leituras.push({ passo: listar ? 'listar' : 'transcrever', paginas, doCache,
                    midia: midia.map((m) => m.type), modelo: corpo.model });

    let texto;
    if (listar) {
      const materias = [{ titulo: 'O porto que mudou a cidade', resumo: 'Reportagem sobre o porto.',
                          paginas: paginas.filter((n) => n === 2 || n === 4), tipo: 'reportagem' }];
      if (paginas.includes(3)) {
        materias.push({ titulo: 'Esportes: time vence clássico', resumo: 'Nota de esportes.',
                        paginas: [3, 99], tipo: 'nota' });   // 99 não foi enviada: o leitor tem de descartar
      }
      texto = 'Encontrei estas matérias:\n```json\n' + JSON.stringify({ materias }) + '\n```';
    } else {
      const titulo = (pedido.match(/Transcreva a matéria «([^»]+)»/) || [])[1] || 'Sem título';
      texto = 'Aqui está a transcrição:\n```markdown\n# ' + titulo + '\n\nPor Ana Lima\n\n'
        + 'O porto abriu em 1990 e hoje movimenta 3 milhões de toneladas.\n\n'
        + 'Moradores contam que o bairro mudou de cara em duas décadas.\n\n'
        + '## O futuro do cais\n\nA prefeitura estuda ampliar o cais até 2030.\n\n'
        + '> Box: o porto em números\n\nLegenda: navios atracados no cais norte\n```';
    }
    return json({
      id: 'msg_p', type: 'message', role: 'assistant', model: corpo.model,
      content: [{ type: 'text', text: texto }], stop_reason: 'end_turn',
      usage: doCache
        ? { input_tokens: 300, cache_read_input_tokens: 8000, output_tokens: 700 }
        : { input_tokens: 300, cache_creation_input_tokens: 8000, output_tokens: 700 },
    }, 200);
  }

  /* ------------------------------------------------------ busca na web

     Os eventos seguem a documentação: o pedido de busca chega em pedaços de
     JSON, o resultado chega inteiro com conteúdo cifrado, e a citação chega
     num citations_delta. No roteiro «buscaPausada» o primeiro turno para em
     pause_turn logo depois do resultado; o segundo só é respondido se o turno
     pausado voltar intacto — consulta montada e conteúdo cifrado incluídos. */
  const FONTE = { url: 'https://exemplo.com.br/porto', title: 'O porto, segundo o Exemplo' };

  function buscar(corpo) {
    const ultimo = corpo.messages[corpo.messages.length - 1];
    const retomando = ultimo.role === 'assistant';
    if (retomando) {
      const blocos = Array.isArray(ultimo.content) ? ultimo.content : [];
      const busca = blocos.find((b) => b.type === 'server_tool_use');
      const res = blocos.find((b) => b.type === 'web_search_tool_result');
      const intacto = busca && busca.input && busca.input.query === 'porto cidade cobertura'
        && !('__json' in busca)
        && res && Array.isArray(res.content) && res.content[0].encrypted_content === 'ENC1';
      buscas.push({ retomada: true, intacto: !!intacto });
      if (!intacto) {
        return json({ error: { message: 'messages: invalid continuation of a paused turn' } }, 400);
      }
    } else {
      buscas.push({ retomada: false, ferramentas: corpo.tools });
    }

    const ev = [{ type: 'message_start', message: { id: 'msg_b', type: 'message',
                                                    usage: { input_tokens: 900 } } }];
    if (!retomando) {
      ev.push(
        { type: 'content_block_start', index: 0, content_block: { type: 'text', text: '' } },
        { type: 'content_block_delta', index: 0, delta: { type: 'text_delta', text: 'Vou comparar. ' } },
        { type: 'content_block_stop', index: 0 },
        { type: 'content_block_start', index: 1,
          content_block: { type: 'server_tool_use', id: 'srvtoolu_1', name: 'web_search', input: {} } },
        { type: 'content_block_delta', index: 1,
          delta: { type: 'input_json_delta', partial_json: '{"query":"porto ci' } },
        { type: 'content_block_delta', index: 1,
          delta: { type: 'input_json_delta', partial_json: 'dade cobertura"}' } },
        { type: 'content_block_stop', index: 1 },
        { type: 'content_block_start', index: 2, content_block: {
          type: 'web_search_tool_result', tool_use_id: 'srvtoolu_1',
          content: [{ type: 'web_search_result', url: FONTE.url, title: FONTE.title,
                      encrypted_content: 'ENC1', page_age: '3 de outubro de 2026' }] } },
        { type: 'content_block_stop', index: 2 });
      if (roteiro === 'buscaPausada') {
        ev.push({ type: 'message_delta', delta: { stop_reason: 'pause_turn' },
                  usage: { output_tokens: 40, server_tool_use: { web_search_requests: 1 } } },
                { type: 'message_stop' });
        return new Response(emPedacos(ev), { status: 200, headers: { 'Content-Type': 'text/event-stream' } });
      }
    }
    const i = retomando ? 0 : 3;
    ev.push(
      { type: 'content_block_start', index: i, content_block: { type: 'text', text: '' } },
      { type: 'content_block_delta', index: i, delta: { type: 'citations_delta', citation: {
        type: 'web_search_result_location', url: FONTE.url, title: FONTE.title,
        encrypted_index: 'IDX1', cited_text: 'o porto abriu em 1990' } } },
      // uma «fonte» maliciosa: não pode virar link
      { type: 'content_block_delta', index: i, delta: { type: 'citations_delta', citation: {
        type: 'web_search_result_location', url: 'javascript:alert(1)', title: 'armadilha',
        encrypted_index: 'IDX2', cited_text: 'x' } } },
      { type: 'content_block_delta', index: i,
        delta: { type: 'text_delta', text: 'O Exemplo também diz que o porto abriu em 1990.' } },
      { type: 'content_block_stop', index: i },
      { type: 'message_delta', delta: { stop_reason: 'end_turn' },
        usage: { output_tokens: 120, server_tool_use: { web_search_requests: retomando ? 0 : 1 } } },
      { type: 'message_stop' });
    return new Response(emPedacos(ev), { status: 200, headers: { 'Content-Type': 'text/event-stream' } });
  }
  const buscas = [];

  const json = (corpo, status) => new Response(JSON.stringify(corpo),
    { status, headers: { 'Content-Type': 'application/json' } });

  const original = window.fetch;

  window.fetch = async function (url, opcoes) {
    const u = String(url);
    if (!/^https:\/\/api\.anthropic\.com/.test(u)) return original.call(window, url, opcoes);

    opcoes = opcoes || {};
    const cabecalhos = opcoes.headers || {};
    const corpo = JSON.parse(opcoes.body);
    pedidos.push({ cabecalhos, corpo });

    // sem o cabeçalho de acesso direto, a API de verdade recusa e é isso que importa
    if (cabecalhos['anthropic-dangerous-direct-browser-access'] !== 'true') {
      return json({ error: { message: 'CORS: direct browser access not enabled' } }, 403);
    }
    if (!/^sk-ant-/.test(cabecalhos['x-api-key'] || '')) {
      return json({ error: { type: 'authentication_error', message: 'invalid x-api-key' } }, 401);
    }
    if (roteiro === 'semCredito') {
      return json({ error: { message: 'Your credit balance is too low' } }, 400);
    }
    if (roteiro === 'semOpus55' && corpo.model === 'claude-opus-5-5') {
      // uma conta que ainda não tem o modelo novo
      return json({ error: { type: 'not_found_error',
                             message: 'model: claude-opus-5-5' } }, 404);
    }
    if (roteiro === 'semPensar' && corpo.thinking) {
      // um modelo que não aceita o pedido completo: o leitor tem de descer
      return json({ error: { message: 'thinking: unsupported for this model' } }, 400);
    }
    if (roteiro === 'sobrecarga') {
      return json({ error: { message: 'Overloaded' } }, 529);
    }
    if (roteiro === 'redeFora') throw new TypeError('Load failed');

    /* Pedido de ida e volta, sem stream: é o caminho dos resumos de capítulo.
       Devolve uma marca rastreável com o começo do que recebeu, para o teste
       poder conferir QUAL capítulo foi resumido. */
    if (!corpo.stream && Array.isArray(corpo.messages[0].content)) {
      return lerPaginas(corpo);
    }
    if (!corpo.stream) {
      if (roteiro === 'resumoRuim') return json({ error: { message: 'Overloaded' } }, 529);
      const recebido = String(corpo.messages[0].content);
      return json({
        id: 'msg_r', type: 'message', role: 'assistant', model: corpo.model,
        content: [{ type: 'text', text: 'RESUMO[' + recebido.slice(0, 70).replace(/\n/g, ' ') + ']' }],
        stop_reason: 'end_turn',
        usage: { input_tokens: 1200, output_tokens: 90 },
      });
    }

    if ((corpo.tools || []).some((t) => t.name === 'web_search')) return buscar(corpo);

    const eventos = EVENTOS[roteiro === 'semPensar' ? 'normal' : roteiro] || EVENTOS.normal;
    return new Response(emPedacos(eventos),
      { status: 200, headers: { 'Content-Type': 'text/event-stream' } });
  };

  return {
    pedidos,
    ultimo: () => pedidos[pedidos.length - 1],
    limpar: () => { pedidos.length = 0; },
    roteiro: (r) => { roteiro = r; },
    leituras,
    buscas,
  };
})();

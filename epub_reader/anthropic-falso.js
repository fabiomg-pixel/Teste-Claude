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

    const eventos = EVENTOS[roteiro === 'semPensar' ? 'normal' : roteiro] || EVENTOS.normal;
    return new Response(emPedacos(eventos),
      { status: 200, headers: { 'Content-Type': 'text/event-stream' } });
  };

  return {
    pedidos,
    ultimo: () => pedidos[pedidos.length - 1],
    limpar: () => { pedidos.length = 0; },
    roteiro: (r) => { roteiro = r; },
  };
})();

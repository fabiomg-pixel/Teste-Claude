"""Integração com a LLM (Claude) com garantia estrutural anti-spoiler.

A ideia central: o modelo nunca recebe uma única palavra do livro depois da
fronteira de leitura. O contexto é montado a partir de três fontes, todas
recortadas em ``boundary`` (índice do último bloco lido):

1. **Memória** – resumos por capítulo, gerados incrementalmente e guardados
   em cache. O capítulo em que o leitor está é resumido apenas até o bloco
   atual (resumo parcial).
2. **Trechos recuperados** – BM25 sobre os blocos já lidos, para a pergunta
   feita.
3. **Contexto recente** – os últimos blocos lidos, na íntegra, para que a
   conversa acompanhe "onde estamos agora".

O prompt reforça a regra no plano do comportamento (o modelo pode conhecer a
obra pelo treinamento), mas a barreira que realmente vale é a do recorte.
"""

from __future__ import annotations

import os
import threading

import retrieval
import store

MODEL = os.environ.get("EPUB_LLM_MODEL", "claude-opus-5")
SUMMARY_MODEL = os.environ.get("EPUB_SUMMARY_MODEL", MODEL)
CHAT_EFFORT = os.environ.get("EPUB_LLM_EFFORT", "medium")

MAX_SUMMARY_CHARS = 50_000     # tamanho máximo de um trecho por chamada
MAX_RECENT_CHARS = 6_000       # contexto recente enviado na íntegra
MAX_PASSAGE_CHARS = 900        # corte por trecho recuperado
TOP_PASSAGES = 8

_client = None
_client_lock = threading.Lock()

MODES = {
    "perguntar": "",
    "recapitular": (
        "Tarefa: recapitule a leitura até o ponto atual. Organize em: (1) onde "
        "estamos agora — cena, lugar, momento; (2) o que aconteceu de mais "
        "importante, em ordem; (3) fios narrativos ainda em aberto; (4) o que "
        "vale ter em mente ao retomar. Seja específico com nomes e fatos."
    ),
    "personagens": (
        "Tarefa: apresente quem já apareceu no livro até aqui — quem é cada "
        "um, o que fez, como se relaciona com os demais e qual é a situação "
        "atual de cada um. Não inclua ninguém que ainda não tenha aparecido."
    ),
    "refletir": (
        "Tarefa: proponha uma reflexão sobre o que já foi lido. Comece com um "
        "parágrafo curto apontando uma tensão, ambiguidade ou escolha "
        "interessante do texto até aqui; depois faça de 3 a 5 perguntas "
        "abertas para o leitor pensar. As perguntas devem se sustentar apenas "
        "no que já foi lido."
    ),
    "contexto": (
        "Tarefa: explique o pano de fundo — conceitos, fatos históricos, "
        "referências culturais, científicas ou literárias — que aparece no "
        "que já foi lido e ajuda a entender melhor o texto. Deixe explícito o "
        "que vem do livro e o que é conhecimento externo."
    ),
    "explicar": (
        "Tarefa: explique o trecho selecionado pelo leitor: o que está "
        "acontecendo, o que significa, por que importa dado o que já se leu, e "
        "qualquer termo, alusão ou referência que valha esclarecer."
    ),
}

SYSTEM_RULES = """\
Você é um companheiro de leitura embutido em um leitor de e-books. O leitor \
está no meio de um livro e conversa com você sobre o que já leu.

## Fronteira anti-spoiler (regra absoluta)
- O contexto que você recebe contém APENAS material anterior ao ponto de \
leitura. Não existe, para esta conversa, nada além dele.
- Mesmo que você reconheça a obra e conheça o resto pelo seu treinamento, é \
proibido revelar, insinuar, antecipar ou dar pistas sobre qualquer coisa que \
aconteça depois do ponto de leitura: reviravoltas, destinos de personagens, \
revelações, o final, ou o sentido retroativo de algo que ainda parece banal.
- Não diga que um detalhe "vai fazer sentido depois", que "isso muda mais à \
frente" nem coisa semelhante: isso já é spoiler estrutural. Se a pergunta \
puxar para o futuro do enredo, diga em uma frase que não vai adiantar nada e \
ofereça algo melhor — hipóteses a partir do que já foi lido (marcadas como \
especulação) ou um aprofundamento do que já aconteceu.
- Se algo não estiver no contexto, diga que não encontrou no que foi lido. \
Nunca preencha a lacuna com conhecimento externo sobre esta obra.

## Conhecimento externo
- Para conceitos, história, ciência, mitologia, língua, contexto cultural e \
referências em geral, use seu conhecimento livremente — é justamente para \
isso que o leitor tem você ao lado.
- O que é vedado é conhecimento externo *sobre este livro*: enredo posterior, \
biografia dos personagens além do lido, leitura crítica que pressupõe a obra \
inteira, comparações que entreguem para onde a história vai.
- Marque a fronteira: "no que você leu…" para o texto, "fora do livro…" para \
contexto externo.

## Como responder
- Responda no idioma do leitor (português do Brasil, salvo se ele escrever em \
outro idioma).
- Vá direto ao ponto: sem preâmbulo, sem repetir a pergunta, sem encerrar \
oferecendo mais ajuda. De um a quatro parágrafos, ou uma lista curta quando \
couber. Prosa comum, sem enfeite.
- Cite a origem quando ajudar a ancorar ("no cap. 4", "no trecho da carta").
- Especulação é bem-vinda quando pedida — desde que rotulada como tal e \
construída só com o que já foi lido.
"""

STRICT_RULES = """\

## Modo estrito ativado
Responda usando exclusivamente os trechos e resumos fornecidos. Não recorra a \
conhecimento externo, nem sobre a obra nem sobre os assuntos que ela toca. Se \
o material não bastar, diga isso.
"""


class AssistantError(Exception):
    pass


def get_client():
    global _client
    with _client_lock:
        if _client is None:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover
                raise AssistantError(
                    "Pacote 'anthropic' não instalado. Rode: pip install -r requirements.txt"
                ) from exc
            if not (os.environ.get("ANTHROPIC_API_KEY") or
                    os.environ.get("ANTHROPIC_AUTH_TOKEN")):
                raise AssistantError(
                    "Defina ANTHROPIC_API_KEY no ambiente para conversar sobre o livro."
                )
            _client = anthropic.Anthropic()
        return _client


def available() -> bool:
    try:
        get_client()
        return True
    except AssistantError:
        return False


# --------------------------------------------------------------------------
# memória: resumos por capítulo


def _chapters_up_to(content: dict, boundary: int) -> list[tuple[dict, int]]:
    """Capítulos lidos, com o bloco final considerado em cada um.

    O último item pode ser um capítulo parcial (o leitor parou no meio dele).
    """
    out = []
    for chapter in content["chapters"]:
        if chapter["last_block"] < chapter["first_block"]:
            continue  # capítulo sem texto (separadores, páginas de imagem)
        if chapter["last_block"] <= boundary:
            out.append((chapter, chapter["last_block"]))
        elif chapter["first_block"] <= boundary:
            out.append((chapter, boundary))
            break
        else:
            break
    return out


def pending_summaries(book_id: str, content: dict, boundary: int) -> list[tuple[dict, int]]:
    pending = []
    for chapter, end in _chapters_up_to(content, boundary):
        if store.get_summary(book_id, chapter["index"], end) is None:
            pending.append((chapter, end))
    return pending


def _chapter_text(content: dict, chapter: dict, end_block: int) -> str:
    parts = [b["t"] for b in content["blocks"]
             if b["c"] == chapter["index"] and b["i"] <= end_block]
    return "\n\n".join(parts)


def _call(model: str, system: str, prompt: str, max_tokens: int = 1500,
          effort: str = "low") -> str:
    client = get_client()
    kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": effort},
    }
    try:
        response = client.messages.create(**kwargs)
    except TypeError:  # SDK antigo sem output_config/thinking
        kwargs.pop("output_config", None)
        kwargs.pop("thinking", None)
        response = client.messages.create(**kwargs)
    if getattr(response, "stop_reason", None) == "refusal":
        raise AssistantError("O modelo recusou a solicitação.")
    return "".join(b.text for b in response.content if b.type == "text").strip()


SUMMARY_SYSTEM = """\
Você resume trechos de livros para servir de memória a um companheiro de \
leitura. Escreva em português do Brasil, em prosa corrida, até 220 palavras.

Cubra, na ordem do texto: o que acontece, quem aparece e o que faz, mudanças \
de lugar e de tempo, informações factuais que provavelmente importarão \
depois, e o tom/estado em que o trecho termina. Em obras de não ficção, cubra \
as teses, os argumentos e os exemplos.

Ative-se ao trecho: não interprete além dele, não compare com outras obras, \
não antecipe nada e não comente o que está fora do que foi enviado. Sem \
introdução ("Neste capítulo…") — comece direto pelo conteúdo."""


def _summarize_text(text: str, label: str, partial: bool) -> str:
    if len(text) <= MAX_SUMMARY_CHARS:
        note = (" Este é um trecho PARCIAL: o leitor parou no meio, então o "
                "resumo deve terminar exatamente onde o texto termina.") if partial else ""
        return _call(
            SUMMARY_MODEL, SUMMARY_SYSTEM,
            f"Trecho: {label}.{note}\n\n<texto>\n{text}\n</texto>",
            max_tokens=1200,
        )
    # capítulo muito longo: resume por partes e depois consolida
    chunks = [text[i:i + MAX_SUMMARY_CHARS] for i in range(0, len(text), MAX_SUMMARY_CHARS)]
    partials = []
    for n, chunk in enumerate(chunks, 1):
        partials.append(_call(
            SUMMARY_MODEL, SUMMARY_SYSTEM,
            f"Trecho: {label} (parte {n} de {len(chunks)}).\n\n<texto>\n{chunk}\n</texto>",
            max_tokens=1200,
        ))
    joined = "\n\n".join(f"[parte {n}] {p}" for n, p in enumerate(partials, 1))
    return _call(
        SUMMARY_MODEL, SUMMARY_SYSTEM,
        f"Consolide os resumos parciais abaixo de {label} em um único resumo "
        f"contínuo, sem repetições e sem perder fatos.\n\n{joined}",
        max_tokens=1400,
    )


def summarize_chapter(book_id: str, content: dict, chapter: dict, end: int) -> str:
    """Resume um capítulo (ou o trecho lido dele) e guarda em cache."""
    text = _chapter_text(content, chapter, end)
    if not text.strip():
        summary = "(trecho sem texto)"
    else:
        summary = _summarize_text(
            text, f"«{chapter['title']}»", partial=end < chapter["last_block"]
        )
    store.save_summary(book_id, chapter["index"], end, summary)
    return summary


def build_memory(book_id: str, content: dict, boundary: int, on_status=None) -> int:
    """Gera (e guarda) os resumos que faltam até a fronteira."""
    pending = pending_summaries(book_id, content, boundary)
    for n, (chapter, end) in enumerate(pending, 1):
        if on_status:
            on_status(chapter, n, len(pending))
        summarize_chapter(book_id, content, chapter, end)
    return len(pending)


def memory_status(book_id: str, content: dict, boundary: int) -> dict:
    chapters = _chapters_up_to(content, boundary)
    pending = pending_summaries(book_id, content, boundary)
    return {"chapters_read": len(chapters), "pending": len(pending),
            "ready": len(chapters) - len(pending)}


# --------------------------------------------------------------------------
# montagem do contexto


def position_label(content: dict, boundary: int) -> dict:
    total = max(content["total_blocks"], 1)
    chapter = None
    for ch in content["chapters"]:
        if ch["first_block"] <= boundary <= max(ch["last_block"], ch["first_block"]):
            chapter = ch
            break
    if chapter is None:
        chapter = content["chapters"][0] if content["chapters"] else {"index": 0, "title": "—"}
    span = max(chapter.get("last_block", 0) - chapter.get("first_block", 0), 1)
    within = (boundary - chapter.get("first_block", 0)) / span
    return {
        "chapter_index": chapter["index"],
        "chapter_title": chapter.get("title", ""),
        "chapter_percent": round(100 * min(max(within, 0), 1)),
        "book_percent": round(100 * (boundary + 1) / total, 1),
        "block": boundary,
    }


def _collect_sources(book_id: str, content: dict, boundary: int, query: str) -> list[dict]:
    if not query.strip():
        return []
    index = retrieval.get_index(book_id, content["blocks"])
    hits = index.search(query, limit=TOP_PASSAGES, max_block=boundary)
    titles = {c["index"]: c["title"] for c in content["chapters"]}
    sources = []
    for hit in hits:
        block = hit["block"]
        sources.append({
            "block": block["i"],
            "chapter": block["c"],
            "chapter_title": titles.get(block["c"], ""),
            "text": block["t"][:MAX_PASSAGE_CHARS],
            "score": hit["score"],
        })
    return sources


def _recent_blocks(content: dict, boundary: int) -> list[dict]:
    recent, size = [], 0
    for block in reversed(content["blocks"]):
        if block["i"] > boundary:
            continue
        size += len(block["t"])
        recent.append(block)
        if size > MAX_RECENT_CHARS:
            break
    return list(reversed(recent))


def build_context(book, content: dict, boundary: int, query: str) -> tuple[str, list[dict]]:
    position = position_label(content, boundary)
    titles = {c["index"]: c["title"] for c in content["chapters"]}
    parts = [
        "<livro>",
        f"Título: {book['title']}",
        f"Autoria: {book['author'] or 'desconhecida'}",
        f"Idioma da obra: {book['language'] or 'não informado'}",
        "</livro>",
        "",
        "<ponto_de_leitura>",
        f"O leitor está em «{position['chapter_title']}» "
        f"(capítulo {position['chapter_index'] + 1} de {book['total_chapters']}), "
        f"a cerca de {position['chapter_percent']}% do capítulo e "
        f"{position['book_percent']}% do livro.",
        "Tudo o que vem abaixo está ANTES deste ponto. Não existe mais nada.",
        "</ponto_de_leitura>",
        "",
        "<memoria_do_lido>",
    ]
    for chapter, end in _chapters_up_to(content, boundary):
        summary = store.get_summary(book["id"], chapter["index"], end)
        if not summary:
            continue
        partial = " (lido só até aqui)" if end < chapter["last_block"] else ""
        parts.append(f"### Cap. {chapter['index'] + 1} — {chapter['title']}{partial}")
        parts.append(summary)
        parts.append("")
    parts.append("</memoria_do_lido>")

    sources = _collect_sources(book["id"], content, boundary, query)
    if sources:
        parts += ["", "<trechos_recuperados>",
                  "Passagens do que já foi lido que casam com a pergunta:"]
        for src in sources:
            parts.append(
                f"[cap. {src['chapter'] + 1} — {src['chapter_title']}] {src['text']}"
            )
        parts.append("</trechos_recuperados>")

    recent = _recent_blocks(content, boundary)
    if recent:
        parts += ["", "<leitura_recente>",
                  "As últimas linhas lidas, na íntegra (o leitor acabou de passar por elas):"]
        current_chapter = None
        for block in recent:
            if block["c"] != current_chapter:
                current_chapter = block["c"]
                parts.append(f"[cap. {current_chapter + 1} — {titles.get(current_chapter, '')}]")
            parts.append(block["t"])
        parts.append("</leitura_recente>")

    return "\n".join(parts), sources


# --------------------------------------------------------------------------
# resposta


def stream_answer(book, content: dict, boundary: int, question: str, mode: str,
                  history: list[dict], selection: str = "", strict: bool = False):
    """Gera a resposta em streaming. Rende dicionários de evento."""
    mode_instruction = MODES.get(mode, "")
    query_for_retrieval = " ".join(filter(None, [question, selection, mode_instruction[:120]]))

    try:
        pending = pending_summaries(book["id"], content, boundary)
    except AssistantError as exc:
        yield {"type": "error", "message": str(exc)}
        return
    for n, (chapter, end) in enumerate(pending, 1):
        yield {"type": "status",
               "message": f"Relendo o que você já leu… ({n}/{len(pending)}) {chapter['title']}"}
        try:
            summarize_chapter(book["id"], content, chapter, end)
        except AssistantError as exc:
            yield {"type": "error", "message": str(exc)}
            return
        except Exception as exc:  # falha em um capítulo não derruba a conversa
            yield {"type": "status", "message": f"(não consegui resumir «{chapter['title']}»: {exc})"}
    if pending:
        yield {"type": "status", "message": ""}

    context, sources = build_context(book, content, boundary, query_for_retrieval)

    system = [
        {"type": "text", "text": SYSTEM_RULES + (STRICT_RULES if strict else "")},
        {"type": "text", "text": context, "cache_control": {"type": "ephemeral"}},
    ]

    messages = []
    for item in history[-8:]:
        if item["role"] in ("user", "assistant") and item["content"].strip():
            messages.append({"role": item["role"], "content": item["content"]})
    if messages and messages[0]["role"] == "assistant":
        messages.pop(0)

    user_parts = []
    if mode_instruction:
        user_parts.append(mode_instruction)
    if selection:
        user_parts.append(f"Trecho selecionado pelo leitor:\n<<<{selection.strip()}>>>")
    if question.strip():
        user_parts.append(f"Pergunta do leitor: {question.strip()}")
    if not user_parts:
        user_parts.append("Comente o que foi lido até aqui.")
    messages.append({"role": "user", "content": "\n\n".join(user_parts)})

    yield {"type": "sources", "sources": [
        {"block": s["block"], "chapter": s["chapter"], "chapter_title": s["chapter_title"],
         "excerpt": s["text"][:180]} for s in sources
    ]}

    try:
        client = get_client()
    except AssistantError as exc:
        yield {"type": "error", "message": str(exc)}
        return

    kwargs = {
        "model": MODEL,
        "max_tokens": 8000,
        "system": system,
        "messages": messages,
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": CHAT_EFFORT},
    }
    try:
        try:
            stream_cm = client.messages.stream(**kwargs)
        except TypeError:
            kwargs.pop("output_config", None)
            kwargs.pop("thinking", None)
            stream_cm = client.messages.stream(**kwargs)
        with stream_cm as stream:
            for text in stream.text_stream:
                yield {"type": "delta", "text": text}
            final = stream.get_final_message()
        if getattr(final, "stop_reason", None) == "refusal":
            yield {"type": "error", "message": "O modelo recusou responder a esta mensagem."}
            return
        yield {"type": "done"}
    except Exception as exc:
        yield {"type": "error", "message": f"Falha ao falar com o modelo: {exc}"}

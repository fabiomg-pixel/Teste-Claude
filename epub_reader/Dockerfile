# O leitor na nuvem.
#
# Constrói a partir desta pasta (epub_reader/), não da raiz do repositório —
# lá vive outro projeto, com um app.py e um requirements.txt que não são
# estes.
#
#   cd epub_reader && fly deploy

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# As dependências primeiro, numa camada só delas: mexer no código do leitor
# não obriga a reinstalar tudo a cada deploy.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn==23.0.0

COPY . .

# /data é o volume: é o que sobrevive a um deploy. Todo o resto da imagem é
# descartável e volta igual na próxima subida.
ENV EPUB_DATA_DIR=/data \
    EPUB_ATRAS_DE_PROXY=1 \
    EPUB_EXIGIR_SENHA=1 \
    PORT=8080

EXPOSE 8080

# gthread, e não o worker padrão: a conversa responde em streaming (SSE) e
# uma resposta longa prenderia um worker síncrono inteiro. O timeout alto
# existe pelo mesmo motivo — uma resposta do modelo passa dos 30s padrão.
#
# --preload importa o app no processo mestre, antes de bifurcar. Sem ele, uma
# configuração inválida (a senha faltando, digamos) mata o worker, o mestre o
# reergue, e o serviço fica batendo a cabeça para sempre em vez de falhar de
# uma vez — que é o que se quer ver num deploy errado.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--preload", \
     "--worker-class", "gthread", "--workers", "1", "--threads", "8", \
     "--timeout", "300", "--graceful-timeout", "30", \
     "--access-logfile", "-", "app:app"]

"""Gera os três segredos que o servidor pede na nuvem, prontos para colar.

    python3 segredos.py

Eles não vão para o repositório nem para a imagem: são variáveis de ambiente
do serviço, definidas uma vez no painel da hospedagem. Numa hospedagem de
disco efêmero isso deixa de ser conselho e vira requisito — o que o servidor
gerasse sozinho nasceria diferente a cada reinício, e aí:

- `EPUB_SYNC_TOKEN` novo  →  todos os aparelhos passam a levar 401, em silêncio;
- `EPUB_SECRET` nova      →  todo mundo é deslogado a cada vez que ele acorda.

Livros e estado, esses sim, se reconstroem sozinhos: os aparelhos os reenviam
na sincronização seguinte.
"""

from __future__ import annotations

import secrets
import string


def senha_legivel(palavras: int = 4) -> str:
    """Uma senha que dá para digitar no teclado do celular sem ódio.

    Sílabas sorteadas em vez de caracteres aleatórios: o que se ganha em
    entropia por caractere se perde quando a pessoa desiste e escolhe «1234».
    """
    silabas = ("ba be bi bo bu ca ce co cu da de di do du fa fe fi fo fu ga "
               "go gu ja je ji jo ju la le li lo lu ma me mi mo mu na ne ni "
               "no nu pa pe pi po pu ra re ri ro ru sa se si so su ta te ti "
               "to tu va ve vi vo vu za ze zi zo zu").split()
    return "-".join("".join(secrets.choice(silabas) for _ in range(3))
                    for _ in range(palavras))


if __name__ == "__main__":
    alfabeto = string.ascii_letters + string.digits
    print("Defina estas três variáveis no ambiente do serviço:\n")
    print("EPUB_SENHA=" + senha_legivel())
    print("EPUB_SYNC_TOKEN=" + "".join(secrets.choice(alfabeto) for _ in range(32)))
    print("EPUB_SECRET=" + secrets.token_urlsafe(48))
    print("\nA senha é a que você digita no navegador; o token é o que os")
    print("aparelhos usam para sincronizar; a chave assina o cookie de sessão.")
    print("Guarde-as — a senha e o token você vai precisar digitar de novo.")

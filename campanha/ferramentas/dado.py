#!/usr/bin/env python3
"""Rolador de dados honesto da campanha "O Oitavo Canto".

Usa aleatoriedade criptográfica (secrets). Mostra cada dado rolado.

Exemplos:
  python3 dado.py 1d20+5
  python3 dado.py 1d20+5 --rotulo "Percepção de Dalva" --log
  python3 dado.py 2d6+3 1d8                 # várias expressões
  python3 dado.py 4d6k3                     # mantém os 3 maiores
  python3 dado.py 1d20+3adv                 # vantagem (2d20, maior)
  python3 dado.py 1d20+3des                 # desvantagem (2d20, menor)
  python3 dado.py 1d20+2 --cd 15            # compara com uma CD
  python3 dado.py ini "Dalva:1" "Lobos:2" "Cássia:1"   # iniciativa em bloco
  python3 dado.py 1d20 --json               # saída em JSON
"""
import argparse
import datetime
import json
import pathlib
import re
import secrets
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
LOG = RAIZ / "estado" / "rolagens.log"

EXPR = re.compile(
    r"^(?P<n>\d*)d(?P<faces>\d+)(?:k(?P<keep>\d+))?(?P<mod>[+-]\d+)?(?P<flag>adv|des)?$",
    re.IGNORECASE,
)


def rolar(expr: str) -> dict:
    m = EXPR.match(expr.replace(" ", ""))
    if not m:
        raise ValueError(f"expressão inválida: {expr!r} (use algo como 1d20+5, 2d6, 4d6k3, 1d20adv)")
    n = int(m.group("n") or 1)
    faces = int(m.group("faces"))
    keep = int(m.group("keep")) if m.group("keep") else None
    mod = int(m.group("mod") or 0)
    flag = (m.group("flag") or "").lower()
    if n < 1 or n > 100 or faces < 2 or faces > 1000:
        raise ValueError(f"fora dos limites: {expr!r}")

    detalhe = ""
    if flag in ("adv", "des"):
        if n != 1 or faces != 20:
            raise ValueError("adv/des só se aplicam a 1d20")
        a, b = secrets.randbelow(20) + 1, secrets.randbelow(20) + 1
        escolhido = max(a, b) if flag == "adv" else min(a, b)
        dados = [escolhido]
        detalhe = f"{'vantagem' if flag == 'adv' else 'desvantagem'}: [{a}, {b}] -> {escolhido}"
    else:
        dados = [secrets.randbelow(faces) + 1 for _ in range(n)]
        if keep:
            ordenados = sorted(dados, reverse=True)
            mantidos = ordenados[:keep]
            detalhe = f"todos {dados}, mantidos {mantidos}"
            dados = mantidos

    soma = sum(dados) + mod
    natural = dados[0] if (faces == 20 and len(dados) == 1) else None
    return {
        "expressao": expr,
        "dados": dados,
        "modificador": mod,
        "total": soma,
        "detalhe": detalhe,
        "natural20": natural == 20,
        "natural1": natural == 1,
    }


def formatar(r: dict, cd: int | None, rotulo: str | None) -> str:
    sinal = f"{r['modificador']:+d}" if r["modificador"] else ""
    partes = [f"{rotulo}: " if rotulo else "", f"{r['expressao']} -> [{', '.join(map(str, r['dados']))}]{sinal} = **{r['total']}**"]
    if r["detalhe"]:
        partes.append(f"  ({r['detalhe']})")
    if r["natural20"]:
        partes.append("  CRÍTICO!")
    if r["natural1"]:
        partes.append("  falha crítica")
    if cd is not None:
        partes.append(f"  vs CD {cd} -> {'SUCESSO' if r['total'] >= cd else 'FALHA'}")
    return "".join(partes)


def iniciativa(args: list[str]) -> list[dict]:
    """Cada arg no formato Nome:mod. Rola 1d20+mod e ordena."""
    linhas = []
    for a in args:
        nome, _, mod = a.partition(":")
        mod_i = int(mod or 0)
        r = rolar(f"1d20{mod_i:+d}" if mod_i else "1d20")
        linhas.append({"nome": nome, "iniciativa": r["total"], "dados": r["dados"], "modificador": mod_i})
    linhas.sort(key=lambda x: (-x["iniciativa"], -x["modificador"], secrets.randbelow(1000)))
    return linhas


def registrar(entradas: list[dict]) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        for e in entradas:
            e = dict(e)
            e["quando"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("expressoes", nargs="+", help="expressões de dados, ou 'ini' seguido de Nome:mod")
    p.add_argument("--rotulo", "-r", help="descrição da rolagem")
    p.add_argument("--cd", type=int, help="Classe de Dificuldade para comparar")
    p.add_argument("--log", action="store_true", help=f"acrescenta ao {LOG.relative_to(RAIZ)}")
    p.add_argument("--json", action="store_true", help="saída em JSON")
    a = p.parse_args()

    try:
        if a.expressoes[0].lower() == "ini":
            ordem = iniciativa(a.expressoes[1:])
            if a.json:
                print(json.dumps(ordem, ensure_ascii=False, indent=2))
            else:
                print("Iniciativa:")
                for i, l in enumerate(ordem, 1):
                    print(f"  {i}. {l['nome']}: {l['iniciativa']}  (d20 {l['dados'][0]}{l['modificador']:+d})")
            if a.log:
                registrar([{"tipo": "iniciativa", "rotulo": a.rotulo, "ordem": ordem}])
            return 0

        resultados = [rolar(e) for e in a.expressoes]
        if a.json:
            print(json.dumps(resultados, ensure_ascii=False, indent=2))
        else:
            for r in resultados:
                print(formatar(r, a.cd, a.rotulo))
        if a.log:
            registrar([{"tipo": "rolagem", "rotulo": a.rotulo, "cd": a.cd, **r} for r in resultados])
        return 0
    except ValueError as e:
        print(f"erro: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

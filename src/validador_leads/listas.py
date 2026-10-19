from functools import cache
from importlib.resources import files


@cache
def carregar(nome: str) -> frozenset[str]:
    texto = (files("validador_leads") / "listas" / f"{nome}.txt").read_text(encoding="utf-8")
    return frozenset(
        linha.strip().lower() for linha in texto.splitlines() if linha.strip() and not linha.startswith("#")
    )

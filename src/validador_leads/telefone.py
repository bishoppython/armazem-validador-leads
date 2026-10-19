"""Telefones brasileiros: normalização para 55DDNNNNNNNNN e classificação celular/fixo."""

import re
from dataclasses import dataclass

DDDS = frozenset(
    {11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 24, 27, 28, 31, 32, 33, 34, 35, 37, 38, 41, 42, 43, 44, 45,
     46, 47, 48, 49, 51, 53, 54, 55, 61, 62, 63, 64, 65, 66, 67, 68, 69, 71, 73, 74, 75, 77, 79, 81, 82, 83,
     84, 85, 86, 87, 88, 89, 91, 92, 93, 94, 95, 96, 97, 98, 99}
)  # fmt: skip


@dataclass(frozen=True)
class TelefoneAnalisado:
    numero: str | None  # 55 + DDD + número; None = inválido ou ausente
    celular: bool = False
    presente: bool = False


def analisar(bruto: str | None) -> TelefoneAnalisado:
    if not bruto or not str(bruto).strip():
        return TelefoneAnalisado(numero=None)
    digitos = re.sub(r"\D", "", str(bruto))
    if digitos.startswith("55") and len(digitos) in (12, 13):
        digitos = digitos[2:]
    digitos = digitos.lstrip("0")
    if len(digitos) not in (10, 11) or int(digitos[:2]) not in DDDS:
        return TelefoneAnalisado(numero=None, presente=True)
    assinante = digitos[2:]
    celular = len(assinante) == 9 and assinante[0] == "9"
    fixo = len(assinante) == 8 and assinante[0] in "2345"
    if not (celular or fixo) or len(set(assinante)) == 1:
        return TelefoneAnalisado(numero=None, presente=True)
    return TelefoneAnalisado(numero=f"55{digitos}", celular=celular, presente=True)

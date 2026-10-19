"""Validação de CNPJ pelos dígitos verificadores (sem consulta à Receita)."""

import re


def _digito(base: str) -> str:
    pesos = list(range(len(base) - 7, 1, -1)) + list(range(9, 1, -1))
    resto = sum(int(d) * p for d, p in zip(base, pesos, strict=True)) % 11
    return "0" if resto < 2 else str(11 - resto)


def normalizar(bruto: str | None) -> str | None:
    """14 dígitos se o CNPJ for válido, senão None."""
    if not bruto:
        return None
    digitos = re.sub(r"\D", "", str(bruto)).zfill(14)
    if len(digitos) != 14 or len(set(digitos)) == 1:
        return None
    base = digitos[:12]
    dv1 = _digito(base)
    dv2 = _digito(base + dv1)
    return digitos if digitos[12:] == dv1 + dv2 else None


def gerar_digitos(base12: str) -> str:
    """Completa uma base de 12 dígitos com os verificadores (usado no gerador de dados)."""
    dv1 = _digito(base12)
    return base12 + dv1 + _digito(base12 + dv1)

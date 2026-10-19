"""Validação de e-mail sem rede: normalização, sintaxe, typos de domínio e tipo de endereço."""

import difflib
from dataclasses import dataclass

from email_validator import EmailNotValidError, validate_email

from validador_leads.listas import carregar

# Erros de digitação vistos com frequência em bases brasileiras.
TYPOS = {
    "gmial.com": "gmail.com",
    "gmai.com": "gmail.com",
    "gamil.com": "gmail.com",
    "gmail.com.br": "gmail.com",
    "gmail.co": "gmail.com",
    "gnail.com": "gmail.com",
    "hotmal.com": "hotmail.com",
    "hotmial.com": "hotmail.com",
    "hotmail.co": "hotmail.com",
    "hotmeil.com": "hotmail.com",
    "outlok.com": "outlook.com",
    "outllook.com": "outlook.com",
    "yaho.com.br": "yahoo.com.br",
    "yahoo.com.bt": "yahoo.com.br",
    "uol.com": "uol.com.br",
    "bol.com": "bol.com.br",
}

# Caixas de função: chegam à empresa, mas não a uma pessoa que decide.
FUNCOES = frozenset(
    """
    contato comercial vendas atendimento financeiro faturamento sac suporte info adm
    administrativo admin rh marketing compras cobranca falecom faleconosco ola oi noreply no-
    reply
    """.split()
)


@dataclass(frozen=True)
class EmailAnalisado:
    original: str
    email: str | None  # normalizado (e corrigido, se havia typo); None = sintaxe inválida
    dominio: str | None
    corrigido: bool = False
    descartavel: bool = False
    pessoal: bool = False
    funcao: bool = False


def normalizar(bruto: str) -> str:
    # Espaço no meio não é removido: "joao silva@" pode ser joaosilva, joao.silva ou joao_silva.
    texto = bruto.strip().strip("<>\"'").lower()
    return texto.removeprefix("mailto:").rstrip(".,;")


def corrigir_dominio(dominio: str) -> str:
    if dominio in TYPOS:
        return TYPOS[dominio]
    pessoais = carregar("pessoais")
    if dominio in pessoais:
        return dominio
    # Domínio a uma letra de um provedor conhecido (ex.: "hotmaill.com").
    # Ordenado: a ordem de um frozenset muda entre processos e decidiria empates.
    parecido = difflib.get_close_matches(dominio, sorted(pessoais), n=1, cutoff=0.9)
    return parecido[0] if parecido else dominio


def analisar(bruto: str | None) -> EmailAnalisado:
    if not bruto or not str(bruto).strip():
        return EmailAnalisado(original="", email=None, dominio=None)
    original = str(bruto)
    texto = normalizar(original)
    if texto.count("@") != 1:
        return EmailAnalisado(original=original, email=None, dominio=None)
    local, dominio = texto.split("@")
    certo = corrigir_dominio(dominio)
    try:
        validado = validate_email(f"{local}@{certo}", check_deliverability=False)
    except EmailNotValidError:
        return EmailAnalisado(original=original, email=None, dominio=None)
    dominio_final = validado.domain.lower()
    return EmailAnalisado(
        original=original,
        email=validado.normalized.lower(),
        dominio=dominio_final,
        corrigido=certo != dominio,
        descartavel=dominio_final in carregar("descartaveis"),
        pessoal=dominio_final in carregar("pessoais"),
        funcao=local.split("+")[0] in FUNCOES,
    )

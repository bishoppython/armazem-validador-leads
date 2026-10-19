"""Pipeline de validação, da etapa mais barata para a mais cara.

1. normalização e sintaxe (local)  2. domínio descartável/pessoal/typo (local)
3. deduplicação (local)            4. MX (DNS, com cache)
5. site da empresa (HTTP, opcional) 6. score e relatório
"""

import logging
import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import Any

import pandas as pd

from validador_leads import cnpj, email, telefone
from validador_leads.dns_mx import VerificadorMX
from validador_leads.enriquecimento import Baixador, baixar, enriquecer
from validador_leads.pontuacao import DESCARTE, Avaliacao

log = logging.getLogger(__name__)

# Nomes de coluna aceitos na entrada → nome canônico.
ALIASES = {
    "nome": ("nome", "name", "contato", "nome_completo"),
    "email": ("email", "e-mail", "e_mail", "mail"),
    "telefone": ("telefone", "fone", "celular", "whatsapp", "phone", "tel"),
    "empresa": ("empresa", "company", "razao_social", "organizacao"),
    "cnpj": ("cnpj",),
}


@dataclass
class Opcoes:
    verificar_mx: bool = True
    enriquecer_site: bool = False
    verificador: VerificadorMX | None = None
    baixador: Baixador = baixar


def _canonizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    renomear: dict[str, str] = {}
    for coluna in df.columns:
        chave = str(coluna).strip().lower()
        for canonico, nomes in ALIASES.items():
            if chave in nomes and canonico not in renomear.values():
                renomear[coluna] = canonico
    df = df.rename(columns=renomear)
    for canonico in ALIASES:
        if canonico not in df.columns:
            df[canonico] = None
    return df


def _texto(valor: Any) -> str:
    return "" if valor is None or (isinstance(valor, float) and pd.isna(valor)) else str(valor).strip()


def _chave_nome(nome: str, empresa: str) -> str:
    base = f"{nome} {empresa}".lower()
    sem_acento = "".join(c for c in unicodedata.normalize("NFKD", base) if not unicodedata.combining(c))
    return " ".join(sem_acento.split())


def validar(entrada: pd.DataFrame, opcoes: Opcoes | None = None) -> tuple[pd.DataFrame, dict[str, Any]]:
    opcoes = opcoes or Opcoes()
    df = _canonizar_colunas(entrada.copy())
    avaliacoes = [Avaliacao() for _ in range(len(df))]
    saida: dict[str, list[Any]] = {
        k: [] for k in ("email_normalizado", "dominio", "telefone_normalizado", "celular", "cnpj_normalizado")
    }

    # 1 e 2. Etapas locais, linha a linha.
    for i, linha in enumerate(df.itertuples(index=False)):
        av = avaliacoes[i]
        e = email.analisar(_texto(linha.email))
        if not _texto(linha.email):
            av.motivos.append("email_ausente")
        elif e.email is None:
            av.motivos.append("email_invalido")
        else:
            if e.descartavel:
                av.motivos.append("email_descartavel")
            if e.corrigido:
                av.motivos.append("email_corrigido")
            if e.pessoal:
                av.motivos.append("email_pessoal")
            if e.funcao:
                av.motivos.append("email_funcao")
        t = telefone.analisar(_texto(linha.telefone))
        if not t.presente:
            av.motivos.append("telefone_ausente")
        elif t.numero is None:
            av.motivos.append("telefone_invalido")
        elif not t.celular:
            av.motivos.append("telefone_fixo")
        c = cnpj.normalizar(_texto(linha.cnpj))
        if not _texto(linha.cnpj):
            av.motivos.append("cnpj_ausente")
        elif c is None:
            av.motivos.append("cnpj_invalido")
        if not _texto(linha.nome):
            av.motivos.append("nome_ausente")
        if not _texto(linha.empresa):
            av.motivos.append("empresa_ausente")
        saida["email_normalizado"].append(e.email)
        saida["dominio"].append(e.dominio)
        saida["telefone_normalizado"].append(t.numero)
        saida["celular"].append(t.celular)
        saida["cnpj_normalizado"].append(c)

    # 3. Deduplicação: mantém a primeira ocorrência, por e-mail normalizado e por nome + empresa.
    vistos_email: set[str] = set()
    vistos_nome: set[str] = set()
    for i, linha in enumerate(df.itertuples(index=False)):
        av = avaliacoes[i]
        if av.descartado:
            continue
        chave_email = saida["email_normalizado"][i]
        nome, empresa = _texto(linha.nome), _texto(linha.empresa)
        chave_nome = _chave_nome(nome, empresa) if nome and empresa else None
        if chave_email in vistos_email or (chave_nome and chave_nome in vistos_nome):
            av.motivos.append("duplicado")
            continue
        vistos_email.add(chave_email)
        if chave_nome:
            vistos_nome.add(chave_nome)

    # 4. MX só para quem sobreviveu às etapas locais; um domínio, uma consulta.
    vivos = [i for i, av in enumerate(avaliacoes) if not av.descartado]
    if opcoes.verificar_mx:
        verificador = opcoes.verificador or VerificadorMX()
        mx = verificador.verificar(saida["dominio"][i] for i in vivos)
        for i in vivos:
            if not mx[saida["dominio"][i]]:
                avaliacoes[i].motivos.append("dominio_sem_mx")

    # 5. Site da empresa: só domínios corporativos de leads ainda válidos.
    sites = {}
    if opcoes.enriquecer_site:
        corporativos = {
            saida["dominio"][i]
            for i, av in enumerate(avaliacoes)
            if not av.descartado and "email_pessoal" not in av.motivos
        }
        sites = enriquecer(corporativos, opcoes.baixador)
        for i, av in enumerate(avaliacoes):
            site = sites.get(saida["dominio"][i])
            if site is not None and not av.descartado and not site.no_ar:
                av.motivos.append("site_fora_do_ar")

    # 6. Resultado.
    for k, v in saida.items():
        df[k] = v
    df["score"] = [av.score for av in avaliacoes]
    df["faixa"] = [av.faixa for av in avaliacoes]
    df["motivos"] = [";".join(av.motivos) for av in avaliacoes]
    if opcoes.enriquecer_site:
        df["site_titulo"] = [getattr(sites.get(d), "titulo", None) for d in saida["dominio"]]
        df["site_descricao"] = [getattr(sites.get(d), "descricao", None) for d in saida["dominio"]]
        df["linkedin_empresa"] = [getattr(sites.get(d), "linkedin", None) for d in saida["dominio"]]

    contagem = Counter(m for av in avaliacoes for m in av.motivos)
    faixas = Counter(av.faixa for av in avaliacoes)
    relatorio = {
        "entrada": len(df),
        "validos": len(df) - faixas["descartado"],
        "descartados": faixas["descartado"],
        "faixas": {f: faixas[f] for f in ("A", "B", "C", "descartado")},
        "motivos_descarte": {m: contagem[m] for m in DESCARTE if contagem[m]},
        "alertas": {m: n for m, n in contagem.most_common() if m not in DESCARTE},
        "score_medio_validos": round(
            sum(av.score for av in avaliacoes if not av.descartado) / max(1, len(df) - faixas["descartado"]), 1
        ),
    }
    return df, relatorio

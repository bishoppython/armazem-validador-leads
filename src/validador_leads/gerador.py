"""Base de leads sintética e suja de propósito (Faker pt_BR, semente fixa).

Domínios corporativos usam o TLD reservado .example (RFC 2606) para nunca apontar para
empresas reais; os sem MX usam *.inativo.example. Provedores pessoais são os reais (gmail etc.).
"""

import random
import re
import unicodedata
from typing import Any

import pandas as pd
from faker import Faker

from validador_leads.cnpj import gerar_digitos
from validador_leads.email import FUNCOES, TYPOS
from validador_leads.listas import carregar


def _slug(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto.lower())
    base = "".join(c for c in base if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", base.split(" e ")[0])[:20] or "empresa"


def gerar(n: int = 10_000, semente: int = 42) -> pd.DataFrame:
    fake = Faker("pt_BR")
    Faker.seed(semente)
    rnd = random.Random(semente)
    pessoais = ["gmail.com"] * 6 + ["hotmail.com"] * 3 + ["outlook.com", "yahoo.com.br", "uol.com.br", "bol.com.br"]
    descartaveis = sorted(carregar("descartaveis"))
    typos = sorted(TYPOS)
    funcoes = sorted(FUNCOES - {"noreply", "no-reply", "oi", "ola"})
    empresas = [fake.company() for _ in range(max(50, n // 8))]

    linhas: list[dict[str, Any]] = []
    for _ in range(n):
        nome = fake.name()
        empresa = rnd.choice(empresas)
        dominio_emp = f"{_slug(empresa)}.example"
        primeiro, ultimo = _slug(nome.split()[0]), _slug(nome.split()[-1])
        local = rnd.choice(
            [f"{primeiro}.{ultimo}", f"{primeiro}{ultimo[:1]}", f"{primeiro}_{ultimo}{rnd.randint(1, 99)}"]
        )
        r = rnd.random()
        if r < 0.40:
            mail = f"{local}@{rnd.choice(pessoais)}"
        elif r < 0.50:
            mail = f"{rnd.choice(funcoes)}@{dominio_emp}"
        else:
            mail = f"{local}@{dominio_emp}"

        sujeira = rnd.random()
        if sujeira < 0.04:
            mail = f"{local}@{rnd.choice(typos)}"
        elif sujeira < 0.07:
            mail = f"{local}@{rnd.choice(descartaveis)}"
        elif sujeira < 0.10:
            mail = rnd.choice(
                [mail.replace("@", ""), mail.replace("@", "@@"), f"{primeiro} {ultimo}@{dominio_emp}", f"{local}@"]
            )
        elif sujeira < 0.13:
            mail = f"{local}@{_slug(empresa)}.inativo.example"
        elif sujeira < 0.18:
            mail = f"  {mail.upper()} "

        ddd = rnd.choice([81, 81, 81, 87, 11, 21, 31, 71, 85])
        t = rnd.random()
        if t < 0.08:
            fone = ""
        elif t < 0.13:
            fone = rnd.choice(["99999", "(81) 1234-5678", "00 0000-0000", f"({ddd}) 99999-9999"])
        elif t < 0.30:
            fone = f"({ddd}) {rnd.randint(3000, 3999)}-{rnd.randint(1000, 9999)}"
        else:
            fone = rnd.choice([f"({ddd}) 9{rnd.randint(8000, 9999)}-{rnd.randint(1000, 9999)}",
                               f"+55 {ddd} 9{rnd.randint(8000, 9999)}{rnd.randint(1000, 9999)}"])  # fmt: skip

        c = rnd.random()
        base = "".join(str(rnd.randint(0, 9)) for _ in range(8)) + "0001"
        cnpj = "" if c < 0.15 else gerar_digitos(base)
        if 0.15 <= c < 0.19:
            cnpj = cnpj[:-1] + str((int(cnpj[-1]) + 1) % 10)
        if cnpj and rnd.random() < 0.5:
            cnpj = f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"

        linhas.append(
            {
                "Nome": "" if rnd.random() < 0.03 else nome,
                "E-mail": mail,
                "Telefone": fone,
                "Empresa": "" if rnd.random() < 0.05 else empresa,
                "CNPJ": cnpj,
                "Cidade": rnd.choice(["Caruaru", "Recife", "Toritama", "Santa Cruz do Capibaribe", fake.city()]),
            }
        )

    # Duplicatas: 6% de cópias com caixa e espaços diferentes.
    for linha in rnd.sample(linhas, k=int(n * 0.06)):
        copia = dict(linha)
        copia["E-mail"] = f" {copia['E-mail'].title()}"
        linhas.insert(rnd.randrange(len(linhas)), copia)
    return pd.DataFrame(linhas)


def resolvedor_simulado(dominio: str) -> bool:
    """Para a demo offline: *.inativo.example não tem MX; o resto tem."""
    return not dominio.endswith(".inativo.example")

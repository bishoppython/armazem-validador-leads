from pathlib import Path

import pytest

from validador_leads import cnpj, email, telefone
from validador_leads.dns_mx import VerificadorMX
from validador_leads.enriquecimento import enriquecer, extrair
from validador_leads.pontuacao import Avaliacao


@pytest.mark.parametrize(
    ("bruto", "esperado", "corrigido"),
    [
        ("  Joao.Silva@GMAIL.com ", "joao.silva@gmail.com", False),
        ("maria@gmial.com", "maria@gmail.com", True),
        ("ana@hotmaill.com", "ana@hotmail.com", True),
        ("mailto:compras@malharia.example.", "compras@malharia.example", False),
        ("sem-arroba.com", None, False),
        ("dois@@arrobas.com", None, False),
        ("joao silva@empresa.com.br", None, False),
        ("", None, False),
    ],
)
def test_email_normaliza_e_corrige(bruto: str, esperado: str | None, corrigido: bool) -> None:
    r = email.analisar(bruto)
    assert r.email == esperado
    assert r.corrigido is corrigido


def test_email_classifica_descartavel_pessoal_e_funcao() -> None:
    assert email.analisar("x@mailinator.com").descartavel
    # yopmail.com fica a 0,90 de ymail.com: descartável nunca é "corrigido" para provedor legítimo.
    yop = email.analisar("x@yopmail.com")
    assert yop.descartavel and not yop.corrigido and yop.dominio == "yopmail.com"
    assert email.analisar("x@uol.com.br").pessoal
    assert email.analisar("vendas@malharia.example").funcao
    corporativo = email.analisar("joana.lima@malharia.example")
    assert not (corporativo.pessoal or corporativo.funcao or corporativo.descartavel)


@pytest.mark.parametrize(
    ("bruto", "numero", "celular"),
    [
        ("(81) 99876-5432", "5581998765432", True),
        ("+55 81 998765432", "5581998765432", True),
        ("081 3721-1234", "558137211234", False),
        ("(20) 99876-5432", None, False),  # DDD inexistente
        ("(81) 99999-9999", None, False),  # todos iguais
        ("(81) 1234-5678", None, False),  # fixo não começa com 1
        ("99999", None, False),
    ],
)
def test_telefone(bruto: str, numero: str | None, celular: bool) -> None:
    r = telefone.analisar(bruto)
    assert r.numero == numero
    assert r.celular is celular
    assert r.presente


def test_cnpj_digitos_verificadores() -> None:
    valido = cnpj.gerar_digitos("112223330001")
    assert valido == "11222333000181"
    assert cnpj.normalizar("11.222.333/0001-81") == valido
    assert cnpj.normalizar("11.222.333/0001-82") is None
    assert cnpj.normalizar("00000000000000") is None
    assert cnpj.normalizar("") is None


def test_mx_consulta_cada_dominio_uma_vez() -> None:
    chamados: list[str] = []

    def falso(d: str) -> bool:
        chamados.append(d)
        return d != "morto.example"

    v = VerificadorMX(falso)
    assert v.verificar(["a.example", "a.example", "morto.example"]) == {"a.example": True, "morto.example": False}
    v.verificar(["a.example"])
    assert sorted(chamados) == ["a.example", "morto.example"]


def test_extrai_dados_publicos_do_site() -> None:
    html = Path("tests/fixtures/site_empresa.html").read_text(encoding="utf-8")
    s = extrair("malharia.example", html)
    assert s.titulo == "Malharia Exemplo · Uniformes em Caruaru"
    assert s.descricao and s.descricao.startswith("Uniformes")
    assert s.linkedin == "https://www.linkedin.com/company/malharia-exemplo/"
    assert s.instagram == "https://www.instagram.com/malhariaexemplo"


def test_enriquecer_marca_site_fora_do_ar() -> None:
    r = enriquecer(["vivo.example", "fora.example"], lambda d: "<title>ok</title>" if d == "vivo.example" else None)
    assert r["vivo.example"].no_ar and not r["fora.example"].no_ar


def test_score_desconta_e_descarta() -> None:
    assert Avaliacao(["email_pessoal", "telefone_fixo"]).score == 75
    assert Avaliacao(["email_pessoal", "telefone_fixo"]).faixa == "B"
    assert Avaliacao(["email_funcao", "duplicado"]).score == 0
    assert Avaliacao([]).faixa == "A"

import json
from pathlib import Path

import pandas as pd
from typer.testing import CliRunner

from validador_leads.cli import app
from validador_leads.dns_mx import VerificadorMX
from validador_leads.gerador import gerar, resolvedor_simulado
from validador_leads.pipeline import Opcoes, validar

CNPJ = "11.222.333/0001-81"


def _opcoes(**kw: object) -> Opcoes:
    return Opcoes(verificador=VerificadorMX(resolvedor_simulado), **kw)  # type: ignore[arg-type]


def test_pipeline_ponta_a_ponta() -> None:
    entrada = pd.DataFrame(
        [
            {
                "Nome": "Ana Lima",
                "E-mail": "ana.lima@malharia.example",
                "Fone": "(81) 99876-5432",
                "Empresa": "Malharia",
                "CNPJ": CNPJ,
            },
            {"Nome": "Ana Lima", "E-mail": " ANA.LIMA@malharia.example", "Fone": "", "Empresa": "Malharia", "CNPJ": ""},
            {"Nome": "Bruno", "E-mail": "bruno@mailinator.com", "Fone": "", "Empresa": "X", "CNPJ": ""},
            {"Nome": "Caio", "E-mail": "caio@velha.inativo.example", "Fone": "", "Empresa": "Y", "CNPJ": ""},
            {"Nome": "Davi", "E-mail": "davi@gmial.com", "Fone": "(81) 3721-1234", "Empresa": "Z", "CNPJ": CNPJ},
            {"Nome": "", "E-mail": "sem-arroba", "Fone": "", "Empresa": "", "CNPJ": ""},
        ]
    )
    df, rel = validar(entrada, _opcoes())
    assert list(df["faixa"]) == ["A", "descartado", "descartado", "descartado", "B", "descartado"]
    assert df.loc[0, "score"] == 100
    assert df.loc[4, "email_normalizado"] == "davi@gmail.com"
    assert set(df.loc[4, "motivos"].split(";")) == {"email_corrigido", "email_pessoal", "telefone_fixo"}
    assert rel["motivos_descarte"] == {"email_invalido": 1, "email_descartavel": 1, "dominio_sem_mx": 1, "duplicado": 1}
    assert rel["validos"] == 2


def test_duplicado_por_nome_e_empresa_com_email_diferente() -> None:
    entrada = pd.DataFrame(
        [
            {"nome": "José Silva", "email": "jose@a.example", "empresa": "Malharia Sol"},
            {"nome": "jose  silva", "email": "jose.silva@gmail.com", "empresa": "MALHARIA SOL"},
        ]
    )
    df, _ = validar(entrada, _opcoes())
    assert df.loc[1, "motivos"].endswith("duplicado")


def test_mx_desligado_nao_consulta() -> None:
    def proibido(d: str) -> bool:
        raise AssertionError("não devia consultar DNS")

    df, _ = validar(
        pd.DataFrame([{"email": "a@b.example"}]), Opcoes(verificar_mx=False, verificador=VerificadorMX(proibido))
    )
    assert df.loc[0, "faixa"] != "descartado"


def test_gerador_reprodutivel_e_sujo() -> None:
    a, b = gerar(500, semente=7), gerar(500, semente=7)
    assert a.equals(b)
    assert len(a) == 530  # 6% de duplicatas
    _, rel = validar(a, _opcoes())
    assert set(rel["motivos_descarte"]) == {"email_invalido", "email_descartavel", "dominio_sem_mx", "duplicado"}


def test_cli_valida_csv(tmp_path: Path) -> None:
    entrada = tmp_path / "leads.csv"
    entrada.write_text(
        "nome;email;telefone\nAna;ana@malharia.example;81998765432\nB;x@mailinator.com;\n", encoding="utf-8"
    )
    saida, relatorio = tmp_path / "saida.csv", tmp_path / "rel.json"
    r = CliRunner().invoke(
        app,
        ["validar", str(entrada), "-o", str(saida), "--relatorio", str(relatorio), "--mx", "simulado", "--so-validos"],
    )
    assert r.exit_code == 0, r.output
    assert len(pd.read_csv(saida)) == 1
    assert json.loads(relatorio.read_text())["descartados"] == 1


def test_validacao_reprodutivel_entre_processos(tmp_path: Path) -> None:
    import os
    import subprocess
    import sys

    base = tmp_path / "base.csv"
    gerar(2000, semente=3).to_csv(base, index=False)
    saidas = []
    for semente_hash in ("1", "2"):
        saida = tmp_path / f"v{semente_hash}.csv"
        subprocess.run(
            [sys.executable, "-m", "validador_leads.cli", "validar", str(base), "-o", str(saida), "--mx", "simulado"],
            check=True,
            capture_output=True,
            env={**os.environ, "PYTHONHASHSEED": semente_hash},
        )
        saidas.append(saida.read_bytes())
    assert saidas[0] == saidas[1]

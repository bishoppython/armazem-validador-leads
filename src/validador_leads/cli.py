"""Linha de comando: leads validar | gerar."""

import json
import logging
from enum import StrEnum
from pathlib import Path

import pandas as pd
import typer

app = typer.Typer(no_args_is_help=True, help="Validação, deduplicação e score de bases de leads.")


class ModoMX(StrEnum):
    real = "real"
    simulado = "simulado"
    desligado = "desligado"


def _ler(caminho: Path) -> pd.DataFrame:
    if caminho.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(caminho, dtype=str)
    return pd.read_csv(caminho, dtype=str, sep=None, engine="python", encoding="utf-8-sig")


@app.command()
def validar(
    entrada: Path,
    saida: Path = typer.Option(Path("leads_validados.csv"), "-o", help="CSV com todas as linhas e colunas novas."),
    relatorio: Path | None = typer.Option(None, help="Relatório em JSON."),
    mx: ModoMX = typer.Option(ModoMX.real, help="real = DNS; simulado = demo offline; desligado = pula."),
    site: bool = typer.Option(False, help="Visita o site dos domínios corporativos."),
    so_validos: bool = typer.Option(False, help="Grava só os leads não descartados."),
) -> None:
    """Valida uma planilha de leads (CSV ou XLSX)."""
    from validador_leads.dns_mx import VerificadorMX
    from validador_leads.gerador import resolvedor_simulado
    from validador_leads.pipeline import Opcoes
    from validador_leads.pipeline import validar as rodar

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    verificador = VerificadorMX(resolvedor_simulado) if mx is ModoMX.simulado else VerificadorMX()
    df, rel = rodar(
        _ler(entrada), Opcoes(verificar_mx=mx is not ModoMX.desligado, enriquecer_site=site, verificador=verificador)
    )
    if so_validos:
        df = df[df["faixa"] != "descartado"]
    df.sort_values("score", ascending=False).to_csv(saida, index=False)
    texto = json.dumps(rel, indent=2, ensure_ascii=False)
    if relatorio:
        relatorio.write_text(texto, encoding="utf-8")
    typer.echo(texto)


@app.command()
def gerar(saida: Path = Path("dados/leads_sujos.csv"), n: int = 10_000, semente: int = 42) -> None:
    """Gera uma base sintética suja para demonstração."""
    from validador_leads.gerador import gerar as gerar_base

    saida.parent.mkdir(parents=True, exist_ok=True)
    df = gerar_base(n, semente)
    df.to_csv(saida, index=False)
    typer.echo(f"{len(df)} leads em {saida}")


if __name__ == "__main__":
    app()

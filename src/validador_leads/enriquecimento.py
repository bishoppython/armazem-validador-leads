"""Enriquecimento pelo site público da empresa, a partir do domínio do e-mail corporativo.

Lê só a página inicial: título, descrição e links públicos (inclusive o link para a página da
empresa no LinkedIn, sem visitá-la). Não raspa perfis de pessoas, o que viola os termos do
LinkedIn e é ponto sensível na LGPD.
"""

import logging
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

USER_AGENT = "validador-leads/0.1 (+https://github.com/bishoppython/armazem-validador-leads)"

Baixador = Callable[[str], str | None]


@dataclass(frozen=True)
class SiteEmpresa:
    dominio: str
    no_ar: bool
    titulo: str | None = None
    descricao: str | None = None
    linkedin: str | None = None
    instagram: str | None = None


def baixar(dominio: str, timeout: float = 8.0) -> str | None:
    for esquema in ("https", "http"):
        try:
            r = httpx.get(
                f"{esquema}://{dominio}", headers={"User-Agent": USER_AGENT}, timeout=timeout, follow_redirects=True
            )
        except httpx.HTTPError:
            continue
        if r.status_code < 400 and "html" in r.headers.get("content-type", "html"):
            return r.text
    return None


def extrair(dominio: str, html: str) -> SiteEmpresa:
    sopa = BeautifulSoup(html, "html.parser")
    titulo = sopa.title.get_text(strip=True) if sopa.title else None
    meta = sopa.find("meta", attrs={"name": "description"}) or sopa.find("meta", attrs={"property": "og:description"})
    descricao = str(meta.get("content") or "").strip() or None if meta else None
    links = [str(a.get("href") or "") for a in sopa.find_all("a")]
    linkedin = next((h for h in links if "linkedin.com/company/" in h), None)
    instagram = next((h for h in links if "instagram.com/" in h and "/p/" not in h), None)
    return SiteEmpresa(dominio, True, titulo, descricao, linkedin, instagram)


def enriquecer(dominios: Iterable[str], baixador: Baixador = baixar, paralelismo: int = 8) -> dict[str, SiteEmpresa]:
    """Uma visita por domínio, em paralelo."""
    unicos = sorted(set(dominios))

    def um(d: str) -> SiteEmpresa:
        html = baixador(d)
        return extrair(d, html) if html else SiteEmpresa(d, False)

    with ThreadPoolExecutor(paralelismo) as pool:
        resultado = dict(zip(unicos, pool.map(um, unicos), strict=True))
    log.info("sites: %d visitados, %d no ar", len(unicos), sum(s.no_ar for s in resultado.values()))
    return resultado

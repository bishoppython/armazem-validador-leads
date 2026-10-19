"""Verificação de registro MX com cache por domínio e consultas em paralelo."""

import logging
import threading
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor

import dns.exception
import dns.resolver

log = logging.getLogger(__name__)

Resolvedor = Callable[[str], bool]


def resolver_mx(dominio: str, timeout: float = 4.0) -> bool:
    """True se o domínio aceita e-mail (MX, ou A como fallback previsto na RFC 5321)."""
    r = dns.resolver.Resolver()
    r.lifetime = timeout
    try:
        return bool(r.resolve(dominio, "MX"))
    except (dns.resolver.NoAnswer, dns.resolver.NoNameservers):
        try:
            return bool(r.resolve(dominio, "A"))
        except dns.exception.DNSException:
            return False
    except dns.exception.DNSException:
        return False


class VerificadorMX:
    """Cada domínio é consultado uma única vez, mesmo com milhares de leads do mesmo provedor."""

    def __init__(self, resolvedor: Resolvedor = resolver_mx, paralelismo: int = 16) -> None:
        self._resolvedor = resolvedor
        self._paralelismo = paralelismo
        self._cache: dict[str, bool] = {}
        self._trava = threading.Lock()
        self.consultas = 0

    def verificar(self, dominios: Iterable[str]) -> dict[str, bool]:
        unicos = sorted(set(dominios))
        with self._trava:
            faltando = [d for d in unicos if d not in self._cache]
        if faltando:
            with ThreadPoolExecutor(self._paralelismo) as pool:
                for dominio, ok in zip(faltando, pool.map(self._resolvedor, faltando), strict=True):
                    with self._trava:
                        self._cache[dominio] = ok
            self.consultas += len(faltando)
            log.info("MX: %d domínios consultados, %d do cache", len(faltando), len(unicos) - len(faltando))
        return {d: self._cache[d] for d in unicos}

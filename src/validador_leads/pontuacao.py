"""Nota de 0 a 100 por lead, com o motivo de cada desconto."""

from dataclasses import dataclass, field

# Motivos que descartam o lead (não adianta contatar).
DESCARTE = ("email_ausente", "email_invalido", "email_descartavel", "dominio_sem_mx", "duplicado")

# Descontos sobre 100. Pensados para B2B: e-mail pessoal e caixa de função valem menos.
DESCONTOS = {
    "email_corrigido": 5,
    "email_pessoal": 20,
    "email_funcao": 10,
    "telefone_ausente": 15,
    "telefone_invalido": 15,
    "telefone_fixo": 5,
    "cnpj_ausente": 10,
    "cnpj_invalido": 20,
    "nome_ausente": 10,
    "empresa_ausente": 10,
    "site_fora_do_ar": 10,
}


@dataclass
class Avaliacao:
    motivos: list[str] = field(default_factory=list)

    @property
    def descartado(self) -> bool:
        return any(m in DESCARTE for m in self.motivos)

    @property
    def score(self) -> int:
        if self.descartado:
            return 0
        return max(0, 100 - sum(DESCONTOS.get(m, 0) for m in self.motivos))

    @property
    def faixa(self) -> str:
        if self.descartado:
            return "descartado"
        s = self.score
        return "A" if s >= 80 else "B" if s >= 60 else "C"

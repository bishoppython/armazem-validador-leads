# Validador de Leads — Armazém Agreste

[![ci](https://github.com/bishoppython/armazem-validador-leads/actions/workflows/ci.yml/badge.svg)](https://github.com/bishoppython/armazem-validador-leads/actions/workflows/ci.yml)

Recebe uma base de marketing bagunçada (CSV ou XLSX) e devolve a mesma base limpa: e-mails validados e corrigidos, telefones e CNPJs conferidos, duplicatas removidas e uma nota de 0 a 100 por lead, com o motivo de cada desconto.

**Problema de negócio:** disparar para uma base suja derruba a reputação do domínio de envio (bounce), gasta mensagens em quem não existe e manda a mesma oferta duas vezes para a mesma pessoa. Validar antes custa segundos.

Projeto 5 do portfólio **Armazém Agreste**. Todos os dados são sintéticos. Em produção, é a biblioteca de validação usada antes do disparo num serviço de prospecção B2B.

## Antes e depois: 10.600 leads sintéticos

`make demo` gera uma base suja de propósito (Faker pt_BR, semente fixa) e valida em cerca de 2 s.

| | Leads |
|---|---|
| Entrada | 10.600 |
| Válidos | 8.795 (83%) |
| Faixa A (score ≥ 80) | 6.575 |
| Faixa B (60–79) | 2.054 |
| Faixa C (< 60) | 166 |
| **Descartados** | **1.805** |

| Motivo do descarte | Leads |
|---|---|
| Duplicado (mesmo e-mail, ou mesmo nome + empresa) | 907 |
| E-mail com sintaxe inválida | 315 |
| Domínio sem MX | 314 |
| E-mail descartável (mailinator, yopmail…) | 269 |

Além disso, 415 e-mails tiveram o domínio corrigido (`gmial.com` → `gmail.com`) e 496 telefones foram marcados como inválidos. Relatório completo: [`exemplos/relatorio-10k.json`](exemplos/relatorio-10k.json). O resultado é reprodutível: a mesma semente gera a mesma base e a mesma saída em qualquer processo (há teste para isso).

O gerador injeta 6% de duplicatas exatas; o resto das 907 vem de pessoas com o mesmo nome na mesma empresa, mas com outro e-mail, que o Faker produz como numa base real.

## Etapas, da mais barata para a mais cara

| # | Etapa | Custo | Módulo |
|---|---|---|---|
| 1 | Normalização e sintaxe (caixa, espaços, `mailto:`) | local | `email.py` |
| 2 | Typo de provedor, domínio descartável, e-mail pessoal ou de função | local | `email.py`, `listas/` |
| 3 | Telefone (DDD válido, celular ou fixo) e CNPJ (dígitos verificadores) | local | `telefone.py`, `cnpj.py` |
| 4 | Deduplicação por e-mail normalizado e por nome + empresa | local | `pipeline.py` |
| 5 | Registro MX, com cache: **um domínio, uma consulta**, em paralelo | DNS | `dns_mx.py` |
| 6 | Site da empresa: título, descrição e link do LinkedIn da empresa (opcional) | HTTP | `enriquecimento.py` |
| 7 | Score de 0 a 100 + relatório com a contagem de cada motivo | local | `pontuacao.py` |

Cada etapa só roda para quem passou nas anteriores. A base de 10 mil leads tem cerca de 800 domínios distintos, então o MX faz cerca de 800 consultas, não 10 mil.

**Score:** começa em 100 e desconta por e-mail pessoal (−20), CNPJ inválido (−20), sem telefone (−15), caixa de função como `vendas@` (−10), sem CNPJ (−10), e assim por diante. Os pesos estão em [`pontuacao.py`](src/validador_leads/pontuacao.py) e foram pensados para venda B2B.

## Como rodar

```bash
uv sync --all-extras
make demo                                   # 10 mil leads sintéticos, MX simulado
uv run leads validar minha_base.csv -o limpa.csv --relatorio relatorio.json
uv run leads validar minha_base.xlsx --site --so-validos   # com enriquecimento pelo site
docker compose run --rm leads               # demo no Docker
```

As colunas são reconhecidas por nome (`nome`, `email`/`e-mail`, `telefone`/`celular`/`whatsapp`, `empresa`/`razao_social`, `cnpj`) e o separador do CSV é detectado sozinho.

Como biblioteca:

```python
from validador_leads import email, telefone

r = email.analisar("  Maria@GMIAL.com ")
r.email, r.corrigido, r.pessoal  # ('maria@gmail.com', True, True)
telefone.analisar("(81) 99876-5432").numero  # '5581998765432'
```

## LGPD

- **Base legal:** prospecção B2B costuma se apoiar no legítimo interesse (art. 7º, IX), o que exige finalidade clara, dado mínimo e opção fácil de sair. O validador ajuda nas duas primeiras: aponta dado que não serve e evita contato repetido.
- **Dado mínimo:** o enriquecimento usa só informação pública da **empresa** (site institucional). Não visita perfis de pessoas e não raspa o LinkedIn.
- **Descarte:** o que foi descartado não deve ser reaproveitado para outro fim. Use `--so-validos` para gravar só os leads aproveitáveis e apague a base bruta depois da validação.
- **Sem dado real neste repositório:** a base de demonstração é sintética, e os domínios corporativos usam o TLD reservado `.example` (RFC 2606), que nunca aponta para empresas reais.

Isto não é parecer jurídico; a base legal de cada campanha deve ser avaliada caso a caso.

## Decisões técnicas

- **`email-validator` + `dnspython`**, no lugar do `validate_email`, que está sem manutenção. Ver [ADR 0001](docs/adr/0001-validacao-sem-smtp-e-sem-raspar-linkedin.md).
- **Sem SMTP:** a porta 25 costuma ser bloqueada, domínios catch-all aceitam qualquer endereço e a sondagem pode pôr o IP em lista de bloqueio.
- **Não adivinhar:** o validador só corrige o que tem uma resposta certa. Espaço no meio do e-mail torna o endereço inválido, em vez de virar um palpite.
- **Demo offline:** com `--mx simulado`, os domínios `*.inativo.example` não têm MX e os outros têm. Com `--mx real` (o padrão), a consulta é DNS de verdade.

## Próximos passos

- Lista de domínios descartáveis atualizada automaticamente (hoje é uma amostra versionada de 40 domínios).
- Validação de CNPJ ativa na Receita (situação cadastral) com cache.
- Saída direto para o CRM do serviço de prospecção.

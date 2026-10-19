# ADR 0001 — email-validator + dnspython, sem SMTP por padrão e sem raspar LinkedIn

**Data:** 2026-10-19 · **Status:** aceito

## Contexto
O plano original pedia `validate_email` para os e-mails e BeautifulSoup para enriquecer com perfis do LinkedIn.

## Decisão
- **`email-validator` + `dnspython` no lugar de `validate_email`.** O pacote `validate_email` está sem manutenção há anos. O `email-validator` cuida da sintaxe (inclusive domínios internacionais e TLDs reservados) e a consulta de MX fica num módulo próprio, com cache por domínio e consultas em paralelo: uma base de 10 mil leads costuma ter poucas centenas de domínios.
- **Sem verificação SMTP.** Abrir conexão na porta 25 para perguntar se a caixa existe é bloqueado por muitos provedores, devolve falso positivo em domínios catch-all e pode pôr o IP de origem em lista de bloqueio. O pipeline para no MX.
- **Sem raspar o LinkedIn.** Raspar perfis viola os termos da plataforma e trata dado pessoal sem base legal clara. O enriquecimento lê só a página inicial pública do domínio corporativo do e-mail (título, descrição e o link para a página da empresa no LinkedIn, que não é visitada).
- **Não adivinhar.** O validador corrige só o que tem uma resposta certa: caixa, espaços nas pontas, `mailto:` e erros de digitação conhecidos em provedores (`gmial.com`). Espaço no meio do endereço torna o e-mail inválido, porque "joao silva@" pode ser `joaosilva`, `joao.silva` ou `joao_silva`.

## Consequências
- Validação offline e rápida (cerca de 2 s para 10 mil leads com MX simulado).
- Um e-mail aprovado ainda pode dar bounce se a caixa não existir; o score indica a qualidade, não garante entrega.

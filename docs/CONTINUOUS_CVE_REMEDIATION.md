# MrStore — ciclo contínuo de remediação de CVEs

## Critério de conclusão

O catálogo de **254 aplicações / 258 imagens** não pode ser declarado
seguro apenas porque os controlos de CI passaram. Uma CVE detetada continua
aberta enquanto não existir imagem corrigida e validada (ou uma análise de
risco explícita e documentada quando não existe correção a montante).
O objetivo é diminuir as ocorrências CRITICAL e HIGH observadas em AMD64
e ARM64, preservando volumes, configuração, credenciais e arquitetura real.

## Defeito corrigido: monitor de imagens fixadas por SHA256

O monitor anterior consultava a referência completa já fixada
por SHA256. Por definição, `crane digest vendor/app:tag@sha256:antigo`
tende a devolver o digest antigo, mesmo que `vendor/app:tag` já
tenha sido atualizado. Isso ocultava oportunidades de correção.

`scripts/updates.py` agora:
- valida a imagem original contra a baseline aprovada;
- consulta a tag *sem o sufixo SHA256* para descobrir o digest atual;
- não altera a baseline `data/image-digests.json`, nem com sucesso;
- grava os candidatos em `out/updates.json` e o instantâneo
  separado em `out/updates-live-digests.json`;
- reporta pedidos 429, erros de rede e fontes sem baseline como
  inconclusivos, nunca CVEs iguais a zero.

## Cobertura automática do catálogo inteiro

A workflow `.github/workflows/cve-remediation-sweep.yml` corre todos
os dias ou manualmente e divide as 258 referências Docker em oito
shards determinísticos, com concorrência reduzida.

Para cada imagem alterada desde o digest aprovado:
1. Confirma o digest atual na mesma tag/fornecedor (sem substituir origin).
2. Analisa com o scanner Trivy utilizado pelo catálogo as plataformas
   AMD64 e ARM64 efetivamente anunciadas.
3. Classifica a comparação de CRITICAL e HIGH por arquitetura.
4. Guarda JSON/Markdown por shard, incluindo erros e imagens sem alteração.
5. Abre/atualiza um issue de oportunidades de correção quando encontra
   reduções verificadas ou resultados inconclusivos.

Esta workflow **não** modifica instalações, não muda Compose, não altera
bases de dados, não cria exceções CVE e não fecha alertas por omissão.
Digests mais recentes não têm necessariamente menos vulnerabilidades
ou boa compatibilidade: continuam a exigir comparação, documentação
do fornecedor, testes de persistência, backup, rollback e PR específico
antes de integrar alterações.

## Auditoria CVE de referência

A workflow `.github/workflows/cve-scan.yml` mantém o scan diário completo
das imagens já instaláveis e a publicação da evidência por shard, com
falha real quando há CVEs altas/críticas ou scanners inconclusivos.

A automatização não pode garantir que todos os projetos publiquem
correções para todas as vulnerabilidades. As pendências sem correção,
o risco residual e os testes de execução que faltarem continuam visíveis.

## Comandos

- Identificar novas tags (sem alterar a baseline):
  `python scripts/updates.py --workers 2`
- Rever uma oitava parte das imagens:
  `python scripts/cve_remediation_sweep.py --shard 0 --shards 8`
- Validar os testes offline:
  `python -m unittest tests/test_updates_baseline.py tests/test_cve_remediation_sweep.py`

**Esta remediação é contínua, mas nunca deve promover automaticamente
uma imagem que ainda tenha evidência inconclusiva ou testes em falta.**

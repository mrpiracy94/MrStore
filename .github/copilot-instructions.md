# Instruções Copilot — MrStore

Projeto: catálogo de aplicações Docker com 254 definições em `Apps/`, publicação ZimaOS e adaptadores universais ainda em validação. Responder e documentar em português de Portugal.

## Regras obrigatórias
- Fazer **uma tarefa/issue por PR**. Procurar PRs e issues relacionados antes de editar; não duplicar trabalho.
- Nunca declarar apps, arquiteturas ou plataformas "certificadas" sem evidência de instalações e atualizações reais. Testes sintéticos/Compose/Helm não são certificação.
- Nunca remover/quarentenar apps apenas para tornar um relatório verde, suprimir CVEs ou tratar erro/timeout de scanner como "sem CVEs".
- Para publicação, manter auditoria de **HIGH e CRITICAL em AMD64 e ARM64**, digests imutáveis, cobertura completa, aprovação/quarentena e `release-status.json`.
- Nunca atualizar diretamente imagens de bases de dados/volumes, permissões privilegiadas, portas, dados persistentes ou instalações de produção sem plano explícito de backup, migração e rollback e aprovação humana.
- `scripts/validate.py`, `python -m unittest discover -s tests -v`, `scripts/compose_preflight.py` são a base de teste. Testar também caminhos de falha; apresentar logs/artefactos reais, não apenas "CI verde".
- Manter o catálogo, a homepage e o backend intactos quando a tarefa é de outro subsistema. Rebrand transversal: evitar alegar compatibilidade exclusiva ZimaOS no marketing, sem eliminar as integrações reais ZimaOS.
- Nunca fazer merge, publicar, fechar issues de segurança ou alterar secrets sem revisão. GitHub Actions e Renovate já existem; estender, não duplicar.
- Em PR: descrever problema, alterações, testes executados, testes ainda pendentes, riscos, evidência e passos de rollback.

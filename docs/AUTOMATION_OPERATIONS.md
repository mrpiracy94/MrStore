# Operações automáticas da MrStore

## Trabalho no PR
- `Validate MrStore` valida Compose, compatibilidade estática e testes Python.
- `Review risky app migrations` deteta mudanças de imagens de bases de dados, volumes, portas, credenciais, ID e arquiteturas; mudanças de risco elevado exigem `docs/upgrades/<app>.md` com **backup, migração, testes e rollback**.
- O workflow de publicação em PR (PR #50) faz análise completa AMD64/ARM64 e compilação ZimaOS v2 **sem publicar**.

## Publicação e quarentena
- `scripts/release_scan.py` obtém e analisa digests imutáveis de cada arquitetura declarada; consulta erros e CVEs HIGH/CRITICAL.
- `scripts/release_catalog.py` exige oito relatórios completos, exclui aplicações inseguras ou inconclusivas, preserva o motivo e gera `dist/release-status.json`.
- A alteração do catálogo público não desinstala containers. A ausência de alertas não comprova segurança nem funcionamento real no ZimaOS.

## Monitorização
- `MrStore public catalog uptime` consulta `store.json`, `index.json` e `release-status.json` de 6 em 6 horas. Se a publicação for inválida ou indisponível, cria ou atualiza um único issue; a verificação não altera containers nem o catálogo.
- `Curated new application discovery` verifica mensalmente `data/app-candidates.json` e propõe **issues**, nunca publica aplicações automaticamente.
- Renovate e os monitores existentes continuam a funcionar sem auto-merge de atualizações sensíveis.

## Evidência em hardware ZimaOS
As verificações GitHub Actions **não são** um teste real num NAS. Usar o modelo `ZimaOS device test` para registar arquitetura, versão ZimaOS, instalação, interface, login, dados persistentes, backup, migração e rollback num equipamento de ensaio. O issue #45 continua a acompanhar os testes C3 pendentes.

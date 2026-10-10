# Issue #64 — comparação verificável de imagens antigas

Esta investigação **não altera os manifests**. O workflow `Review stale Docker image candidates`
corre semanalmente ou por pedido, compara imagens imutáveis com Trivy separadamente
em AMD64 e ARM64 e guarda os achados HIGH/CRITICAL e os erros de registry.
Um resultado sem alertas **não** é autorização para substituir a imagem.

| App | Imagens analisadas | Condição para substituir |
| --- | --- | --- |
| Organizr | `organizr/organizr:latest` (atual), `ghcr.io/organizr/organizr:latest` (oficial), `anguy079/organizr:v2.7.2` (fork NÃO verificado) | Provar origem, manutenção, licenças, compatibilidade `/config`, scans limpos e instalação ZimaOS |
| Series Troxide | `lscr.io/linuxserver/series-troxide:latest` (atual) | Sem sucessor seguro comprovado. Trivy e testes funcionais obrigatórios; não remover `seccomp:unconfined` sem prova |
| Dockge | `louislam/dockge:1` (atual), `louislam/dockge:nightly` (instável) | A tag nightly NÃO é substituta automática da estável. Testar stacks, persistência, segurança e Docker Socket em NAS isolado |
| Immich/Postgres | Acompanhar issue #58 | Migração PostgreSQL 14→16 com backup, restore, VectorChord e rollback, nunca apenas troca de tag |
| SteamOS | Acompanhar PR #70 | Imagem oficialmente descontinuada; impedir nova publicação até alternativa segura |

## Critérios obrigatórios de aceitação

1. Confirmar upstream, origem/licença da imagem e manutenção ativa.
2. Provar digests imutáveis e zero HIGH/CRITICAL em **cada arquitetura declarada**, sem erros.
3. Ensaiar portas, login, volumes, dependências e persistência em instalação de teste.
4. Para Dockge, validar o controlo Docker daemon e isolamento: uma imagem recente não remove privilégios.
5. Só então propor o novo digest em PR individual, com rollback e evidência ZimaOS.

Resultados de comparação em artifacts `mrstore-maintenance-<app>` da Action.
CVEs não são resolvidas pela simples criação destes relatórios ou pela quarentena.

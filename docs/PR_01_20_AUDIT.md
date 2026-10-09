# Auditoria histórica — GitHub #1–#20 (2026-10-10)

**Âmbito:** verificar as primeiras 20 posições do historial GitHub. PR e issues usam a mesma sequência numérica. A numeração não corresponde a 20 pull requests.

| N.º | Tipo / estado observado | Resultado e próximo passo |
| --- | --- | --- |
| [#1](https://github.com/mrpiracy94/MrStore/pull/1) | PR fechada, sem merge | Renovate sugeriu Meilisearch 1.13.3 → 1.54.3 sem migração. Substituída por [#24](https://github.com/mrpiracy94/MrStore/pull/24), integrada com `--upgrade-db`, teste sintético de persistência e procedimento de backup. Falta prova de upgrade em ZimaOS real. |
| [#2](https://github.com/mrpiracy94/MrStore/pull/2) | PR integrada | Redis 7 → 8. A entrada Paperless atual usa Redis 8 Alpine, validada por teste de regressão e workflow específico. Sem validação de todos os dados reais. |
| #3–#4 | Não são PRs | Números usados por issues; não há PR a integrar. |
| [#5](https://github.com/mrpiracy94/MrStore/pull/5) | PR fechada, sem merge | PostgreSQL 14 → 16 no Immich exigia migração de dados ausente no Renovate. **Por resolver no runtime**, acompanhado em [issue #58](https://github.com/mrpiracy94/MrStore/issues/58). Não trocar tags diretamente. |
| [#6](https://github.com/mrpiracy94/MrStore/pull/6) | PR fechada, sem merge | Tag LinuxServer `20.04.1` inválida como upgrade de versão qBittorrent. Substituída por variante 5.2.4 libtorrent v1, imagem GHCR verificada em AMD64/ARM64 com digest imutável. Upgrade real 4→5 requer backup. |
| [#7](https://github.com/mrpiracy94/MrStore/pull/7) | PR integrada | Correção de ícones; testes `test_icon_assets.py` vigiam assets. |
| #8–#9 | Não são PRs | Números usados por issues. |
| [#10](https://github.com/mrpiracy94/MrStore/pull/10) | PR integrada | Auditoria CVE diária completa e Frigate sem `privileged` por omissão. Resultado estrutural não prova eliminação de CVEs. |
| #11 | Não é PR | Número usado por issue. |
| [#12](https://github.com/mrpiracy94/MrStore/pull/12) | PR integrada | Migração qBittorrent 4→5. A referência atual é GHCR, fixada por digest; confirmar backup para instalações anteriores. |
| [#13](https://github.com/mrpiracy94/MrStore/pull/13) | PR integrada | Actual Budget usa imagem GHCR oficial. |
| #14–#16 | Não são PRs | Números usados por issues. |
| [#17](https://github.com/mrpiracy94/MrStore/pull/17) | PR integrada | Concorrência da auditoria CVE: `push` pode cancelar runs obsoletos; agendamento e manual continuam separados. |
| [#18](https://github.com/mrpiracy94/MrStore/pull/18) | PR integrada | Publicação protegida de imagem qBittorrent AMD64/ARM64 com scans, sem alterar instalações. |
| #19–#20 | Não são PRs | Números usados por issues. |

## Conclusão auditável

- **10 PRs encontradas** no intervalo: **7 integradas**, **3 encerradas sem merge**, **0 abertas**.
- **10 números** correspondem a issues e não devem ser contados como PRs pendentes.
- **#1:** mudança de catálogo corrigida pela #24, mas migração num NAS real ainda não comprovada.
- **#5:** não resolvida enquanto migração e recuperação PostgreSQL 14→16 não forem demonstradas; issue #58 aberto.
- **#6:** upgrade Renovate errado descartado; substituição qBittorrent com digest verificado aplicada ao catálogo, mas upgrade real requer backup.
- Novos testes: `tests/test_historical_pr_01_20.py`, com restrições para impedir regressões de Meilisearch, PostgreSQL, qBittorrent, Actual Budget, Frigate e política de auditoria CVE.

## Limites dos testes

Os testes não instalam apps nem correm containers e **não reexecutam scans CVE de todas as imagens**. Os CI atuais e a política de publicação continuam responsáveis por Trivy e por compatibilidade estática. Não interpretar um workflow verde como migração real validada ou ausência total de vulnerabilidades.

# MrStore — catálogo inicial de 32 aplicações

Esta edição tem **32 candidatas** selecionadas editorialmente a partir das
**253 aplicações de origem**. Não é um ranking de downloads nem dados de
telemetria: são projetos conhecidos e úteis para tarefas típicas de homelab.

A lista editável é [`data/featured-apps.json`](../data/featured-apps.json).
É intencionalmente pequena para reduzir a complexidade da loja enquanto
estabilizamos as instalações, as atualizações, as integrações e as auditorias.

## Primeira seleção

| Grupo | Aplicações |
| --- | --- |
| Multimédia e fotos | Jellyfin, Plex, Immich, Audiobookshelf, Navidrome, Kavita, Calibre-Web |
| Downloads e organização | qBittorrent, Sonarr, Radarr, Prowlarr, Bazarr, Seerr, MeTube |
| Domótica e infraestrutura | Home Assistant, Dockge, Nginx Proxy Manager, Tailscale, Syncthing, Uptime Kuma |
| Produtividade | Nextcloud, Paperless-ngx, Actual Budget, Mealie, Stirling PDF |
| Desenvolvimento e IA | Gitea, Code Server, IT-Tools, Ollama, Open WebUI |
| Outros serviços | Homepage, Vaultwarden |

**32 candidatas** não quer dizer 32 publicadas: só entram na loja
as que passarem a auditoria Trivy de todas as arquiteturas declaradas,
o bloqueio de configurações inseguras, o pinning de imagens e as
verificações do builder ZimaOS. Se uma falhar, fica em **quarentena**,
não é substituída por outra nem apresentada como segura.

## O que acontece às outras 221?

Nada é apagado. As outras 221 definições mantêm-se em `Apps/`,
mas não são incluídas no release e a montra também não as apresenta.
O relatório `release-status.json` passa a distinguir:
- `approved`: candidatas seguras efetivamente publicadas;
- `quarantined`: candidatas rejeitadas pela política de segurança;
- `deferred`: projetos arquivados editorialmente para fases posteriores.

As auditorias atuais continuam a verificar a origem completa. Não há
mudança na política de zero CVE HIGH/CRITICAL das imagens publicadas,
nem nas verificações do Docker Compose e respetivos digests. O
ZimaOS v2 e o website recebem exatamente o mesmo conjunto publicado.

## Como aumentar o catálogo

Editar `data/featured-apps.json`, adicionando slugs existentes do
repositório, e abrir PR. Os testes rejeitam nomes duplicados ou
desconhecidos. A seleção adicional só chega a `gh-pages` depois
de completar o pipeline e passar todos os controlos de segurança.

Não atualizar `dist/`, `index.json` ou `gh-pages` manualmente.
Se o build falhar, a loja publicada conserva a última edição válida.

A futura loja multiplataforma deve usar o **mesmo conjunto aprovado**,
não a totalidade do arquivo de origem. A [PR #116](https://github.com/mrpiracy94/MrStore/pull/116)
deverá integrar este contrato quando voltar a estar pronta.

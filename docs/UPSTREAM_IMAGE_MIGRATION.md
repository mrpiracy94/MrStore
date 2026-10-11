# MrStore — proveniência oficial e redução verificável de CVEs

## Objetivo

Preservar as 254 aplicações, mas favorecer imagens mantidas pelo projeto
original **quando comprovadamente têm menos CVEs e uma migração compatível**.

LinuxServer.io é um fornecedor reputado de contentores, embora nem sempre
seja o fabricante original da aplicação. Uma imagem oficial pode continuar a
ter centenas de CVEs. Nem upstream, nem fixação SHA256 equivalem a segurança
certificada.

## Âmbito auditado

O comando python scripts/upstream_image_audit.py analisa todas as imagens do
catálogo Apps/ e distingue:
- third_party_linuxserver: mantidas pela LinuxServer.io;
- mrstore_rebuild: imagens personalizadas produzidas pela MrStore;
- publisher_not_verified: restantes imagens ainda sem atribuição formal de
  autoria (podem ser oficiais, mas o nome não chega para provar).

As candidatas com documentação do projeto ficam registadas em
data/upstream-candidates.json. A listagem completa das 254 aplicações não
sofre qualquer alteração nem a sua publicação é condicionada pelo comparador.

## Comparação reproduzível

O comando python scripts/upstream_image_audit.py --compare --app homeassistant
usa crane para resolver o SHA256 atual do candidato e Trivy para inspecionar
a mesma arquitetura da imagem atual, já fixada por digest no Compose.

A ferramenta marca redução apenas se as contagens de HIGH e CRITICAL
não aumentarem e pelo menos uma diminuir **em cada arquitetura anunciada**.
Erros, scanners incompletos ou arquiteturas ausentes nunca são tratados como
zero vulnerabilidades.

A workflow .github/workflows/upstream-image-comparison.yml produz um artefacto
JSON e Markdown por candidata, executado a pedido e às terças-feiras.
Não efetua instalações, merges, atualizações de manifestos ou deployments.

## Primeiros candidatos documentados

| Aplicação | Candidato do fornecedor original | Verificação obrigatória |
|---|---|---|
| Home Assistant | ghcr.io/home-assistant/home-assistant:stable | Rede, /config, permissões, dispositivos |
| qBittorrent | qbittorrentofficial/qbittorrent-nox:latest | Aviso legal, WebUI, portas, /config, shutdown |
| Nextcloud | nextcloud:apache | Volume /var/www/html, data e base de dados |
| Jellyfin | jellyfin/jellyfin:latest | Imagem custom, media paths, UID/GID, cache |

Fontes:
- https://www.home-assistant.io/installation/linux/
- https://github.com/qbittorrent/docker-qbittorrent-nox
- https://github.com/nextcloud/docker
- https://jellyfin.org/docs/general/installation/container/

## Condições para migração real

1. Validar origem do projeto, licença, manutenção e arquiteturas AMD64/ARM64.
2. Comparar relatórios Trivy no mesmo dia e arquivar versões/digests.
3. Criar Compose adaptado para novos volumes, permissões, portas e variáveis.
4. Confirmar backup, preservação de dados e reversão em ambiente isolado.
5. Testar instalação e atualização real por sistema, sem declarar
   compatibilidade universal com ZimaOS/UmbrelOS/CasaOS.
6. Só depois submeter migração individual para revisão com atualização de
   data/image-digests.json e dos testes de regressão.

**Estado desta fase:** apenas auditoria e pipeline de comparação. Não se
declara redução de CVEs sem resultado dos scanners e não foram modificados
os manifestos de produção ou contentores existentes.

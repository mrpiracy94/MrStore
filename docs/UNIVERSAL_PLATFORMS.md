# MrStore Universal — matriz de suporte e provas

Um catálogo central com 11 destinos **não equivale** a 11 integrações nativas
concluídas. Cada integração é independente, gerada apenas a partir de
`release-source` aprovado pelo processo de segurança, e a sua instalação e
atualizações devem ser validadas num sistema real.

| Plataforma | Forma de utilização | Estado em PR #116 |
| --- | --- | --- |
| ZimaOS | Loja v2 por URL | Existente, não alterada |
| Homeio | Importação de fonte ZIP CasaOS | ZIP experimental; testar versões reais |
| CasaOS | ZIP CasaOS / Compose | Pacote de origem experimental; não equivale ao sysroot v1 |
| umbrelOS | Community App Store via repositório Git | ZIP-semente de apps simples; sem repo Git dedicado |
| Cosmos | Importar Compose em ServApps | Compose aprovado por app, instalação real pendente |
| Portainer | App Templates v2 e Stacks Compose | Templates de contentor único + Compose por app |
| HomeDock OS | Packager HDS / bundle HDStore | Gerador de .hds e .hdstore, testes reais pendentes |
| Olares | Olares Application Chart v0.12.0 / Helm | Charts experimentais de apps simples, Market e runtime pendentes |
| Dockge | Stacks Docker Compose | Compose aprovado, instalação real pendente |
| Runtipi | Loja externa através de repositório Git | ZIP-semente Runtipi v4+, sem repo Git dedicado |
| Docker / Linux | docker compose | Manifesto auditado para importar manualmente |

## Artefactos — apenas depois de release aprovado

- `/store.json` + `/index.json`: catálogo ZimaOS v2.
- `/universal/catalog.json`: catálogo central e 11 perfis de instalação.
- `/universal/compose/<slug>.yml`: Docker Compose auditado por aplicação.
- `/universal/portainer-templates.json`: templates v2 de apps representáveis num contentor.
- `/store/casaos-homeio-preview.zip`: origem CasaOS/Homeio experimental.
- `/store/umbrel-community-preview.zip`: semente para um **repositório Git** Umbrel.
- `/store/runtipi-store-preview.zip`: semente para um **repositório Git** Runtipi.
- `/homedock/catalog.json`: mapa de pacotes elegíveis.
- `/homedock/<slug>.hds`: pacote nativo HomeDock por app.
- `/homedock/mrstore.hdstore`: bundle HomeDock.
- `/olares/catalog.json`: mapa de charts elegíveis.
- `/olares/<chart>.tgz`: OAC/Helm por app.
- `/olares/olares-oac-preview.zip`: árvore de charts para ensaios.

Os caminhos são relativos a `https://mrpiracy94.github.io/MrStore`,
mas **não existem garantidamente** enquanto a PR não for testada,
aprovada e publicada. Não usar um ZIP direto da branch main, porque
pode incluir aplicações em quarentena.

## HomeDock OS — HDS 1.0 e HDStore

O exportador próprio `scripts/export_homedock.py` gera `.hds` com
`manifest.json`, `icon.png`, `docker-compose.yml`,
`.hds_signature` e um bundle `.hdstore` com
`store_manifest.json`, os pacotes e `.hdstore_signature`.
O hash SHA-256 verifica **integridade**, mas **não autentica o publicador**.
Staks multi-serviço permanecem multi-serviço no Compose original.

**Atualizações:** o manifest `version` vem dos metadados de origem e
pode não mudar quando a imagem muda de digest; não se afirma suporte
automático a updates, rollback ou migrações antes de testar no HomeDock OS.
O utilizador deve inspecionar volumes, portas, segredos e compatibilidade
de arquitetura em máquina de ensaio.

Formato de referência:
https://github.com/BansheeTech/HomeDockOS/blob/main/pymodules/hd_HDSPackageManager.py

## Olares — OAC 0.12.0 e Helm

O exportador `scripts/export_olares_preview.py` cria
`Chart.yaml`, `OlaresManifest.yaml`, `values.yaml`,
`owners` e `templates/workload.yaml`, apenas se o Compose
for uma aplicação HTTP simples de contentor único, uma porta TCP,
sem segredos externos e com pastas apenas em
`/DATA/AppData/<slug>/...`. O armazenamento é ligado a
`.Values.userspace.appData`, valor injetado pelo Olares.

**Ainda falta:** validar `helm lint` e `helm template`, carregar no Olares
Studio, ensaiar instalação e atualização com dados de teste, e submeter um
chart aceite segundo o processo do Olares Market. Estes ficheiros não criam
magicamente uma loja externa nativa do Olares.

Especificação:
https://www.olares.com/docs/developer/develop/package/manifest

## Critérios de certificação por sistema e arquitetura

Antes de classificar uma app como compatível:

1. Verificar equivalência de serviços, imagens/digests, volumes, portas,
   arquitetura AMD64/ARM64 e mecanismos de atualização.
2. Importar o pacote num sistema **real de teste**, registando versão.
3. Instalar, validar UI e função principal, reiniciar e verificar dados.
4. Fazer backup, upgrade, ensaio de reversão/restauro e revalidar CVEs.
5. Guardar prova anonimizada por aplicação e plataforma; sem prova,
   apresentar *não verificado*.

Uma falha num adaptador opcional não desbloqueia apps em quarentena nem
permite publicar manifests não analisados. O catálogo ZimaOS deve continuar
independente do sucesso das pré-visualizações multiplataforma.

Referências:
- https://github.com/getumbrel/umbrel-community-app-store
- https://runtipi.io/docs/guides/create-your-own-app-store
- https://docs.portainer.io/user/docker/templates/custom
- https://docs.homedock.cloud/homedock-os/app-store/
- https://www.olares.com/docs/developer/develop/
- https://github.com/doctor-io/homeio

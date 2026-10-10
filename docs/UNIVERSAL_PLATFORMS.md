# MrStore Universal — 11 plataformas (matriz de suporte)

> **Objetivo:** encontrar, inspecionar e obter aplicações **aprovadas** da MrStore em
> todos os ecossistemas indicados. Suporte por Compose/importação **não** é o mesmo
> que uma loja externa integrada com instalação por um clique.

| Sistema | Método de distribuição | Estado atual |
|---|---|---|
| ZimaOS | Loja oficial v2 da MrStore | Catálogo existente, runtime por validar |
| Homeio | ZIP com Apps/ e x-casaos | Piloto PR #116; teste de importação real pendente |
| CasaOS | ZIP CasaOS/Compose | Piloto; ZIP atual não é pacote CasaOS legado v1 |
| umbrelOS | Community App Store num repositório Git dedicado | ZIP-semente experimental (subset restrito), instalação real pendente |
| Cosmos | Import Docker Compose em ServApps | Download Compose aprovado; testar importador |
| Portainer | App Templates v2 (apenas contentores simples) + Stacks Compose | JSON nativo para subset elegível; resto via Compose; testes reais pendentes |
| HomeDock OS | Packager a partir do Compose CasaOS | Download Compose aprovado; pacote .hds futuro |
| Olares | Olares Application Chart (Helm/OAC) | Adaptador e validação Kubernetes pendentes |
| Dockge | compose.yaml / stack | Download Compose aprovado; testar caminhos e volumes |
| Runtipi | Repositório Git custom App Store com x-runtipi | ZIP-semente experimental (subset restrito); testes reais pendentes |
| Docker / Linux | docker compose config / up | Download Compose aprovado; testes por app pendentes |

A geração \`scripts/export_portable_catalog.py\` recebe **somente**
\`release-source\` e \`out/release-selection.json\` do scanner Trivy em oito
shards. Reutiliza as verificações de \`scripts/export_universal.py\`.
Não existe exportação que faça fallback para os 254 manifests de origem.

Depois de um release aprovado e publicado:

- \`https://mrpiracy94.github.io/MrStore/universal/catalog.json\` — lista dos 11 destinos, métodos e apps aprovadas.
- \`https://mrpiracy94.github.io/MrStore/universal/compose/<slug>.yml\` — Compose por app, digest SHA256 da auditoria.
- \`https://mrpiracy94.github.io/MrStore/store/casaos-homeio-preview.zip\` — ZIP experimental (Homeio/CasaOS).
- \`https://mrpiracy94.github.io/MrStore\` — índice ZimaOS v2, mantido.

**IMPORTANTE:** os ZIP Umbrel/Runtipi **não** são URLs diretamente importáveis como loja: é necessário publicar o conteúdo num repositório Git separado e confirmar requisitos de cada app. Alguns serviços são excluídos por terem vários contentores, mounts de media, modos de rede ou recursos que não podemos converter sem riscos. A ausência de ZIP significa que não houve candidatos seguros nessa edição.

**Atenção:** ficheiros Compose podem conter caminhos \`/DATA/*\`, portas
ocupadas ou serviços dependentes de dispositivos. Antes de instalar,
adaptar os volumes, verificar permissões, portas, segredos e arquitetura.
\`docker compose config\` analisa sintaxe e interpolação, **não** comprova
segurança operacional nem ausência de CVEs.

## Critérios para declarar suporte nativo

Cada integração terá de passar:
1. exportador com formato documentado para a versão alvo;
2. validador de estrutura e referências a imagens aprovadas;
3. importação num dispositivo/VM real com versão e arquitetura registadas;
4. instalação, ligação à UI, persistência, upgrade, backup e recuperação;
5. bloqueio de publicação dessa integração se algum critério falhar.

Documentação consultada:
- https://github.com/getumbrel/umbrel-community-app-store
- https://runtipi.io/docs/guides/create-your-own-app-store
- https://docs.portainer.io/user/docker/templates/custom
- https://cosmos-cloud.io/docs/servapps/
- https://docs.homedock.cloud/homedock-os/app-store/
- https://www.olares.com/docs/developer/develop/
- https://github.com/louislam/dockge
- https://github.com/doctor-io/homeio

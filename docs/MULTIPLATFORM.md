# MrStore — compatibilidade multiplataforma

A fonte única continua a ser **Apps/** (254 aplicações). A presença no catálogo não significa instalação funcional nem segurança CVE certificada.

| Sistema | Formato | Estado |
| --- | --- | --- |
| ZimaOS | App Store v2 | Integração técnica existente; validar cada app em dispositivo |
| CasaOS | Arquivo ZIP v1 | Exportação piloto de 2 aplicações |
| Homeio | Arquivo ZIP compatível com CasaOS | Exportação piloto de 2 aplicações; testar paths |
| UmbrelOS | Repositório Git com umbrel-app-store.yml | Estrutura e pacotes piloto exportáveis; não publicados como loja nativa |
| Docker, Portainer, Dockge | Docker Compose | Ficheiros piloto exportáveis; instalação manual |
| Cosmos, HomeDock OS, Olares, Runtipi | Adaptadores futuros | Não afirmar suporte nativo até implementar e testar |

## Geração de pacotes

```bash
python -m pip install -r requirements.txt
python scripts/platform_export.py --platform all --output out/platforms
python -m unittest discover -s tests -p 'test_platform_export.py' -v
```

A saída produz **compatibility.json** para todas as aplicações, ZIPs de CasaOS/Homeio, ficheiros Docker e a estrutura de um repositório comunitário Umbrel.
A escolha explícita dos pilotos fica em **data/platform-pilots.json**, inicialmente IT-Tools e Uptime Kuma. O catálogo web mantém os 254 registos.

## Instalação de testes

**CasaOS:** após o workflow completo de publicação na main, abrir App Store → Add Source e usar:

https://mrpiracy94.github.io/MrStore/platforms/mrstore-casaos.zip

**Homeio:** abrir App Store → Manage Sources e, após publicação, usar:

https://mrpiracy94.github.io/MrStore/platforms/mrstore-homeio.zip

Os dois endereços só existem após publicação bem-sucedida do workflow que os gera. Não assumir disponibilidade antecipada. No Homeio, verificar se os mounts em /DATA/AppData são adequados ao host.

**UmbrelOS:** copiar apenas o conteúdo de out/platforms/umbrel/ para a raiz de um **repositório Git próprio**. O Umbrel necessita da URL do repositório que contenha umbrel-app-store.yml na raiz e pastas de apps com o ID prefixado por mrstore-. Não usar o URL da branch main da MrStore como loja Umbrel.

**Docker / Portainer / Dockge:** importar o Compose gerado, verificar volumes relativos em ./data, rede, permissões e credenciais antes de iniciar.

## Portabilidade e segurança

- O exportador apenas analisa YAML e escreve pacotes, sem executar contentores ou obter segredos.
- Bloqueia privilégios elevados, Docker socket, namespaces do host, mounts fora de /DATA/AppData/<app>, imagens flutuantes, credenciais estáticas e dependências não adaptadas.
- As imagens exportadas são fixadas a digests SHA-256 constantes no inventário. Isto não significa que a análise de CVEs esteja limpa.
- Umbrel usa app_proxy e APP_DATA_DIR, sem expor diretamente a porta web do Compose original.
- As classificações pilot_exportable, review_required e blocked são **estáticas**, nunca prova de instalação real.
- Cada app e plataforma exigem testes de importação, arquitetura, credenciais, persistência, reinício, atualização, reversão e desinstalação.
- Para criar novos pilotos, rever primeiro a configuração, os avisos de segurança e os digests, só depois adicionar o slug a data/platform-pilots.json.

## Documentação técnica

- Umbrel Community App Store: https://github.com/getumbrel/umbrel-community-app-store
- CasaOS ZIP stores: https://awesome.casaos.io/content/3rd-party-app-stores/create-your-first-custom-appstore.html
- Homeio: https://github.com/doctor-io/homeio
- ZimaOS v2: https://github.com/IceWhaleTech/CasaOS-AppStore
- Guias de segurança: docs/SAFE_RELEASE_POLICY.md, docs/ZIMAOS_COMPATIBILITY.md

**Nota:** não anunciar compatibilidade nativa global enquanto não houver integração e evidência por dispositivo.

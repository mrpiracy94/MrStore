# Segurança da loja MrStore (S01–S07)

O destino destas correções é **o código GitHub da MrStore** e a publicação do catálogo
para ZimaOS v2. Não há instaladores Windows e não é efetuada qualquer modificação
na máquina de quem instala.

## Melhorias efetivas no catálogo

- **Dozzle (S02):** API Docker mediada por um socket-proxy em rede Docker interna,
  sem porta pública; Dozzle recebe \`DOZZLE_REMOTE_HOST\` e não monta o socket.
  O proxy limita endpoints e permite apenas GET/HEAD. Risco residual: o proxy
  conserva acesso ao socket; proteger também a interface Dozzle na rede.
- **Netdata (S02):** removida a montagem do socket Docker. Isto reduz acesso ao
  daemon, mas implica perder a integração de métricas Docker dependente do socket.
- **CI (S05):** actions críticas fixadas a SHA. Rever atualizações destes SHAs
  através de PRs, não usar tags móveis inadvertidamente.
- **Publicação (S06):** após staging editorial e antes do build oficial, todas
  as imagens são fixadas aos digests em \`data/image-digests.json\`. O script
  aborta a publicação inteira se faltar um digest, se existir divergência ou se
  não for possível verificar todas as linhas \`image:\`. Não remove aplicações.
- **CI (S07):** o evento \`pull_request\` usa job de testes sem token Copilot e
  apenas \`contents: read\`. Escrita em issues é reservada ao job de queue.

## Riscos ainda não resolvidos automaticamente

- **Kasm (S01):** LinuxServer.io exige \`privileged: true\` para Docker-in-Docker.
  Não é seguro removê-lo sem trocar a arquitetura. Instalar só numa VM/host
  isolado e com administração privada.
- **Dockge (S02):** gerencia contentores e exige acesso de escrita ao daemon;
  socket-proxy apenas GET/HEAD quebraria o serviço. A instância deve estar
  numa rede administrativa com autenticação.
- **Credenciais (S03):** \`CHANGE_ME\` nos manifests editoriais não é seguro
  para instalar tal e qual. O instalador verificado do ZimaOS v2 não suporta
  universalmente \`\${VAR:?}\` para pedir os segredos. Não foram inventadas
  passwords nem introduzidas variáveis que causariam falhas de instalação.
  A seleção auditada continua a bloquear estas configurações; instalações
  destes serviços requerem configuração individual de segredos.
- **Portas (S04):** o repositório não conhece o IP da LAN de cada NAS.
  Substituir todas as portas por \`127.0.0.1\` inutilizaria o acesso nativo
  no ZimaOS. Restringir por firewall/VPN/proxy autenticado antes de expor
  interfaces administrativas à Internet.

## Distinção de segurança

A loja editorial lista todos os manifests com \`certification: not_assessed\`;
**a fixação de digests NÃO garante ausência de CVEs**. O workflow auditado
é independente, com quarentena e verificação Trivy por arquitetura.
Os hashes na baseline são históricos e devem ser renovados/revistos regularmente.

## Testar antes de promover

\`\`\`sh
python -m unittest discover -s tests -p 'test_pin_editorial_images.py' -v
python -m unittest discover -s tests -v
python scripts/validate.py
\`\`\`

Testar em ZimaOS v2 o arranque Dozzle, os logs, a disponibilidade LAN da
interface, e o build de todas as apps. Uma alteração ao repositório não
atualiza automaticamente contentores já instalados. Fazer backup antes de
qualquer redeploy. Nunca usar \`docker compose down -v\` como reversão.

Referências:
- https://dozzle.dev/guide/remote-hosts
- https://docs.linuxserver.io/images/docker-socket-proxy/
- https://docs.linuxserver.io/images/docker-kasm/

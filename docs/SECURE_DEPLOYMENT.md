# Instalação segura — credenciais e acesso ao host

> Alteração de segurança para revisão; não é prova de compatibilidade operacional no ZimaOS.

## Segredos obrigatórios, sem valores públicos

Os manifestos afetados usam a expansão Docker Compose `${NOME:?Set NOME before deployment}`. Quando a variável estiver **ausente ou vazia**, `docker compose config` falha antes de criar containers. Isto evita iniciar com valores públicos `CHANGE_ME`, mas **não verifica entropia, formato ou reutilização** de um valor não vazio. Configurar valores únicos, fortes e privados em cada instalação. Nunca escrever credenciais em ficheiros versionados, issues ou logs.

| App | Variáveis a definir no ambiente Compose |
| --- | --- |
| BookStack | `BOOKSTACK_APP_KEY`, `BOOKSTACK_DB_HOST`, `BOOKSTACK_DB_PASSWORD` |
| Cloudflared | `CLOUDFLARED_TUNNEL_TOKEN` |
| DuckDNS | `DUCKDNS_TOKEN` |
| Frigate | `FRIGATE_RTSP_PASSWORD` |
| Gluetun | `GLUETUN_VPN_SERVICE_PROVIDER`, `GLUETUN_WIREGUARD_PRIVATE_KEY` |
| Healthchecks | `HEALTHCHECKS_SUPERUSER_PASSWORD` |
| HedgeDoc | `HEDGEDOC_DB_PASSWORD` |
| Homarr | `HOMARR_SECRET_ENCRYPTION_KEY` |
| Immich | `IMMICH_DB_PASSWORD` (partilhada entre servidor e PostgreSQL) |
| Karakeep | `KARAKEEP_NEXTAUTH_SECRET`, `KARAKEEP_MEILI_MASTER_KEY` (esta última partilhada entre serviços) |
| Kimai | `KIMAI_ADMIN_PASSWORD` |
| LLDAP | `LLDAP_JWT_SECRET`, `LLDAP_KEY_SEED`, `LLDAP_LDAP_USER_PASS` |
| MariaDB | `MARIADB_ROOT_PASSWORD` |
| NetBox | `NETBOX_SUPERUSER_PASSWORD`, `NETBOX_DB_PASSWORD` |
| Paperless-ngx | `PAPERLESS_SECRET_KEY` |
| PhotoPrism | `PHOTOPRISM_ADMIN_PASSWORD` |
| Planka | `PLANKA_SECRET_KEY` |
| Speedtest Tracker | `SPEEDTEST_TRACKER_APP_KEY` |
| Tailscale | `TAILSCALE_AUTHKEY` |


Em BookStack, a base de dados MariaDB/MySQL **não está incluída** no Compose; é preciso configurar uma base de dados existente, gerar `APP_KEY` com formato compatível com Laravel e definir `APP_URL` corretamente. Em Homarr, a chave deve ser hexadecimal de 64 caracteres (por exemplo, gerada localmente com `openssl rand -hex 32`). Em Speedtest Tracker, `SPEEDTEST_TRACKER_APP_KEY` deve conter **todo** o valor `base64:...` de uma chave Laravel válida; não basta fornecer uma string aleatória. Em Gluetun, `GLUETUN_VPN_SERVICE_PROVIDER` é uma configuração obrigatória, não um segredo.

Exemplo local sem publicar credenciais (a partir da raiz do repositório):

```bash
# Criar um ficheiro privado (ignorado pelo Git) e preencher manualmente as variáveis.
umask 077
${EDITOR:-vi} Apps/immich/.env
docker compose --env-file Apps/immich/.env -f Apps/immich/docker-compose.yml config --quiet
```

O comando `config --quiet` só valida a configuração; não inicia containers. Para outras apps, criar o ficheiro `.env` respetivo e introduzir as variáveis da tabela. **Nunca confirmar/guardar `.env` no GitHub.**

### Limitação confirmada do builder ZimaOS v2

O código oficial do builder `IceWhaleTech/build-appstore-action` executa
`split_compose` e **elimina `services.*.x-casaos`**, incluindo
`x-casaos.envs`. Logo, os campos editáveis do manifesto de origem **não
garantem um formulário de credenciais na loja v2**. A secção
`x-casaos.tips.before_install` de topo, entretanto adicionada às 19 apps
afetadas, sobrevive à compilação como metadados `meta.json` (inclui
`en_US` e `pt_PT`) e avisa o utilizador. Este aviso **não é uma barreira
técnica à instalação**, nem prova que uma determinada versão da interface
ZimaOS o apresente.

As expressões `\${VAR:?mensagem}` continuam no Compose, obrigando a
disponibilizar a variável ao motor **antes** da interpolação. O teste de
CI `scripts/check_required_secrets.py` executa o Docker Compose com
credenciais sintéticas: confirma que cada aplicação aceita valores não vazios
e falha quando qualquer variável requerida estiver ausente ou vazia.
Nunca faz `up`, `pull`, `build` nem executa containers. Isto **não
testa o instalador ZimaOS**.

O workflow de publicação verifica também, **depois do builder oficial**, que os ficheiros v2 preservam as expressões obrigatórias e incluem os avisos pré-instalação em `meta.json`, através de `scripts/verify_installer_payload.py`. Isto verifica o catálogo gerado, não o instalador real.\n\nA publicação destas alterações permanece bloqueada até se observar
num ZimaOS real que os segredos são pedidos/configurados e chegam ao
Docker Compose **antes** da expansão. Uma opção é configurar as
variáveis manualmente num fluxo aprovado do ZimaOS; não pressupor
que os campos do serviço estejam disponíveis na loja v2.

Referências: [builder oficial](https://github.com/IceWhaleTech/build-appstore-action/blob/main/scripts/build_appstore.py),
[formato v2 e tips](https://github.com/IceWhaleTech/CasaOS-AppStore/blob/main/docs/specs/compose-and-x-casaos.md),
[interpolação Docker Compose](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation).

## Acesso ao Docker socket

O socket `/var/run/docker.sock` permite acesso de elevado privilégio ao daemon Docker; marcar um bind como `read_only` **não** restringe os métodos da API. Para reduzir o acesso por omissão, foram removidas as montagens diretas de **Homarr, Homepage, Glances e Netdata**. Estas aplicações mantêm a interface principal, mas perdem integração/estatísticas Docker até se configurar um proxy com permissões efetivamente limitadas e sem API mutável.

Permanecem três exceções explícitas que requerem decisão administrativa antes da instalação: **Dockge** (controla stacks), **Dozzle** (recolhe logs Docker) e **Socket Proxy** (intermediário do daemon). Não devem ser consideradas seguras apenas por terem o socket montado como `read_only`; isolar a máquina, controlar o acesso e reduzir os endpoints permitidos no proxy. Dockge requer operações de escrita para a sua função central.

## Kasm — exceção a privilégios mínimos

`lscr.io/linuxserver/kasm` executa Docker-in-Docker e a documentação oficial exige `privileged: true`. Remover esta flag sem mudança de arquitetura não é uma correção funcional. **Não instalar Kasm num NAS partilhado, em produção ou com outros dados sensíveis**, a menos que o administrador aceite expressamente o risco e disponha de isolamento adequado. A exceção continua a aparecer na auditoria até existir uma alternativa testada sem privilégios elevados.

Referências: [LinuxServer Kasm](https://docs.linuxserver.io/images/docker-kasm/), [OWASP Docker Security](https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html), [ZimaOS Compose e x-casaos](https://github.com/IceWhaleTech/CasaOS-AppStore/blob/main/docs/specs/compose-and-x-casaos.md).

## Aceitação antes de integrar a PR

1. Verificar os 254 manifestos no CI e a ausência de `CHANGE_ME` em valores de ambiente ativos.
2. Confirmar que cada app com `${VAR:?}` falha sem configuração e passa com valores de teste não reais.
3. Confirmar no builder ZimaOS que as variáveis obrigatórias não são substituídas por segredos de CI nem publicadas com defaults inseguros.
4. Testar instalação e arranque num ZimaOS de teste, incluindo persistência e reinício, sem segredos reais.
5. Rever as três exposições restantes ao Docker socket e a exceção `privileged` de Kasm antes da utilização.

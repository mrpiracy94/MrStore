# Docker Socket Proxy — proteção de escrita e acesso

O serviço `Apps/socket-proxy` continua a montar `/var/run/docker.sock` porque a sua função é ler a API do daemon Docker. `read_only: true` num bind **não torna a API imutável**. A segurança exige a configuração operacional `POST=0` e os flags `ALLOW_*=0` de forma explícita; o upstream documenta que, quando `POST=0`, apenas métodos GET/HEAD são permitidos, mas `ALLOW_START/STOP/RESTARTS` conseguem permitir exceções e por isso são fixados em 0.

O serviço não publica a porta TCP 2375 no NAS; encontra-se apenas numa rede Docker privada. A opção `read_only` do sistema de ficheiros, `tmpfs: /run` e `no-new-privileges` reduzem a superfície de ataque. A execução de teste em Actions confirma resposta à leitura `GET /containers/json` e negação de criação de containers via `POST /containers/create` (HTTP 403).

**Risco residual:** o Socket Proxy ainda é um intermédio privilegiado, e o controlo GET/HEAD não substitui autenticação, isolamento de rede nem revisão de CVEs. O Dozzle e o Dockge continuam com montagens próprias e devem ser remediados separadamente. Nunca publicar o TCP 2375 na LAN/Internet sem controlo de acesso.

Fonte oficial: https://docs.linuxserver.io/images/docker-socket-proxy/

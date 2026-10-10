# Segurança dos bind mounts Docker — issue #53

O bloqueio de novas configurações perigosas na MrStore usa agora
`sensitive_host_bind`, que normaliza caminhos absolutos e reconhece
montagens de ficheiros sensíveis, diretórios superiores e sockets
alternativos como `/run/user/1000/docker.sock`.

Exemplos bloqueados na revisão de PRs:
- `/var/run/docker.sock`, `/run/docker.sock`, `/var/run` e `/var`;
- `/var/lib/docker`, `/var/lib/docker/containers` e diretórios superiores;
- `/run/containerd/containerd.sock` e sockets `docker.sock` alternativos;
- `/root/.ssh`, `/proc/1/root`, `/sys/kernel` e `/dev/kmsg`;
- grafias com barras redundantes e componentes `..` normalizados.

Volumes persistentes de aplicações em `/DATA/...` e o ficheiro
`/etc/localtime` continuam permitidos. Não foram modificados containers,
volumes, credenciais nem manifestos existentes. Os riscos legados continuam
nos relatórios e podem ser colocados em quarentena; não são remediados
apenas por adicionar esta verificação.

A revisão regressiva compara o estado atual com a base Git, bloqueando
**novas** exposições sem remover silenciosamente funcionalidades.
O seletor de publicação `scripts/release_catalog.py` reutiliza **a mesma
política de caminhos**. Isto é independente da comparação com a branch base:
mesmo um bind perigoso antigo, ou montado `:ro`, mantém a aplicação em
quarentena. As montagens nomeadas (`type: volume`), `/etc/localtime` e
`/DATA/AppData/...` não são indevidamente bloqueadas por esta regra.
O bloqueio é por aplicação e não elimina nenhum manifesto de origem.

Os PRs #69 (Socket Proxy) e #75 (Dozzle) tratam correções concretas
dos serviços, separadamente deste bloqueio geral. Kasm e Dockge
continuam a exigir isolamento de host e testes funcionais ZimaOS.

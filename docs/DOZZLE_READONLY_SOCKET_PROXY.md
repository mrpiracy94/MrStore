# Dozzle: Docker API só de leitura

O serviço `dozzle-web` conserva a UI na porta externa **30011** e deixa de montar `docker.sock`. O serviço `dozzle` passa a ser o Socket Proxy LinuxServer, numa rede Docker `internal: true` sem portas de host. O socket físico mantém-se no proxy, não no frontend. `POST=0` e `ALLOW_START/STOP/RESTARTS=0` proíbem operações de escrita; `ALLOW_LOGS=1` é estritamente necessário para permitir o GET dos logs após a atualização upstream de agosto de 2026.

O bind `:ro` não é, por si só, uma proteção eficaz para a Docker API: a verificação em CI exige `GET /containers/json` funcionar, `POST /containers/create` devolver 403 e Dozzle arrancar com UI acessível. O proxy continua a ter acesso privilegiado ao socket e a app permanece sujeita à auditoria de vulnerabilidades de imagem. Sem NAS de ensaio, não se declara compatibilidade ZimaOS real.

Referências: https://dozzle.dev/guide/remote-hosts e https://docs.linuxserver.io/images/docker-socket-proxy/.

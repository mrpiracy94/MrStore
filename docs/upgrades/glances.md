# Glances — atualização de imagem oficial com menor contagem CVE

## Evidência CVE
Mantém-se `nicolargo/glances:latest-full`, digest anterior
`sha256:2a7f42503f165c5a50fc3f88f820517e2bd905447ddf578e44bee7db3b52821c`
e novo digest
`sha256:411fb0d71198c414d82756dac2b9c330a6ff490e3722227d583374c33f7370f8`.
Scanner Trivy em 2026-10-11: 2 CRITICAL / 19 HIGH -> 1 CRITICAL /
13 HIGH em AMD64 e ARM64. A imagem nova **continua a ter** vulnerabilidades.
Relatório: https://github.com/mrpiracy94/MrStore/actions/runs/38172909540/job/114569104826

## Backup
Guardar o Compose e quaisquer ficheiros de configuração ligados ao serviço;
registar o digest anterior e as definições de firewall e acesso LAN.

## Migração
Troca apenas de SHA256 da mesma imagem e tag. A porta web 61208,
`GLANCES_OPT=-w` e as permissões mantêm-se sem alteração.
Não acrescentar docker.sock nem permissões privilegiadas. Testar API/UI
da nova imagem e ligação a métricas de CPU, memória e armazenamento.

## Testes
O scan multi-arquitetura foi concluído. O teste funcional em equipamento
real está pendente: abrir dashboard, consultar métricas, reiniciar e verificar
acesso autenticado/rede privada. A publicação não é certificação de ZimaOS.

## Rollback
Parar a imagem, restaurar o Compose/digest antigo e eventual configuração
guardada; não eliminar dados do sistema.

# FreshRSS — atualização de digest com menos CVEs (2026-10-11)

## Evidência
A origem mantém-se `lscr.io/linuxserver/freshrss:latest` (LinuxServer.io).
Digest anterior: `sha256:bd13d4a611959bad42bd79965d3202c518494bd775be4a0f61e4b81098b18b01`.
Digest proposto: `sha256:d5a11c52ba6987702e899c2c3831946eb959b54af34db96b1fe41194286acfb2`.
No Trivy AMD64 e ARM64, 0 CRITICAL/9 HIGH passou para 0 CRITICAL/0 HIGH.

Relatório: https://github.com/mrpiracy94/MrStore/actions/runs/38172909540/job/114569104861

## Backup
Antes de atualizar, guardar `/DATA/AppData/freshrss/config`, exportar
feeds e definições FreshRSS; se for usada uma base de dados externa,
fazer também um dump consistente com hipótese de restauro testada.
Guardar Compose e digest antigo.

## Migração
Alteração exclusiva de digest da mesma tag e fornecedor. Mantidos
`PUID=1000`, `PGID=1000`, `TZ=Europe/Lisbon`, porta publicada 20032
e volume `/config`. Embora preserve a configuração do Compose, não
se assume que o conteúdo da imagem não tenha migrado esquemas internos.
Validar versão de PHP, extensões e compatibilidade da base de dados antes
de substituir uma instalação com dados.

## Testes
A CI valida YAML e digests, e a análise CVE foi feita nas duas arquiteturas.
No NAS de ensaio, testar login, atualização de feeds, utilizadores, cron e
persistência após reinício. Estes testes de execução ainda não foram
confirmados no hardware final.

## Rollback
Parar o contentor, restaurar Compose com digest anterior e reverter
configuração/DB a partir de backup se uma migração interna a tiver alterado.
Não apagar volume `/config` nem feeds do utilizador.

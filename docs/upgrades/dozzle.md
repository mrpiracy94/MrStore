# Dozzle — plano de migração de Docker socket para proxy restrito

## Backup
Antes de atualizar o Compose num NAS ZimaOS v2, exportar a versão atual
e a configuração de qualquer proxy, firewall e autenticação existente.
O Dozzle apresenta logs de outros serviços: guardar os logs importantes fora
da aplicação. Nunca copiar o socket Docker para backups nem publicar logs
que possam conter tokens.

## Migração
A interface Dozzle deixa de montar diretamente /var/run/docker.sock.
O novo serviço dozzle-socket-proxy monta o socket read_only, com POST=0,
sem porta publicada e apenas na rede Docker interna docker-api. A
interface passa a usar DOZZLE_REMOTE_HOST=tcp://dozzle-socket-proxy:2375.
Mantém-se a porta 30011 da UI para acesso LAN ZimaOS, que exige firewall.
As imagens são fixadas a digests da baseline de 11-10-2026; verificar a
disponibilidade multi-arquitetura antes de atualizar sistemas ARM.
Isto NAO retira o risco residual: o proxy tem socket, embora limite a API.
Nao ha migração de volumes de dados, mas a nova topologia de rede exige teste.

## Testes
Num NAS/VM ZimaOS de ensaio, executar a verificacao Compose e validar:
arranque de ambos os serviços, lista de contentores, stream de logs, eventos,
filtros e reconexão. Confirmar que nenhum serviço do LAN consegue aceder
ao proxy pela porta 2375, que o proxy nao expõe portas ao host, e que
endpoints POST/EXEC/SECRETS ficam negados. Confirmar acesso UI com autenticação
e firewall. Estes testes funcionais AINDA NAO foram executados.

## Rollback
Se os testes falharem, restaurar o Compose antigo com cópia de segurança
e fazer redeploy SEM destruir volumes. Confirmar que o Dozzle volta a apresentar
os logs e que não restou proxy exposto nem rede órfã. Este rollback devolve
o risco anterior de socket direto; enquanto nao for resolvido, limitar
o acesso administrativo ao NAS.

## Estado
Plano de migração e rollback obrigatório para revisão. Não certifica a
compatibilidade funcional nem autoriza publicação sem os testes.

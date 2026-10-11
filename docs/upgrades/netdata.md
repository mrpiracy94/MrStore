# Netdata — remoção da montagem direta do Docker socket

## Backup
Guardar o Compose anterior e fazer backup de /DATA/AppData/netdata, bem como
os ficheiros de configuracao sob /etc/netdata, /var/lib/netdata e cache quando
persistentes. Confirmar que o backup é legível e preservar o volume do serviço.

## Migração
Remover o bind /var/run/docker.sock do serviço Netdata. Isto reduz o acesso
privilegiado ao Docker daemon, mas pode interromper a recolha de métricas
detalhadas de contentores Docker. A monitorização de CPU, disco, memória e
outros sensores sem dependência do socket deve continuar. Não migrar ou
reescrever bases de dados do Netdata; não executar Docker automaticamente.

## Testes
Num ZimaOS de teste, verificar o arranque da UI, dashboard, métricas de host,
alertas, persistência e reinício. Confirmar a AUSÊNCIA de acesso ao socket
Docker e anotar os gráficos de contentores que deixam de existir. Caso as
métricas Docker sejam indispensáveis, estudar integração com um proxy GET-only
com endpoints mínimos e testes adicionais, em vez de voltar ao socket direto.
Estes testes funcionais ainda não foram executados.

## Rollback
Se as métricas em falta forem operacionalmente impeditivas, restaurar o
Compose e a configuração anterior, sem remover volumes nem dados persistentes.
Validar a monitorização e deixar explícito que o rollback restaura o risco
anterior de acesso à API Docker até existir uma alternativa testada.

## Estado
Mudança de segurança com degradação funcional documentada. Testes e rollback
necessários antes de publicar.

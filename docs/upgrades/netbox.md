# NetBox — plano de upgrade e segurança

## Backup
Antes de modificar a instalação, parar o serviço e guardar o Compose anterior e a pasta /DATA/AppData/netbox/config. Fazer backup consistente da base de dados PostgreSQL existente e do Redis se armazenar estado relevante. Preservar as credenciais num gestor de segredos, nunca num issue público.

## Migração
O novo manifesto não altera a imagem Docker nem os volumes. Exige PostgreSQL e Redis já existentes e acessíveis: configurar DB_HOST, DB_USER, DB_PASSWORD, REDIS_HOST e portas com os valores utilizados na instalação anterior. Não apontar para uma base vazia por engano. Substituir ALLOWED_HOST=* pelo hostname correto do NAS e configurar CSRF_TRUSTED_ORIGINS se o domínio/HTTPS exigirem. REDIS_USERNAME e REDIS_PASSWORD dependem do Redis usado. Não executar upgrade major de PostgreSQL sem procedimento específico.

## Testes
Num ZimaOS de teste, verificar ligação à base de dados e Redis, login, criação de um registo de inventário fictício, tarefas em background, redirecionamentos e persistência após reiniciar. Estes testes ainda não estão comprovados em ZimaOS. Manter a porta 20048 e o volume /config.

## Rollback
Em caso de falha, parar o NetBox e restaurar o Compose e as variáveis anteriores, a pasta /DATA/AppData/netbox/config e, se os dados foram alterados, os backups PostgreSQL/Redis consistentes. Confirmar que o NetBox volta a ler os registos antigos antes de reabrir a aplicação. Não reverter apenas a imagem depois de uma migração de schema.

Fonte: https://docs.linuxserver.io/images/docker-netbox/

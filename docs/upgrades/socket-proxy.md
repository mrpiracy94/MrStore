# Socket Proxy — revisão de atualização e rollback

## Contexto e risco
A aplicação `socket-proxy` monta `/var/run/docker.sock`, que dá acesso sensível ao daemon Docker. Alterações a volumes, variáveis de ambiente ou opções de segurança requerem aprovação manual. Este documento **não autoriza** a publicação automática de uma configuração com acesso ao socket.

## Backup
Antes de qualquer alteração num ZimaOS real, exportar o manifesto Compose atual, as variáveis e a configuração efetiva do serviço. Confirmar que o backup pode ser lido e restaurado. Não copiar nem expor o socket Docker ou credenciais.

## Migração
Comparar o Compose anterior com o novo e rever explicitamente os endpoints Docker permitidos. Preferir um proxy de socket com ACL mínima, socket só de leitura quando tecnicamente possível, e sem permissões administrativas desnecessárias. Não fazer migração automática nem alterar volumes persistentes.

## Testes
Num ZimaOS de teste, verificar arranque, permissões, endpoints autorizados, bloqueio de endpoints perigosos e ausência de regressões nas aplicações dependentes. Testes estáticos não substituem estes testes reais.

## Rollback
Conservar o manifesto anterior e restaurá-lo se o proxy ou aplicações dependentes falharem. Confirmar o estado dos serviços e rever logs. Qualquer configuração que continue a expor o socket deve permanecer em quarentena até aprovação específica.

## Estado
Plano documental para o gate de revisão. **Sem evidência de testes reais ou autorização de publicação.**

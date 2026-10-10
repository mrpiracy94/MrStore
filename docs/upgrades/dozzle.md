# Dozzle — migração da montagem direta do Docker socket para proxy de leitura

## Impacto e pré-requisitos

A atualização troca o contentor único `dozzle` com acesso direto a
`/var/run/docker.sock` por dois serviços: `dozzle` (proxy interno)
e `dozzle-web` (UI). O identificador ZimaOS, a porta HTTP externa **30011**
e a funcionalidade de consulta de logs devem manter-se. As ações de
arrancar/parar contentores, shell e alterações ao Docker ficam
intencionalmente indisponíveis.

**Não atualizar instalações reais antes dos testes Docker e ZimaOS.**
O socket Docker continua sensível, mesmo com bind em modo de leitura;
o proxy precisa de negar requisições de escrita na API (HTTP 403).

## Backup

1. Guardar uma cópia do Compose antigo e respetivas variáveis/configurações
   locais **fora do repositório público**. Não copiar segredos para logs nem CI.
2. Identificar qualquer volume ou ficheiro de configuração personalizado
   que o utilizador tenha acrescentado, em especial `/data`.
3. Guardar a configuração do ZimaOS e verificar que a porta 30011
   não está ocupada; a app anterior da MrStore não monta um volume de dados.
4. Registar a versão/tag e digest anterior para possibilitar recuperação.

## Migração num Docker/ZimaOS de testes

1. Instalar os dois novos serviços isolados em rede não pública, sem
   partilhar volumes de produção. O proxy possui o único bind de
   `/var/run/docker.sock`; a UI não deve ter qualquer mount do socket.
2. Verificar que o proxy só é acessível na rede interna `dozzle-backend`
   e não publica a porta 2375 no host.
3. Confirmar com pedidos HTTP reais: `GET /containers/json` funciona,
   `POST /containers/create` é negado com 403 e logs em GET funcionam.
4. Confirmar HTTP 200 na UI na porta 30011, listagem de contentores,
   atualização contínua de logs e reinício bem sucedido de ambos os serviços.
5. Testar as arquiteturas AMD64 e ARM64 e analisar ambas as imagens com
   Trivy, sem exceções automáticas para findings HIGH/CRITICAL.
6. Só depois executar um piloto C3 num ZimaOS de ensaio, verificando a
   deteção do serviço principal `dozzle-web`, interface e persistência.

## Reversão e preservação de dados

Se algum teste falhar, **não publicar a atualização** nem reiniciar os
serviços no NAS real. No ambiente de ensaio, executar
`docker compose down` no projeto novo e restaurar o Compose de backup.
Não apagar volumes de utilizadores.

Num NAS real, caso a atualização já tenha sido aplicada e a nova UI falhe,
primeiro parar a aplicação com segurança e restaurar dados/configuração
pelo backup. A configuração antiga tem acesso direto privilegiado ao Docker
socket, portanto só a reativar temporariamente num host isolado e após
aceitação explícita do risco; de preferência manter Dozzle desativado
até ser corrigido o proxy. Nunca expor a porta 2375 sem autenticação.

A aprovação final depende de testes reais de arranque, logs, permissões,
rollback e UI no ZimaOS. Este plano não constitui prova de que tenham passado.

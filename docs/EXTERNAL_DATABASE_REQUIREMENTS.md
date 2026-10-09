# MrStore — HedgeDoc e NetBox: configuração externa obrigatória

Em 10-10-2026 os manifests de HedgeDoc e NetBox foram corrigidos para não pressuporem que um nome interno de base de dados existe no ZimaOS. Estes serviços não são instalações one-click: requerem serviços externos previamente provisionados e acessíveis pela rede Docker.

**HedgeDoc** exige MariaDB/MySQL externa e valores reais em DB_HOST, DB_PORT, DB_USER, DB_PASS e DB_NAME. CMD_DOMAIN e opções de callbacks/HTTPS também são editáveis. A configuração continua a usar o mesmo volume /DATA/AppData/hedgedoc/config e a porta pública 20029. O hostname e a base nunca devem ser inventados pelo catálogo.

**NetBox** exige PostgreSQL e Redis externos. Os parâmetros de ligação, credenciais de administrador e ALLOWED_HOST estão disponíveis no formulário de instalação. ALLOWED_HOST não é um wildcard: começa com zimaos.local, mas deve ser adaptado ao hostname/IP do NAS. REDIS_USERNAME e REDIS_PASSWORD são opcionais consoante o Redis; REDIS_DB_TASK=0 e REDIS_DB_CACHE=1 são os valores publicados pelo fornecedor. Volume e porta 20048 mantêm-se.

Os placeholders CHANGE_ME são indicadores de configuração obrigatória, nunca passwords. O release seguro ainda coloca estas apps em quarentena enquanto o bootstrap correto não estiver concluído. Não desativar esta proteção para aumentar o número de apps publicadas. A remoção de um hostname fictício não corrige as CVEs das imagens.

Upstream: https://docs.linuxserver.io/images/docker-hedgedoc/ e https://docs.linuxserver.io/images/docker-netbox/

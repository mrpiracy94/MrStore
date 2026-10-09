# MrStore — endurecimento dirigido de serviços (2026-10-10)

Esta alteração não modifica versões de imagens Docker nem instala aplicações. Protege configurações concretas e preserva os volumes/portas utilizados por cada serviço.

## Correcções

- Glances: remove a montagem direta e com privilégios do Docker socket. Mantém UI 61208 e GLANCES_OPT=-w. Métricas dos containers deixam de estar disponíveis por defeito.
- Homepage: remove o Docker socket, mantendo /DATA/AppData/homepage e a porta 30007. Substitui HOMEPAGE_ALLOWED_HOSTS=* pelo hostname inicial zimaos.local:30007; o utilizador deve indicar o IP/hostname real quando diferente. Integrações com Docker requerem configurar depois um proxy dedicado com permissões restritas.
- Homarr: elimina o socket Docker por defeito, preserva /DATA/AppData/homarr, 7575 e o campo SECRET_ENCRYPTION_KEY. Docker widgets/gestão não ficam ativos até configuração posterior com proxy de menor privilégio. A chave privada de 64 hex permanece necessária e não é gerada/fixada no repositório.
- DuckDNS: elimina o exemplo de subdomínio não configurado e apresenta ao utilizador os campos SUBDOMAINS e TOKEN. O token real deve ser fornecido na instalação.
- Healthchecks: corrige SITE_ROOT para a porta efetivamente publicada 20037, acrescenta SECRET_KEY e SITE_NAME requeridos pelo fornecedor, obriga a substituir o endereço de email demonstrativo e expõe os cinco campos importantes no editor ZimaOS. Mantém /config.

## Política persistente

O verificador estático assinala agora HOMEPAGE_ALLOWED_HOSTS=* ou ALLOWED_HOST(S)=* como desativação da validação de Host. A publicação segura não aprova esse comportamento. Também passou a verificar SITE_ROOT da mesma forma que URLs públicas equivalentes.

### Limites importantes

- As montagens do Docker socket que são necessárias à função principal de Dozzle, Dockge e socket-proxy não foram removidas indiscriminadamente. Netdata também permanece para revisão técnica própria.
- A permissão do Docker socket continua muito poderosa mesmo com read_only: true; para o voltar a disponibilizar, usar um proxy restrito e revisão explícita.
- Os CHANGE_ME continuam como placeholders de instalação e **não constituem credenciais válidas**. Como os segredos pertencem ao operador, não existe chave universal segura para publicar no Git. A política de release segura continua a colocar estas apps em quarentena até o mecanismo de instalação protegida ser aprovado.
- Não houve alteração das imagens nem confirmação de correção de CVEs HIGH/CRITICAL. A auditoria de imagens e a remediação por app continuam a ser necessárias; não afirmar que um menor número de avisos estáticos significa menos vulnerabilidades de dependências.
- A funcionalidade real permanece sujeita a teste de ZimaOS quando existir ambiente disponível. Não afirmar uma certificação C2/C3/C4.

## Referências dos fornecedores

- Homepage — https://gethomepage.dev/installation/
- Homepage Docker — https://github.com/gethomepage/homepage/blob/dev/docs/installation/docker.md
- Homarr — https://homarr.dev/docs/getting-started/installation/docker/
- Glances — https://github.com/nicolargo/glances/blob/develop/docs/docker.rst
- DuckDNS — https://docs.linuxserver.io/images/docker-duckdns/
- Healthchecks — https://docs.linuxserver.io/images/docker-healthchecks/

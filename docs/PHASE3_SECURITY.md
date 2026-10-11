# MrStore — Segurança Fase 3

Âmbito: 254 aplicações Docker, as respetivas imagens e imagens próprias
construídas a partir dos Dockerfiles do repositório. A verificação é
independente da plataforma de instalação; ZimaOS v2 é um dos consumidores.

## Recuperação da publicação
O builder externo altera o Python do runner. O workflow editorial restaura
Python 3.12 e as dependências fixadas antes de verificar o catálogo e
executar security_inventory.py. A aplicação netboot.xyz passou a usar um
ícone SVG local na MrStore, reduzindo a dependência de uma URL externa
que falhou numa publicação. Não houve alteração ao Docker de netboot.xyz
nem aos seus volumes, redes, portas ou segredos.

## Novos scans independentes
O workflow dockerfile-base-scan.yml lista todos os FROM em
security/images/*/Dockerfile, resolve ARG quando existem valores de
origem definidos no Dockerfile, e consulta digests de registry com crane.
Trivy avalia as imagens-base em AMD64 e ARM64. O relatório de cada
shard é guardado mesmo quando o exame falha.

Resoluções impossíveis de ARG, registry inacessível, imagens com CVEs
HIGH/CRITICAL e falhas de scanner **não contam como CLEAN**.
Estes scans são distintos da auditoria das imagens finais do catálogo
e não provam que uma imagem derivada esteja isenta de vulnerabilidades.

## Riscos que continuam a exigir tratamento humano
Credenciais CHANGE_ME, APIs Docker e portas administrativas publicadas,
seccomp desativado e privilégios obrigatórios de certas aplicações não
podem ser apagados em massa sem testar a operação real. O inventário da
Fase 2 continua a alertar por aplicação e a bloquear novos riscos.

O GitHub Action não instala ou reinicia serviços no NAS do utilizador.
O catálogo ZimaOS, dados persistentes e o total de 254 aplicações devem
ser preservados. Reversão por Git: reverter o commit/PR após revisão e
reexecutar o fluxo de publicação; um rollback do catálogo não reverte
automaticamente instalações ou dados já migrados.

## Testes
Os testes Python de Fase 3 validam ordem do Python depois do builder,
presença do ícone e que o scan das bases não é confundido com testes
de PR. Para concluir é necessário verificar CI, publicação completa,
rede e compatibilidade runtime em equipamentos reais.

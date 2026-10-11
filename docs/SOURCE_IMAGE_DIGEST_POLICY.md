# Digest SHA256 obrigatório em todos os manifestos da MrStore

Todos os 254 manifestos de Apps/ foram alinhados com os digests já revistos
de data/image-digests.json. Esta operação não altera portas, volumes, UID/GID,
privilégios nem segredos. Preserva nomes/tag de imagem para rastreabilidade.

## Proteções
- O ficheiro Apps/*/docker-compose.yml tem de indicar digest imutável.
- scripts/verify_source_digests.py valida todos os serviços e confronta
  o digest com a baseline revista. Erros bloqueiam a CI e a publicação.
- O catálogo distribuído continua a validar digests antes do builder.
- Para atualizar uma imagem, abrir PR que atualiza em conjunto a referência
  de Apps/ e data/image-digests.json, com evidência CVE/multiarch e testes.
- A baseline não deve ser automaticamente sobrescrita por um monitor.

## Limites
Digest imutável não equivale a imagem livre de CVEs; versões fixas deixam
de receber novas correções por si só e exigem manutenção regular.
Arquiteturas AMD64/ARM64 precisam de confirmação no registry e nos hosts.
Aplicações com passwords CHANGE_ME, seccomp desativado, sockets Docker e
portas administrativas continuam a exigir cuidados específicos; este
documento não as declara como seguras para instalar sem configuração.

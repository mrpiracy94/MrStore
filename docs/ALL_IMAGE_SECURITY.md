# Auditoria de segurança de todas as imagens MrStore

O âmbito cobre as 254 aplicações e TODAS as referências Docker, incluindo
bases dos Dockerfiles de imagens derivadas. Não se limita ao ZimaOS v2:
o inventário é relevante também para hosts Docker e outros NAS.

## Política

- Relatórios: scripts/security_inventory.py cria out/all-image-security.json
  e out/all-image-security.md, sem iniciar contentores.
- Verifica credenciais de exemplo, painéis administrativos abertos, permissões
  elevadas, seccomp desativado, mounts sensíveis, digest de cada imagem e
  imagens base usadas nas receitas de build.
- A CI rejeita novas ocorrências críticas; riscos antigos são mantidos como
  avisos até serem corrigidos por migrações verificadas.
- A atualização diária de digests deixa de alterar main automaticamente:
  o relatório de atualizações exige revisão humana por Pull Request.
- A publicação inclui security-inventory.json e mantém
  certification: not_assessed. Digest fixo não significa imagem sem CVEs.
- A análise de Dockerfiles identifica as suas bases, mas não é um scan CVE
  independente de cada base de build.

## Recomendações transversais

Nunca instalar com passwords CHANGE_ME; tokens de terceiros devem ser
emitidos pelo respetivo serviço. Proteger interfaces por autenticação,
firewall, rede privada e TLS. Montar docker.sock em read_only não restringe
operações da API Docker. Privileged e seccomp unconfined precisam de análise
e testes caso a caso. Evitar alterações massivas que impeçam a instalação
ou removam o acesso LAN.

Testar atualizações numa máquina isolada, guardar cópias de segurança dos
dados persistentes e ter um plano de reversão. A auditoria do repositório
não instala software nem altera contentores já existentes.

## Limitações

A verificação estática não prova proteção da firewall, autenticidade de
segredos, ausência de CVEs, disponibilidade de um registry ou funcionamento
em NAS real. O Trivy e os respetivos relatórios são verificações separadas.

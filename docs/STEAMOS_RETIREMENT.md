# SteamOS retirada temporariamente da MrStore

Em 10/10/2026, a aplicação SteamOS foi retirada do **catálogo de origem**
(`Apps/steamos/docker-compose.yml`) a pedido do mantenedor. O histórico do
GitHub preserva o manifesto antigo; remover a definição **não elimina**
nenhum volume, instalação ou dados de utilizadores já existentes.

## Motivo da retirada

A imagem `lscr.io/linuxserver/steamos:latest` foi descontinuada oficialmente
pelo LinuxServer.io e não disponibilizava as plataformas AMD64/ARM64 exigidas
pelas análises recentes.

Fonte: https://info.linuxserver.io/issues/2025-12-13-steamosdep/

## Alterações na origem

- Removido o manifesto da aplicação (a aplicação `steam` é independente e mantém-se).
- Removida a imagem da lista **ativa** de repetição de scans inconclusivos.
- Removido o digest da fotografia ativa e o texto de apresentação PT-PT.
- Preservado o histórico de auditorias e a lista arquivada
  `data/cve-inconclusive-original-20261009.json`.
- A tabela `RETIRED_UPSTREAM` mantém o aviso sobre esta referência, para
  impedir que uma reintrodução seja confundida com imagem suportada.

**Nota de publicação:** a loja GitHub Pages pode continuar a exibir uma versão
antiga enquanto a workflow de publicação segura não concluir. Esta remoção
da origem **não** é autorização para contornar as verificações CVE nem
justificação para eliminar manualmente índices ou prova de segurança.

Uma futura reintrodução depende de uma imagem mantida, arquiteturas
disponíveis, zero HIGH/CRITICAL conhecidos nas análises completas,
compatibilidade de Compose e testes funcionais adequados.

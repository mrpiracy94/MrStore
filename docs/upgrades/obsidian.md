# Obsidian — atualização controlada da imagem LinuxServer.io

## Evidência CVE
A imagem mantém fornecedor e tag `lscr.io/linuxserver/obsidian:latest`.
Digest anterior: `sha256:a3324c3380f40a70d98058636a47db4afaca261907751a720afa4132c7f4c14e`.
Novo digest: `sha256:ed9e6042c95b1fff9f11d3dcf5ec3c8b98fd725124a1621b8d63bb725b5819ea`.
Em 2026-10-11, Trivy AMD64 e ARM64: de 11 CRITICAL / 541 HIGH
para 11 CRITICAL / 530 HIGH, por arquitetura. **Persistem CVEs críticas.**
Relatório: https://github.com/mrpiracy94/MrStore/actions/runs/38172909540/job/114569104845

## Backup
Parar o contentor de teste, guardar integralmente a configuração ligada a
`/config`, perfis, vaults e eventuais plugins de terceiros, e guardar
a versão atual do Compose. A imagem oferece desktop remoto e pode
gravar estados específicos do ambiente da LinuxServer.io.

## Migração
Mudança somente de digest dentro da mesma tag/fornecedor; não alteramos
volumes, portas, privilégios ou UID/GID. Confirmar release notes do fornecedor,
versões de base e comportamento de desktop/clipboard. A redução CVE não
substitui a análise das 11 ocorrências críticas que continuam presentes.

## Testes
Antes de implantar num NAS, num ambiente de ensaio testar sessão remota,
autenticação/isolamento, abertura de vault de teste, plugins e persistência.
A pipeline estática não certifica testes de runtime em ZimaOS.

## Rollback
Parar o contentor, repor Compose e digest anterior, restaurar o backup
da configuração se a imagem nova tiver alterado o perfil. Não destruir
volumes ou vaults durante a reversão.

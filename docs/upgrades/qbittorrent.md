# qBittorrent — atualização de digest com menos CVEs (2026-10-11)

## Evidência
A imagem da LinuxServer.io mantém a tag `lscr.io/linuxserver/qbittorrent:latest`.
O teste comparou o digest original `sha256:b522f9f4b769f8f36d49d22d5eb6a92e9aa18904c6a1830b1439df511ec21983`
com o digest novo `sha256:97333cc1ccf903e0bbcd8eb67e3332e4970e9c1ecabe145e499e9c0847ebcaed`.
Trivy reportou 0 CRITICAL e 13 HIGH no original contra 0 CRITICAL e
0 HIGH no candidato, tanto AMD64 como ARM64.

Relatório: https://github.com/mrpiracy94/MrStore/actions/runs/38172909540/job/114569104792

## Backup
Antes de atualizar um NAS, parar novas transferências e fazer uma cópia de
`/DATA/AppData/qbittorrent/config`, do ficheiro Compose anterior e
da lista de torrents/resumes; guardar também a localização de downloads.
Não modificar `/downloads` durante a cópia de segurança.

## Migração
A alteração no catálogo é APENAS o digest, não o fornecedor nem a tag; mantém
`PUID=1000`, `PGID=1000`, caminhos, UI 8080 e porta 6881 TCP/UDP.
Mudanças de software dentro da tag `latest` ainda podem alterar o
comportamento. Não instalar diretamente por cima de dados importantes
sem validar release notes e migração de configuração num ambiente separado.

## Testes
A CI verifica consistência de digest, análise Trivy de AMD64/ARM64 e sintaxe
Docker Compose; num dispositivo de ensaio ainda é necessário testar arranque,
WebUI/login, torrents de teste, reinício, downloads e persistência.
Compatibilidade real com cada ZimaOS/host ainda não está certificada.

## Rollback
Parar o serviço, repor o digest SHA256 anterior no Compose **e** restaurar
o backup da configuração se a versão mais recente tiver migrado os dados.
Não eliminar os ficheiros de downloads ou volumes no rollback.
Repetir verificações antes de disponibilizar o serviço.

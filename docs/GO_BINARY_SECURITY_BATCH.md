# Remediação em lote: binários Go de Gitea e Qui

**Estado:** candidatos de reconstrução, não imagens certificadas. A branch da
PR #114 recolhe CVEs de todo o catálogo em AMD64/ARM64 e inclui agora estas
duas reconstruções, sem trocar prematuramente as imagens dos manifests.

## Causa confirmada e hipótese verificável

- **Gitea:** os relatórios reais anteriores mostraram **0 CRITICAL e 4 HIGH**
  tanto AMD64 como ARM64. As 4 ocorrências estavam no binário
  `/app/gitea/gitea`, não nos pacotes Alpine. IDs confirmados no issue #34:
  `CVE-2026-78667`, `CVE-2026-78669`, `CVE-2026-97031`; dependências
  `golang.org/x/net v0.59.0` e Go stdlib `v1.27.1`.
  A correção visa `x/net v0.60.0` e Go `v1.27.2`.
- **Qui:** último advisory disponível: **0 CRITICAL e 1 HIGH**. O
  `go.mod` upstream de `v1.31.1` também usa `x/net v0.59.0` e
  Go 1.27.0. **Não há ainda prova** de que o único HIGH do digest
  publicado seja precisamente dessa dependência. A imagem reconstruída só
  será aceite se o Trivy detetar **0 CRITICAL / 0 HIGH**, em ambas as
  arquiteturas, com resultados não vazios. Não ignorar CVEs.

## Fontes e imutabilidade do código

- Gitea `v28.1.0`, commit
  `4ebd5e319b6a9e629bfd7a04292a6fe85b08dee9`; image rootful
  `docker.io/gitea/gitea:28.1.0`. Recompila frontend e backend e substitui
  apenas `/app/gitea/gitea` na imagem rootful com patch de pacotes Go.
  Preserva `/data`, SSH 22, HTTP 3000, `USER_UID` e `USER_GID`.
- Qui `v1.31.1`, commit
  `3cd6f2954549b2adf5f4fdf724788fb06396a7cb`; recompila frontend
  e backend; mantém `/config`, porta 7476, a semântica do entrypoint,
  UID/GID e configuração da app.
- Os dois builders usam toolchain explícita `golang:1.27.2` e exigem
  que `go version -m` reporte a versão corrigida de `x/net`.
  A base Alpine é atualizada durante o build; o scanner valida **a imagem
  final inteira**, não só o binário.

## Gate de publicação

A workflow `publish-patched-go-batch.yml` usa **runners nativos**
AMD64 e ARM64 para cada aplicação. Para cada um dos 4 candidatos:

1. Build com versão do código upstream verificada por SHA.
2. Trivy completo com relatório JSON HIGH/CRITICAL sem allowlist.
3. Gate fail-closed: relatório ausente/vazio/inválido ou qualquer HIGH/
   CRITICAL significa **falha**, não aprovação.
4. Smoke em Docker: versão da aplicação, arranque HTTP, portas internas,
   persistência de bind mount e reinício; SSH adicional no Gitea.
5. Upload dos relatórios CVE de todos os jobs, inclusive falhas.

O workflow não publica a partir da PR. **Só num push validado à main**
e após aprovação integral dos 4 jobs são publicadas tags de arquitetura,
seguidas do manifesto multiarch no GHCR. O digest multiarch é guardado no
artefacto `go-patched-ghcr-multiarch-digests`.

**Não alterar `Apps/gitea/docker-compose.yml` nem
`Apps/qui/docker-compose.yml` para uma tag sem digest.** Após obter os
digests publicados, verificar os dois externamente sem autenticação, voltar
a correr Trivy AMD64/ARM64 e só então fixar os manifests com `@sha256:...`.
Para Gitea, fazer backup de `/DATA/AppData/gitea` e testar HTTP, SSH, Git
clone/push e reinício com dados reais num ZimaOS de teste. Para Qui, backup
de `/DATA/AppData/qui/config`, verificar autenticação, ligação aos
clientes torrent e persistência. Não confundir testes de containers num
runner com prova de compatibilidade ZimaOS C3.

Os restantes CVEs e aplicações ficam sob a auditoria do catálogo, sem
falsas declarações de correção ou de zero alertas globais.

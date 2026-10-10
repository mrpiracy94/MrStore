# MrStore — Publicações seguras com quarentena por aplicação

## Política
O catálogo original continua com 254 manifestos versionados, mas a edição publicada contém só aplicações aprovadas pelos scans atuais. Um CVE de outra app não bloqueia a publicação das restantes.

## Processo
1. O workflow Build and publish MrStore v2 verifica todas as referências de imagens, em oito grupos.
2. Antes de analisar cada imagem, crane digest resolve a referência para um digest imutável. O Trivy examina esse digest em AMD64 e ARM64 segundo as arquiteturas anunciadas pelas apps.
3. O agregador exige os oito relatórios completos e deteta imagens/arquiteturas em falta, relatórios duplicados, contagens inconsistentes ou respostas inválidas.
4. Só as apps cujas imagens deram zero HIGH e CRITICAL, sem erros em nenhuma plataforma declarada, podem ser publicadas. Privileged, acesso ao Docker socket, host networking, segredos CHANGE_ME, cap_add, devices e seccomp unconfined exigem remediação antes de serem elegíveis.
5. O builder oficial ZimaOS v2 recebe exclusivamente a pasta temporária de apps aprovadas, com referências de imagem imutáveis correspondentes aos digests analisados.
6. A verificação confirma os IDs, contagem aprovada, Compose, metadados, digests e subtítulos PT antes de atualizar gh-pages.
7. O ficheiro público release-status.json e os artefactos no Actions guardam as apps não aprovadas e os motivos. A auditoria diária de CVEs e respetivos issues continuam ativos.

**Catálogo completo:** `rollout-233.yml` publica todas as aplicações presentes em `Apps/`, sem filtragem CVE. O seu `release-status.json` identifica sempre `certification: not_assessed`, incluindo os avisos de configuração. Esta listagem é editorial, não uma certificação de instalação, segurança ou compatibilidade. Uma auditoria CVE separada continua a identificar problemas, mas não remove aplicações desta listagem.

A edição auditada em `publish.yml` apenas pode substituir a loja se o seu índice contiver **todos os IDs do inventário**. Nunca poderá reduzir silenciosamente a listagem para o subconjunto sem alertas.

## Limitações e riscos
- Um scan Trivy sem HIGH/CRITICAL não prova ausência absoluta de vulnerabilidades.
- Docker Compose e builder v2 não provam funcionamento real no ZimaOS. Os testes de instalação C2/C3/C4 continuam pendentes.
- Uma app pode desaparecer do catálogo público até ser corrigida e reanalisada, mas os manifests originais não são apagados do repositório.
- A remoção do catálogo não desinstala containers existentes.
- Se nenhuma app passar ou faltar relatório obrigatório, a publicação falha de forma explícita, sem apresentar uma lista vazia como sucesso. Uma edição anterior não é revogada automaticamente.
- A análise multiarch é mais dispendiosa; falhas dos registries mantêm a imagem em quarentena até nova análise.
- Segredos CHANGE_ME continuam a exigir bootstrap seguro antes de um lançamento aprovado.

## Inspeção
GitHub Actions: https://github.com/mrpiracy94/MrStore/actions/workflows/publish.yml
Após release válido: https://mrpiracy94.github.io/MrStore/release-status.json

Nunca editar os relatórios para simular segurança. Corrigir a aplicação/manifest e voltar a testar.

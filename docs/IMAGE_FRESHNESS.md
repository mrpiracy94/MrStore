# MrStore — verificar imagens sem atualizações

## O que é possível comprovar

A monitorização atual (`scripts/updates.py`) compara digests entre execuções. A verificação de 2026-10-09 encontrou **7 alterações**, **1 referência nova** e **1 consulta falhada** entre **258 referências de imagens Docker**. As outras 249 não mudaram *nessa comparação*; isso **não prova** que estejam sem atualizações há meses, nem que o software tenha sido abandonado.

A auditoria adicional `scripts/image_freshness.py` consulta diretamente o `created` da configuração de cada **imagem AMD64** através de `crane config --platform linux/amd64`. Não executa contentores, não muda tags, não toca em dados e não substitui os scans Trivy.

Cada resultado é classificado como:

| Resultado | Significado |
| --- | --- |
| `build_under_180` | Imagem construída há menos de 180 dias |
| `build_180_364` | Imagem construída há 180–364 dias: rever |
| `build_365_plus` | Imagem construída há 365 dias ou mais: prioridade de revisão |
| `unknown` | O registry não fornece data de build fiável |
| `error` | Não se conseguiu consultar a configuração — nunca presumir segurança |

**Idade da imagem não é última versão do software.** Imagens estáveis podem ser antigas e seguras; imagens recentes podem conter CVEs. Imagens fixadas por digest são intencionalmente imutáveis. A versão ARM64 poderá ter uma data de build diferente e requer verificação própria. Nenhum resultado equivale a uma aprovação de segurança.

## Descontinuação comprovada

`lscr.io/linuxserver/steamos:latest` foi descontinuada pelo LinuxServer.io e deixou de ser atualizada. A documentação oficial confirma que a tag `latest` já não é disponibilizada: https://info.linuxserver.io/issues/2025-12-13-steamosdep/ . A MrStore ainda contém uma entrada `Apps/steamos`; não converter silenciosamente essa aplicação noutra diferente.

## Execução automática

O GitHub Actions executa a auditoria semanalmente em **oito grupos de imagens** (com apenas dois grupos paralelos) e permite execução manual. Cada grupo conserva um artefacto JSON com as imagens, datas, razões de classificação e erros, além de um resumo legível. A falta de acesso ao registry faz falhar a verificação correspondente e não conta como aplicação atualizada.

Os resultados constituem uma lista de **candidatas a investigação**. Para afirmar que um projeto não recebe atualizações, é necessário confirmar a manutenção no site/repositório oficial, o changelog, novas releases e a disponibilidade da imagem em cada arquitetura.

Para ver os relatórios, abre **Actions → Audit Docker image build freshness → Artifacts**. A auditoria de CVEs e o bloqueio de publicação são independentes e continuam obrigatórios.

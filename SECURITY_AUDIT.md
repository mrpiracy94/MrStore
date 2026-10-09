# MrStore — auditoria estática (2026-10-09)

O projeto foi reconstruído com os mesmos 254 manifestos Docker Compose. A validação local sem executar containers encontrou:

- **254 aplicações**, **260 serviços** e **258 imagens** distintas.
- **0 erros estruturais** nas regras de validação definidas pela MrStore.
- **401 avisos**: 250 referências de imagens com tags mutáveis, 93 ocorrências de seccomp sem confinamento, 21 placeholders de configuração `CHANGE_ME`, 19 apps sem interface web, 7 montagens sensíveis, 5 casos com capacidades adicionais, 2 apps `privileged`, 2 redes host e 2 grupos de colisões de portas.
- **37 aplicações** AMD64-only de acordo com as falhas de plataforma registadas nos dois primeiros builds oficiais. Não se deve anunciar suporte ARM64 sem verificação do registry.

A auditoria offline **não é uma auditoria CVE**. A pesquisa de vulnerabilidades HIGH/CRITICAL é efetuada com o Trivy no GitHub Actions, em grupos de 1/8 do catálogo por dia. Falhas de acesso à registry ou ao scanner contam como falhas e devem ser investigadas. Os relatórios detalhados estão nos artifacts de GitHub Actions, após a execução dos respetivos workflows.

A publicação v2 usa o builder oficial de ZimaOS e um verificador que exige exatamente 254 apps em `index.json`, cada uma com metadata e Compose. É necessária validação posterior numa instalação ZimaOS real.

Nenhuma aplicação é instalada no GitHub Actions. As atualizações de imagens são apenas notificadas e as propostas do Renovate precisam de aprovação humana; segredos `CHANGE_ME` têm de ser personalizados antes da instalação.

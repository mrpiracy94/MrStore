# MrStore — auditoria estática (2026-10-09)

O projeto foi reconstruído com os mesmos 254 manifestos Docker Compose. A validação local sem executar containers encontrou:

- **254 aplicações**, **260 serviços** e **258 imagens** distintas.
- **0 erros estruturais** nas regras de validação definidas pela MrStore.
- **398 avisos**: 250 referências de imagens com tags mutáveis, 93 ocorrências de seccomp sem confinamento, 21 placeholders de configuração `CHANGE_ME`, 19 apps sem interface web, 7 montagens sensíveis, 5 casos com capacidades adicionais, 1 app `privileged`, 2 redes host e 0 colisões efetivas de portas.
- **37 aplicações** AMD64-only de acordo com as falhas de plataforma registadas nos dois primeiros builds oficiais. Não se deve anunciar suporte ARM64 sem verificação do registry.

As duas colisões antes indicadas eram falsos positivos de protocolos distintos (TCP e UDP). O validador passou a comparar porta e protocolo.

A auditoria offline **não é uma auditoria CVE**. A pesquisa de vulnerabilidades HIGH/CRITICAL é efetuada com o Trivy no GitHub Actions, nos oito grupos (258 imagens) em cada ciclo diário, até quatro grupos em paralelo. As execuções manuais permitem analisar apenas um grupo; ocorrências CRITICAL e erros de scanner fazem falhar a auditoria, depois de preservar os relatórios. Falhas de acesso à registry ou ao scanner contam como falhas e devem ser investigadas. Os relatórios detalhados estão nos artifacts de GitHub Actions, após a execução dos respetivos workflows.

A publicação v2 usa o builder oficial de ZimaOS e um verificador que exige exatamente 254 apps em `index.json`, cada uma com metadata e Compose. É necessária validação posterior numa instalação ZimaOS real.

Nenhuma aplicação é instalada no GitHub Actions. As atualizações de imagens são apenas notificadas e as propostas do Renovate precisam de aprovação humana; segredos `CHANGE_ME` têm de ser personalizados antes da instalação.

## CVEs conhecidas — não escondidas nem consideradas resolvidas

A primeira execução em 2026-10-09 analisou **33 de 258 imagens** e encontrou **127 ocorrências CRITICAL** e **3831 HIGH**. Para 70 das ocorrências CRITICAL, o scanner reportou uma versão corrigida do **pacote**, o que não garante existir já uma imagem compatível e corrigida. Os outros sete grupos ainda não tinham sido verificados nessa execução.

Os maiores contributos CRITICAL do grupo foram Frigate (36), Obsidian (11), Paperless-ngx (9) e UniFi Network Application (9). Frigate deixa de executar privilegiado por omissão; isto diminui a exposição do host, **mas não corrige as CVEs da imagem**.

Os issues por grupo devem permanecer abertos até os fornecedores publicarem versões corrigidas, essas versões serem testadas e um scan novo verificar a melhoria. As versões principais de qBittorrent, PostgreSQL/Immich e outros serviços com dados persistentes precisam de backup, testes de compatibilidade e migração antes de se alterar a tag. O sucesso da validação estrutural ou da publicação não deve ser confundido com ausência de vulnerabilidades.

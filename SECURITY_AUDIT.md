# MrStore — auditoria estática (2026-10-09)

O projeto foi reconstruído com os mesmos 254 manifestos Docker Compose. A validação local sem executar containers encontrou:

- **254 aplicações**, **260 serviços** e **258 imagens** distintas.
- **0 erros estruturais** nas regras de validação definidas pela MrStore.
- **398 avisos**: 250 referências de imagens com tags mutáveis, 93 ocorrências de seccomp sem confinamento, 21 placeholders de configuração `CHANGE_ME`, 19 apps sem interface web, 7 montagens sensíveis, 5 casos com capacidades adicionais, 1 app `privileged`, 2 redes host e 0 colisões efetivas de portas.
- **37 aplicações** AMD64-only de acordo com as falhas de plataforma registadas nos dois primeiros builds oficiais. Não se deve anunciar suporte ARM64 sem verificação do registry.

As duas colisões antes indicadas eram falsos positivos de protocolos distintos (TCP e UDP). O validador passou a comparar porta e protocolo.

A auditoria offline **não é uma auditoria CVE**. A pesquisa de vulnerabilidades HIGH/CRITICAL é efetuada com o Trivy no GitHub Actions, nos oito grupos (258 imagens) em cada ciclo diário, até quatro grupos em paralelo. As execuções manuais permitem analisar apenas um grupo; ocorrências HIGH/CRITICAL e erros de scanner fazem falhar a auditoria, depois de preservar os relatórios. Falhas de acesso à registry ou ao scanner contam como falhas e devem ser investigadas. Os relatórios detalhados estão nos artifacts de GitHub Actions, após a execução dos respetivos workflows.

A publicação v2 usa o builder oficial de ZimaOS e um verificador que exige exatamente 254 apps em `index.json`, cada uma com metadata e Compose. É necessária validação posterior numa instalação ZimaOS real.

Nenhuma aplicação é instalada no GitHub Actions. As atualizações de imagens são apenas notificadas e as propostas do Renovate precisam de aprovação humana; segredos `CHANGE_ME` têm de ser personalizados antes da instalação.

## CVEs conhecidas — não escondidas nem consideradas resolvidas

A primeira execução em 2026-10-09 analisou **33 de 258 imagens** e encontrou **127 ocorrências CRITICAL** e **3831 HIGH**. Para 70 das ocorrências CRITICAL, o scanner reportou uma versão corrigida do **pacote**, o que não garante existir já uma imagem compatível e corrigida. Os outros sete grupos ainda não tinham sido verificados nessa execução.

Os maiores contributos CRITICAL do grupo foram Frigate (36), Obsidian (11), Paperless-ngx (9) e UniFi Network Application (9). Frigate deixa de executar privilegiado por omissão; isto diminui a exposição do host, **mas não corrige as CVEs da imagem**.

Os issues por grupo devem permanecer abertos até os fornecedores publicarem versões corrigidas, essas versões serem testadas e um scan novo verificar a melhoria. As versões principais de qBittorrent, PostgreSQL/Immich e outros serviços com dados persistentes precisam de backup, testes de compatibilidade e migração antes de se alterar a tag. O sucesso da validação estrutural ou da publicação não deve ser confundido com ausência de vulnerabilidades.

## Remediação qBittorrent verificada (2026-10-09)

- A imagem antiga `lscr.io/linuxserver/qbittorrent:4.6.7` apresentava **4 CRITICAL e 135 HIGH**.
- Uma atualização direta para `lscr.io/linuxserver/qbittorrent:5.2.4-libtorrentv1` eliminava as CRITICAL mas ainda apresentava **13 HIGH**.
- Foi construída uma variante baseada na imagem oficial, com atualização de pacotes Alpine. O Trivy **v0.75.0** encontrou **0 CRITICAL e 0 HIGH** tanto em AMD64 como em ARM64; os binários foram testados nas duas arquiteturas.
- Foi publicada no GHCR e o manifest `Apps/qbittorrent-4/docker-compose.yml` foi atualizado para a referência **imutável** `ghcr.io/mrpiracy94/mrstore-qbittorrent:5.2.4-libtorrentv1-secfix-20261009@sha256:6e0475093e34571c90fc0d1ede2920ca847f1b4a1ac127351931eab6e12c6c4c`. O acesso público e o novo scan ao digest remoto foram validados por GitHub Actions.
- Esta entrada atravessa a versão principal 4.x→5.2.4. Instalações existentes **não são atualizadas automaticamente pelo GitHub**; testar compatibilidade e guardar backup de `/DATA/AppData/qbittorrent-4/config` antes de atualizar no ZimaOS.
- **Isto não resolve CVEs das outras 257 imagens.** A auditoria completa deve continuar a identificar, corrigir e reanalisar cada imagem, ou manter fora da publicação as imagens sem solução validada, após decisão sobre a política da loja.

Provas: [publicação da imagem](https://github.com/mrpiracy94/MrStore/actions/runs/37997771065), [comparação e verificação do digest remoto](https://github.com/mrpiracy94/MrStore/actions/runs/37998362405).

## Política obrigatória de lançamento: 0 HIGH / 0 CRITICAL

A publicação do catálogo fica bloqueada por oito verificações independentes de Trivy, que analisam as **258 referências de imagens** em conjunto. Cada job é obrigatório e falha se tiver uma ocorrência HIGH, CRITICAL ou erro de consulta; o builder/publicador exige `needs: security_audit` e só pode publicar se **todos** tiverem resultado válido e sem vulnerabilidades detetadas. Todos os relatórios ficam guardados mesmo quando a execução falha.

**Consequência imediata:** os relatórios atuais identificam muitas vulnerabilidades em imagens de terceiros; por isso, os próximos releases serão bloqueados até que todas as imagens sejam corrigidas e reanalisadas. Isto **não revoga** uma versão anteriormente publicada, **não remove** aplicações já instaladas nem corrige automaticamente os containers dos utilizadores. Essa decisão requer política de despublicação/quarentena e testes de migração específicos.

A exigência é operacional e limitada às bases de dados e capacidades do Trivy usadas no scan. Tags flutuantes podem mudar entre a análise e o consumo da imagem; versões em digest imutável são preferíveis para evitar mudanças inesperadas.

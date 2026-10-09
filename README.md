# MrStore — ZimaOS App Store (254 apps)

Loja comunitária para **ZimaOS**, migrada do catálogo «Minha Loja» de 09/10/2026. Contém **254 aplicações** e **260 serviços Docker**, com suporte de origem para o **formato v2** da App Store.

**Repositório:** https://github.com/mrpiracy94/MrStore

**Endereço previsto após publicar com GitHub Pages:** https://mrpiracy94.github.io/MrStore — este URL só funcionará depois do build e da configuração de Pages.

## Automação de manutenção

| Workflow | Frequência | O que faz |
| --- | --- | --- |
| `validate.yml` | Alterações no código / manual | Verifica YAML, IDs, categorias, imagens, permissões perigosas e executa testes |
| `publish.yml` | Alterações ao catálogo / manual | Usa a ação oficial de build v2 do ZimaOS e publica os ficheiros `dist/` na branch `gh-pages` |
| `update-monitor.yml` | Todos os dias / manual | Compara o **digest** das imagens Docker com a última amostragem; abre issue se houver alteração; grava o estado sem atualizar contêineres |
| `cve-scan.yml` | Todos os dias / manual | Usa **Trivy** para procurar CVEs HIGH e CRITICAL nas imagens; analisa 1/8 do catálogo por dia e guarda relatórios completos em Actions → Artifacts |

A pesquisa por **digest** identifica alterações à imagem publicada (incluindo tags `latest`); **não** descobre todas as novas versões de aplicações que estão fixadas em tags antigas, nem compara versões instaladas no teu ZimaOS. Para estas funções seriam necessárias fontes upstream por app, histórico de releases ou integração autenticada com o ZimaOS. **Nenhuma atualização é instalada automaticamente.**

A verificação de CVEs necessita de internet e será executada no GitHub Actions; **não existem resultados de CVE confirmados na análise offline inicial**. A presença de uma CVE não prova que a aplicação esteja explorável; a ausência de alertas não demonstra ausência de vulnerabilidades. Falhas de registo/Trivy aparecem explicitamente e não são contadas como resultados limpos.

## Instalação da loja

1. Abrir `Settings → Pages` no repositório GitHub. Escolher `Deploy from a branch`, branch **`gh-pages`**, pasta `/ (root)` **depois** de a ação `Build and publish ZimaOS v2 store` criar a branch. Se não aparecer a branch, executar manualmente `Actions → Build and publish ZimaOS v2 store → Run workflow`.
2. Verificar que `https://mrpiracy94.github.io/MrStore/store.json` e `https://mrpiracy94.github.io/MrStore/index.json` existem e carregam JSON válido.
3. Na interface do ZimaOS, adicionar o URL base `https://mrpiracy94.github.io/MrStore` como uma loja de terceiros v2 (compatibilidade dependente da versão do cliente ZimaOS).

A publicação v2 **pode falhar** se as imagens não existirem nas arquiteturas declaradas, se o builder não conseguir descarregar os ícones externos ou devido a rate limits. Isso deve ser tratado através dos logs e relatórios no GitHub Actions. A publicação e o funcionamento no dispositivo ZimaOS **não foram validados** neste ambiente.

## Desenvolvimento e auditoria local

```bash
python -m pip install -r requirements.txt
python scripts/audit_store.py --strict --out out/static-audit.json
python -m unittest discover -s tests -v
# Requer crane (go-containerregistry) e acesso aos registries:
python scripts/check_updates.py
# Requer trivy instalado e acesso aos registries:
python scripts/scan_cves.py --shards 8 --shard 0
```

Os resultados de auditoria são JSON legível por máquina. Avisos não impedem o build; erros de metadados impedem. Os metadados `version: "1.0.0"` são a **revisão inicial do manifesto MrStore**, não a versão upstream de todas as aplicações. Atualizar conscientemente `version`, `update_at`, `release_notes` e a imagem é necessário para lançar novas versões de manifesto visíveis no ZimaOS.

## Segurança e decisões de migração

- Mantivemos, sem executar, todos os Compose originais. Não foram corrigidos automaticamente flags que uma app possa requerer, por exemplo `privileged` ou `seccomp:unconfined`. **Rever antes de instalar**.
- Algumas apps usam `CHANGE_ME` para segredos: definir valores fortes e particulares antes da instalação.
- As categorias antigas foram convertidas para categorias oficiais ZimaOS v2. O `x-casaos.id` de cada app é estável (prefixo `io.github.mrpiracy94`).
- Em **19 apps sem UI web**, foi colocado `port_map: "0"` e `index: /` para completar os metadados exigidos pelo v2. O botão de abrir UI não terá um serviço HTTP real nestes casos; verificar compatibilidade do cliente.
- Imagens com `latest` e outras tags mutáveis podem mudar sem alteração dos manifestos; scans e aviso de alterações por digest ajudam, mas não substituem revisão do changelog e atualização explícita de versões.
- Publicações de porta host duplicadas entre apps são possíveis, mesmo que cada Compose individual seja válido. Confirmar disponibilidade das portas antes de instalar várias apps.

## Fontes e protocolo

Catálogo original: mistura de definições LinuxServer.io, Seedit4Me e projetos independentes. O ZIP original continha afirmações sobre manutenção e descontinuação de projetos que **não foram revalidadas individualmente**. Confira com as páginas upstream antes de instalar.

- Protocolo v2: https://www.zimaspace.com/docs/developer/app-store-compose-x-casaos
- Build oficial: https://github.com/IceWhaleTech/build-appstore-action
- Scanner CVE: https://github.com/aquasecurity/trivy
- Monitorização de imagens: https://github.com/google/go-containerregistry/tree/main/cmd/crane

Este repositório é uma loja **não oficial** e não representa a IceWhaleTech nem os programadores das aplicações listadas.

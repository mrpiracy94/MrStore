# MrStore — ZimaOS v2

Loja comunitária não oficial, reconstruída em 09-10-2026 a partir das **254 definições Docker Compose** da Minha Loja original. O código da automação foi refeito: os manifests são tratados exclusivamente como dados, nunca executados nos runners. O catálogo contém **260 serviços** e **258 referências únicas de imagens**.

**GitHub:** https://github.com/mrpiracy94/MrStore  
**URL após publicar em Pages:** https://mrpiracy94.github.io/MrStore

## Como adicionar ao ZimaOS

1. Abra `Actions → Build and publish MrStore v2` e confirme que o build publicou todas as 254 apps sem erros.
2. Em `Settings → Pages`, selecione `Deploy from a branch`, a branch **gh-pages** e a pasta **/(root)**; não selecione `main`.
3. Aguarde a publicação, confirme que [`store.json`](https://mrpiracy94.github.io/MrStore/store.json) e [`index.json`](https://mrpiracy94.github.io/MrStore/index.json) devolvem JSON válido e então adicione `https://mrpiracy94.github.io/MrStore` ao ZimaOS como loja externa (cliente compatível com protocolo v2).

O builder oficial do ZimaOS é responsável por gerar os JSON e `content_hash` corretos. A verificação adicional `scripts/verify_dist.py` impede a publicação de catálogos incompletos. A primeira importação para ZimaOS ainda tem de ser validada num dispositivo real.

## Publicação com quarentena por aplicação

A publicação não precisa esperar que **todas as imagens** do catálogo estejam livres de CVEs. Em cada execução, a MrStore analisa as 258 referências de imagens em todas as arquiteturas declaradas, fixa o digest que foi realmente analisado e só publica as apps cujos **todos os serviços** passaram sem HIGH/CRITICAL ou erros de scanner. As apps inseguras ou inconclusivas **não entram no índice publicado** e ficam documentadas; os 254 manifests permanecem no repositório.

Configurações perigosas e segredos predefinidos também impedem a aprovação individual. Nenhuma CVE é considerada resolvida só por retirar uma app do catálogo. Consultar [política de segurança do release](docs/SAFE_RELEASE_POLICY.md) e os relatórios públicos `release-status.json` quando existir um release válido.

**Importante:** a lista de apps na loja publicada pode ser inferior às 254 definições originais. A publicação só ocorre após scans completos em oito grupos; se nenhum resultado for elegível, não publica uma lista vazia enganadora. Isto não instala nem atualiza containers automaticamente.
## Funcionalidades

| Componente | Funcionamento | Automação |
| --- | --- | --- |
| Validação | Inspeciona todos os Compose, IDs, metadados, ícones locais, portas e flags de segurança | Push, PR e manual |
| Publicação | Compila catálogo v2 pelo builder oficial, verifica 254 entradas e publica `dist/` | Push e manual |
| CVE | Trivy verifica vulnerabilidades **HIGH/CRITICAL**, mostrando pacotes afetados e versões corrigidas (quando existem) | Diário, 1/8 das 258 imagens por dia; report JSON/Markdown; issue caso existam CVEs CRITICAL |
| Atualizações por digest | Compara a referência da imagem Docker com o digest anterior; gera relatório e issue por alterações efetivas | Diário, sem instalar atualizações |
| Novas tags/versionamento | Renovate propõe pull requests de alterações nas imagens com tags suportadas | Depois de autorizar a GitHub App Renovate |

**Limitações:** a alteração do digest de `latest`/`release` não é, por si só, uma nova versão upstream e não informa qual a versão instalada no ZimaOS. Para atualizar apps instaladas será necessária uma integração específica com a API da instalação. Os manifestos usam uma versão de revisão inicial `1.0.0` da loja, **não** a versão atual oficial de cada imagem. Não existem atualizações de containers automáticas.

## Segurança

- Nunca instalamos containers para validar os Compose. A revisão estática não elimina perigos reais.
- Alguns projetos exigem `privileged`, `seccomp:unconfined` ou acesso ao Docker Socket; veja os relatórios antes de instalar.
- Substitua todos os segredos `CHANGE_ME` no momento de instalação.
- Ícones externos inválidos foram trocados por placeholders próprios para 87 apps; thumbnails podem continuar externos.
- Os logs do builder oficial mostraram **37 apps com imagem sem ARM64**: declaramos apenas AMD64 nessas apps. A compatibilidade de outras arquiteturas deve ser reconfirmada a cada nova imagem/tag.
- Os scans dependem de acesso a registries e bases de dados Trivy; erros são **falhas**, não resultados limpos.
- `x-casaos.version` e `content_hash` controlam atualizações do catálogo, não upgrades automáticos dos containers.

## Compatibilidade comprovada no ZimaOS

O catálogo de 254 apps publicado em formato v2 e os testes de CI **não são** equivalentes a instalações comprovadas num ZimaOS real.

- Inventário estático por app: `python scripts/compatibility.py` (artefacto GitHub Actions `zimaos-compatibility-static`).
- Smoke test opt-in de uma app já instalada num NAS: `python scripts/zimaos_runtime_probe.py --app actual-budget --host IP_DO_NAS`. O comando usa apenas Docker inspect e HTTP, sem modificar containers; não valida logins nem dados persistentes.
- Critérios C0–C4, testes funcionais, registo de evidência e limitações: [docs/ZIMAOS_COMPATIBILITY.md](docs/ZIMAOS_COMPATIBILITY.md).

**Nenhuma app é declarada validada em ambiente real apenas pelo inventário/CI.**

## Estrutura do projeto

```text
Apps/<app>/docker-compose.yml  # 254 manifests, origem preservada
Apps/<app>/icon.svg            # ícones de recurso para as apps sem ícone válido
scripts/catalog.py             # catálogo e segurança estática
scripts/validate.py            # validação / relatório
scripts/verify_dist.py         # validação do resultado real da compilação v2
scripts/updates.py             # crane / digest e alertas
scripts/cves.py                # Trivy CVEs HIGH/CRITICAL
.github/workflows/             # CI, publicação e monitorizações
renovate.json                  # PRs opcionais de novas tags
```

## Executar localmente

```bash
python -m pip install -r requirements.txt
python scripts/validate.py
python -m unittest discover -s tests -v
# Após instalar a CLI crane e ter acesso aos registries:
python scripts/updates.py
# Após instalar o Trivy e atualizar a base de CVEs:
python scripts/cves.py --shards 8 --shard 0
```

Os relatórios são escritos em `out/` e carregados como artefactos no GitHub Actions. Os dados de referência de digests ficam em `data/image-digests.json`. Revisão obrigatória antes de aceitar PRs de novas imagens ou versões; **não há merges automáticos**.

## Fontes e compatibilidade

- [Documentação do protocolo ZimaOS v2](https://www.zimaspace.com/docs/developer/app-store-github-actions)
- [Descrição da saída de build v2](https://github.com/IceWhaleTech/CasaOS-AppStore/blob/main/docs/specs/build-output.md)
- [Trivy](https://github.com/aquasecurity/trivy)
- [crane](https://github.com/google/go-containerregistry/tree/main/cmd/crane)
- [Renovate](https://github.com/renovatebot/renovate)

MrStore não é uma loja oficial IceWhaleTech. Os projetos originais continuam a pertencer aos respetivos desenvolvedores; o catálogo não garante disponibilidade, manutenção ou segurança de cada imagem.


## Deteção de atualizações do ZimaOS (ramo de integração)

A auditoria de imagens instaladas, o verificador de digests OCI por arquitetura, o versionamento monotónico dos pacotes aprovados e o bloqueio de `content_hash` sem alteração estão documentados em [ZimaOS OCI](docs/ZIMAOS_OCI_UPDATE_CHECK.md), [visibilidade de atualizações](docs/ZIMAOS_UPDATE_VISIBILITY.md) e [proposta nativa](docs/ZIMAOS_NATIVE_UPDATE_PATCH_PROPOSAL.md). Estas ferramentas **não alteram o NAS nem corrigem o gestor nativo do ZimaOS**. Todos os mecanismos de publicação permanecem subordinados à quarentena de segurança.

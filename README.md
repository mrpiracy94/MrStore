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

**Limitações:** a alteração do digest de `latest`/`release` não é, por si só, uma nova versão upstream e não informa qual a versão instalada no ZimaOS. Para atualizar apps instaladas será necessária uma integração específica com a API da instalação. Os manifests de origem podem ter uma revisão inicial `1.0.0`, mas a publicação compara a última versão em `gh-pages` e avança a revisão do **pacote MrStore** apenas quando a referência Docker aprovada muda (ou quando existe uma versão de pacote explicitamente superior). Isto **não** representa a versão oficial da aplicação. Não existem atualizações de containers automáticas.

## Atualizações visíveis no ZimaOS

A deteção de novas imagens no registry e a oferta de atualizações a uma instalação são operações diferentes:

1. `scripts/updates.py` acompanha diariamente os digests dos tags, sem modificar containers nem declarar versões upstream.
2. A publicação, agora também agendada semanalmente, reavalia **todas as arquiteturas** com Trivy. Apenas apps aprovadas são publicadas; imagens vulneráveis ou inconclusivas continuam em quarentena.
3. `scripts/release_versions.py` lê o índice e os Compose da última publicação na branch `gh-pages`, conserva a versão anterior quando as imagens são iguais e incrementa a revisão SemVer do pacote quando uma imagem aprovada mudou. Nunca reduz versões (p. ex. de `1.0.2` para `1.0.0`).
4. O builder oficial gera o novo `content_hash`, `index.json`, `meta.json` e os Compose; as verificações antes da publicação confirmam as versões e os digests.
5. Na interface do ZimaOS, atualizar a fonte da loja e consultar as aplicações instaladas. Uma atualização só pode aparecer para apps instaladas com a identidade/contexto dessa mesma loja.

**Limitação do sistema operativo:** algumas versões do ZimaOS podem marcar imagens `:latest` sem `RepoDigests` como atualizadas mesmo quando não estão. É um problema documentado no [ZimaOS #591](https://github.com/IceWhaleTech/ZimaOS/issues/591) e não pode ser corrigido apenas por metadados de uma loja externa. Nenhum aviso é garantido sem validação num NAS real. Não falsificamos tags nem desativamos as verificações HIGH/CRITICAL para produzir notificações.

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

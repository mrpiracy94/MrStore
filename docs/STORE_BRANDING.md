# MrStore — identidade visual no ZimaOS

A loja mantém o protocolo oficial **ZimaOS App Store v2** e o identificador estável
`io.github.mrpiracy94.mrstore`.

## Identidade
- `store-config.json` contém nome, descrição bilingue e `icon`.
- `branding/mrstore-icon.svg` é o logótipo original laranja/preto. O `icon`
  aponta para a versão pública no branch `main`, pelo que só ficará acessível
  depois do merge.
- Não se alteram as cores, o CSS nem o layout da interface nativa ZimaOS:
  a identidade aparece apenas onde o cliente suporta os metadados da loja.

## Aplicações
- As categorias de `category-list.json` refletem as nove categorias reais
  usadas nos Compose (`x-casaos.category`). Na publicação segura, as contagens
  são recalculadas a partir das apps aprovadas.
- Cada `Apps/<nome>/docker-compose.yml` define ícone, thumbnail, título,
  descrição e possíveis línguas. Foram adicionadas descrições PT a 15 apps.
- Ícones e thumbnails existentes continuam associados aos projetos originais.
  O validador verifica referências HTTPS, mas sem rede não prova a disponibilidade
  desses recursos externos.
- Screenshots reais podem ser adicionados como `Apps/<nome>/screenshot-1.png`,
  `screenshot-2.png` (ou jpg/webp). O builder oficial v2 empacota estes recursos.
  **Não usar mockups da MrStore como capturas de ecrã das aplicações.**
  Não são declaradas screenshots para apps sem fotografias verificadas.

## Destaques e recomendações
- `featured-apps.json`: lista opcional compatível com o formato legado
  `{"appid": "..."}`.
- `recommend-list.json`: recomendações ordenadas e diversificadas, mantendo
  os campos utilizados anteriormente por este catálogo (`id`, `name`, `title`).
- `scripts/release_catalog.py` filtra ambas as listas após a auditoria:
  uma app em quarentena nunca pode surgir nas listas publicadas.
- O workflow inclui os JSON filtrados em `dist/` para clientes compatíveis.
  **O protocolo v2 não garante que a interface nativa do ZimaOS mostre
  ficheiros de destaques legados.** Não prometer posições ou destaques
  específicos sem teste no ZimaOS real.

## Verificação
```bash
python scripts/branding_report.py --strict
python scripts/validate.py
python scripts/curate_taglines.py --check
python -m unittest discover -s tests -v
```

O relatório `out/branding-audit.json` indica quantas descrições PT e
screenshots locais existem e quantas referências externas são usadas.
A compatibilidade visual só fica comprovada depois de instalar a loja num
ZimaOS real, com a publicação v2 concluída.


### Capturas reais incluídas

Três imagens PNG foram copiadas, sem alterações de conteúdo, das
definições da [App Store oficial ZimaOS](https://github.com/IceWhaleTech/CasaOS-AppStore):
[Immich](https://github.com/IceWhaleTech/CasaOS-AppStore/blob/main/Apps/Immich/screenshot-1.png),
[Nextcloud](https://github.com/IceWhaleTech/CasaOS-AppStore/blob/main/Apps/Nextcloud/screenshot-1.png)
e [Vaultwarden](https://github.com/IceWhaleTech/CasaOS-AppStore/blob/main/Apps/Vaultwarden/screenshot-1.png).
Estes ficheiros entram no build v2 apenas quando a app passa a quarentena.
As marcas e interfaces permanecem propriedade dos respetivos projetos; a
reutilização segue a origem e deve respeitar as licenças aplicáveis.

## Descrições portuguesas no catálogo aprovado

Os 15 textos PT-PT escritos diretamente nos manifests permanecem intactos.
Para as restantes aplicações **aprovadas**, o gerador de publicação utiliza
os 254 resumos específicos de `data/taglines-pt.json` como primeira frase da
descrição PT-PT, seguido de orientações genéricas de instalação segura.
Isto é uma **descrição de recurso no catálogo publicado**, e não uma tradução
integral revista por humano da descrição original. Os manifests de origem e
as configurações Docker não são alterados; uma descrição PT-PT existente tem
sempre prioridade. Apps em quarentena nunca são enriquecidas nem publicadas.

## Auditoria online de imagens

`python scripts/asset_audit_online.py --strict --defer-unpublished` inspeciona
online **cada URL único** de ícone e thumbnail referenciado nas 254 apps e o
ícone da loja. Verifica HTTPS, endereços DNS públicos, redirecionamentos,
resposta HTTP e assinatura dos bytes de imagem, com um relatório JSON completo
em `out/asset-audit-online.json` e resumo Markdown. A execução é automática
no CI da PR. As classes não são equivalentes:

- `ok`: resposta obtida e formato de imagem reconhecido;
- `broken`: imagem ausente (404/410) ou resposta não é uma imagem;
- `unsafe`: URL não segura ou destino não público;
- `inconclusive`: falha de rede, bloqueio temporário, 403/429 ou 5xx;
- `deferred`: ficheiro local novo ainda não disponível no endereço `main` antes do merge.

Com `--strict`, URLs quebrados ou inseguros falham o job. Falhas transitórias
ficam assinaladas **sem serem contadas como validadas**. `--require-complete`
também exige que não haja verificações inconclusivas ou adiadas.
No `main`, o CI remove `--defer-unpublished` para voltar a verificar o URL
público da imagem da loja e os demais recursos locais.

## Mais screenshots genuínos na publicação

Além das 3 capturas já presentes no Git, a publicação agora procura **10
capturas adicionais** na
[CasaOS AppStore oficial](https://github.com/IceWhaleTech/CasaOS-AppStore/tree/0909364b800950030e71ea82355a5969a1c08b39/Apps):
Gitea, Home Assistant, Jellyfin, Ollama, Plex, qBittorrent, Syncthing
(screenshot inicial) e uma segunda imagem de Immich, Nextcloud e Vaultwarden.

`scripts/official_screenshots.py` obtém cada imagem de um commit imutável
do repositório oficial, valida a assinatura PNG/JPEG, limita o tamanho e
compara o hash de objeto Git exato. O job de PR usa `--verify-only` (não
grava ficheiros). O release importa ficheiros apenas para `release-source/Apps`
das apps já aprovadas; não modifica os manifests originais nem mostra imagens
de aplicações em quarentena. As capturas extra só são consideradas
**efetivamente presentes no catálogo** após uma compilação e publicação
concluídas, não apenas por esta alteração à pipeline.

Origens e atribuição: ficheiros `Apps/<nome>/screenshot-N.*` do repositório
acima, com nome da pasta original e objeto SHA em
`scripts/official_screenshots.py`. As capturas são das interfaces dos projetos
originais e sujeitas às respetivas licenças. A sua integridade de origem não
comprova que a interface do ZimaOS as apresente corretamente.

## Evidências e testes adicionais

```bash
python scripts/asset_audit_online.py --strict --defer-unpublished
python scripts/official_screenshots.py --verify-only
python -m unittest discover -s tests -v
```

A auditoria externa e a verificação de screenshots requerem ligação à
Internet. A execução no GitHub Actions guarda relatórios em artefactos;
a aprovação final deve basear-se nesses resultados, nunca na mera presença
dos scripts. A confirmação de renderização no ZimaOS real continua pendente.

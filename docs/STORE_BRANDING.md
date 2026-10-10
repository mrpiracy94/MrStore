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


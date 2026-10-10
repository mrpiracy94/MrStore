# Interface da MrStore: GitHub + GitHub Pages

O GitHub controla o seu próprio layout; não é possível mudar o tema, menus
ou o CSS de github.com para cada repositório. A MrStore apresenta-se em dois
locais distintos:

1. README.md — página de entrada do repositório, com banner, navegação curta,
   instalação, segurança e ligações para documentação.
2. https://mrpiracy94.github.io/MrStore/ — montra web estática com identidade
   laranja, pesquisa, filtros, favoritos e detalhes das aplicações.

## Dados e segurança

O navegador obtém os dados do index.json oficial do ZimaOS v2.
Nenhuma aplicação é hardcoded no JavaScript. O número de aplicações
e categorias é calculado a partir da edição efetivamente distribuída.

A montra procura também o release-status.json. Só apresenta uma mensagem
de publicação aprovada quando a lista de IDs coincide integralmente com
as apps aprovadas pelo processo de release. Sem esse relatório, mostra um
aviso de edição sem evidência completa. Nunca esconde uma falha de segurança.

Os ícones e manifests são resolvidos exclusivamente para caminhos locais do
projeto GitHub Pages. Os dados do catálogo entram na página através de
textContent, não por HTML arbitrário. Não existem dependências externas
CDN; favoritos são guardados apenas no browser.

## Publicar sem quebrar a App Store v2

Após todos os scans obrigatórios e a construção v2, a CI copia o relatório
de quarentena e executa:

    python scripts/stage_storefront.py --source web --dist dist

O programa exige index.json, store.json, release-status.json, app_count e
o conjunto de IDs aprovados exatamente consistentes. Apenas copia index.html
e recursos de web/assets. Não altera o protocolo, Compose, imagens, versões ou
metadados oficiais. Se a lista não estiver aprovada, falha a publicação.

A montra só fica online depois de o workflow de publicação da main passar e
GitHub Pages usar a branch gh-pages. Não é um instalador web.

## Testar

    python -m unittest tests/test_storefront.py -v

Para testar a página localmente, usa a pasta dist de uma publicação válida e
um servidor HTTP estático. Abrir web/index.html diretamente a partir de file://
não dá acesso ao index.json publicado.

Não confundir a qualidade visual com segurança certificada ou prova de runtime
num NAS ZimaOS.

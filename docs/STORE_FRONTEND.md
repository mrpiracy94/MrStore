# Interface da MrStore: GitHub + GitHub Pages

O GitHub controla o seu próprio layout; não é possível mudar o tema, menus
ou o CSS de github.com para cada repositório. A MrStore apresenta-se em dois
locais distintos:

1. README.md — apresentação universal do projeto com banner WebP, ligações para o catálogo, plataformas e política de segurança.
2. https://mrpiracy94.github.io/MrStore/ — montra web estática com o mesmo
   banner laranja e grafite, monograma M, pesquisa, filtros, favoritos e detalhes das aplicações.

## Dados e segurança

O navegador obtém as entradas do index.json do catálogo publicado (atualmente exportado no formato v2).
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

A imagem `web/assets/mrstore-hero.webp` é usada no README e no hero da montra.
É um recurso local otimizado em WebP, incluído na lista fechada `ALLOWED` do
staging. O SVG antigo fica disponível apenas como recurso legado. O banner
não anuncia integrações concretas; estas são detalhadas na secção Ecossistema.

A montra só fica online depois de o workflow de publicação da main passar e
GitHub Pages usar a branch gh-pages. Não é um instalador web.

## Testar

    python -m unittest tests/test_storefront.py -v

Para testar a página localmente, usa a pasta dist de uma publicação válida e
um servidor HTTP estático. Abrir web/index.html diretamente a partir de file://
não dá acesso ao index.json publicado.

Não confundir a qualidade visual com certificação de segurança ou prova de funcionamento real em qualquer equipamento.

## Correspondência visual e limites

O README e a homepage usam o mesmo banner local `web/assets/mrstore-hero.webp`,
com monograma M laranja e fundo grafite. Os botões, pesquisa, filtros,
categorias, favoritos e fichas são HTML e JavaScript funcionais, não uma imagem
estática a simular uma aplicação.

A **identidade da marca é universal**. A secção «Ecossistema» apresenta as
plataformas na visão da MrStore e distingue a navegação pública da instalação
nativa. O protocolo efetivamente implementado tem documentação própria no
[guia técnico de integração](ZIMAOS_INSTALLATION.md); não existe garantia
de suporte de loja nativa em todas as plataformas.

A navegação móvel utiliza `details` nativo e o botão «Limpar filtros»
repõe pesquisa, categoria, arquitetura e modo favoritos sem apagar os favoritos
guardados. Os ícones e as capturas são locais, com fallback quando uma imagem
falha. O atributo HTML `hidden` prevalece sobre regras visuais, para que os
controlos indisponíveis não fiquem visíveis.

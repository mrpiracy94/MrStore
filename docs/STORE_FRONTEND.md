# Interface da MrStore: GitHub + GitHub Pages

O GitHub controla o seu próprio layout; não é possível mudar o tema, menus
ou o CSS de github.com para cada repositório. A MrStore apresenta-se em dois
locais distintos:

1. README.md — página de entrada do repositório, com banner, navegação curta,
   instalação, segurança e ligações para documentação.
2. https://mrpiracy94.github.io/MrStore/ — montra web estática com identidade
   azul e escura inspirada no mockup panorâmico, pesquisa, filtros, favoritos e detalhes das aplicações.

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

## Correspondência visual e limites

A interface foi recriada com HTML, CSS e JavaScript funcional, seguindo o
mockup panorâmico azul da MrStore: logótipo em cubo, paisagem noturna,
categorias em mosaico e cartões com capturas **reais do índice publicado**.
O banner vetorial do README é uma interpretação do conceito visual; não é
o PNG original, que ainda não foi acrescentado ao repositório. A montra
não usa uma imagem estática como substituto de botões nem simula instalações.
O botão «Ver detalhes» abre dados reais; a instalação continua a ser feita
no ZimaOS, não diretamente no navegador.

O atributo HTML `hidden` tem prioridade sobre estilos flex para impedir
que ações indisponíveis fiquem visíveis. A pré-visualização de cada app
usa apenas URLs locais do catálogo, com fallback quando a imagem falha.

## Revisão baseada no design Lovable (10-10-2026)

A montra HTML mantém o catálogo aprovado, a política de quarentena e os URLs
locais; o novo `web/assets/lovable.css` aplica o layout da referência enviada:
hero azul-escuro, secção de oito categorias (mapeadas para metadados reais),
quatro aplicações em destaque, cartões com screenshots locais e rodapé compacto.
A secção completa de pesquisa, filtros, favoritos e paginação abre em
«Ver todas as aplicações». Nenhuma aplicação é introduzida artificialmente
no catálogo. «Instalar» abre a ficha e encaminha para a instalação normal no ZimaOS.

O ficheiro `web/assets/hero-scene.svg` é uma **ilustração local de substituição**
e não a fotografia original exportada do Lovable. Para obter uma correspondência
visual exata, substituir só esta imagem por uma fotografia autorizada, mantendo
HTML, interações e regras de segurança.

Um workflow separado `lovable-ui.yml` executa Playwright/Chromium a
1536×864 e 390×844. As capturas de PR são **fixtures sintéticas explicitamente
marcadas**, nunca prova de que as aplicações foram aprovadas ou publicadas.
O workflow do release continua a exigir a seleção de segurança antes de publicar.

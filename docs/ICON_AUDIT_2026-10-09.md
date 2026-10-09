# MrStore — auditoria completa de ícones (2026-10-09)

## Resultado

**254 aplicações analisadas.**

- **165** já tinham ícones diferentes dos SVGs genéricos.
- **89** tinham `Apps/*/icon.svg` provisórios (quadrados com iniciais).
- **25** já tinham fonte oficial/reconhecida indicada no manifesto: os SVGs provisórios foram removidos.
- **55** receberam imagens com nome correspondente do catálogo original LinuxServer.io, com URLs fixados a commit.
- **5** receberam ícones confirmados diretamente no upstream ou no README do fornecedor: Blade of Agony, DOSBox Staging, Luanti, SealSkin e SWAG.
- **4** receberam pictogramas próprios, desenhados especificamente para a função da aplicação (BudgE, Faster Whisper, Modmanager, Socket Proxy), explicitamente não oficiais.

**Total: 89/89 ícones genéricos de letras corrigidos, sem casos desse tipo pendentes.** Em quatro apps fica um `icon.svg` **não genérico** com pictograma original. Os restantes 85 apontam para imagens upstream nas definições.

## Âmbito das alterações

Somente os campos de apresentação `x-casaos.icon` e `x-casaos.thumbnail` (60 manifestos) e os ficheiros visuais `Apps/*/icon.svg` foram alterados. Serviços Docker, volumes, imagens, portas, redes, variáveis, arquitetura, configuração de segurança e outras definições foram preservados.

Fontes, links fixados e autoria documentados em [ICON_SOURCES.md](../ICON_SOURCES.md). Imagens de marcas não representam endosso nem afiliação.

## Validação

1. `python scripts/validate.py` sem erros e `python -m unittest discover -s tests -v` completo.
2. Compilar e publicar todas as 254 aplicações com o builder oficial de ZimaOS v2.
3. Inspecionar `gh-pages/index.json` e confirmar que os 89 ícones corrigidos **não** continuam a usar SVGs provisórios com iniciais.
4. Atualizar a loja no ZimaOS e, se necessário, a cache de imagens do navegador.

A auditoria dos ficheiros fonte não substitui a validação visual no NAS; esta depende de sincronizar o catálogo publicado com a instalação.

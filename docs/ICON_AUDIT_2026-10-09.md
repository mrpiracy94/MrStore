# Auditoria dos ícones da MrStore — 2026-10-09

## Inventário verificado

Foi analisado o `gh-pages/index.json` publicado, com **254 aplicações**.

- 165 entradas tinham ícones diferentes dos SVG de recurso com letras;
- 89 entradas apontavam para os `Apps/*/icon.svg` provisórios;
- 25 entradas já possuíam URLs de logótipos reais no manifesto, mas o builder dava preferência aos SVG locais;
- 55 entradas adicionais têm imagens correspondentes confirmadas no [repositório oficial de modelos LinuxServer.io](https://github.com/linuxserver/docker-templates), com revisão fixada;
- restam **9** aplicações sem fonte de logótipo suficientemente confirmada nesta auditoria.

**Resultado pretendido após compilação e publicação: 245 ícones não provisórios, 9 SVG provisórios**. O resultado final no ZimaOS ainda precisa de ser confirmado depois do build e de eventual atualização de cache.

## Alterações preparadas neste PR

1. Remover 25 SVGs provisórios que sobrepunham URLs reais já existentes, mantendo os manifestos originais.
2. Em 55 manifestos, atualizar **apenas** `x-casaos.icon` e `x-casaos.thumbnail` para imagens correspondentes da LinuxServer.io, com URL fixada a commit; remover os respetivos SVGs provisórios.
3. Acrescentar um teste offline que reprova o caso de um SVG de recurso genérico prevalecer sobre um URL de ícone real.
4. Preservar o restante Compose: serviços, imagens, portas, volumes, redes, recursos, variáveis e segurança não são alterados.

## Pendentes — 9

- `blade-of-agony`
- `budge`
- `dosbox-staging`
- `faster-whisper`
- `luanti`
- `modmanager`
- `sealskin`
- `socket-proxy`
- `swag`

Não substituir estes por logótipos de produtos apenas parecidos sem confirmar a origem.

## Verificação após publicação

1. Executar `python scripts/validate.py` e `python -m unittest discover -s tests -v`.
2. Compilar os 254 manifestos com `IceWhaleTech/build-appstore-action@v1` e validar `dist/index.json`.
3. Confirmar que nenhuma das 80 entradas corrigidas emite o SVG genérico de letras como ícone principal e que as 9 restantes ainda podem usar recurso provisório.
4. Depois do merge e da atualização de `gh-pages`, atualizar a loja ZimaOS e verificar a cache dos ícones.

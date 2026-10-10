# MrStore — expansão editorial 6 → 233 (12 apps por lote)

## Objetivo
Manter **253 manifests** na origem sem SteamOS. Publicar apenas **233**
aplicações na montra, sem apagar as outras **20**. A expansão começa nas
**6** publicadas e tem **19 marcos cumulativos**:

`18, 30, 42, 54, 66, 78, 90, 102, 114, 126, 138, 150, 162, 174, 186, 198, 210, 222, 233`.

Os 18 primeiros lotes adicionam 12 apps cada; o último adiciona 11.
Nunca se publicam 234 por arredondamento.

## Ordem da seleção
`data/rollout-233.json` preserva, primeiro, as seis aplicações
originais (Home Assistant, Immich, Jellyfin, Nextcloud, qBittorrent,
Vaultwarden). Depois inclui as aplicações anteriormente priorizadas na
edição de 112 e, em seguida, expande por ordem alfabética até 233.

A seleção é **editorial**, não se baseia num ranking de downloads.
`data/featured-apps.json` mantém o conjunto final, para referência
futura de builds manuais.

## Execução automática
`.github/workflows/rollout-233.yml` inicia quando a implementação
chega à `main`, ou por acionamento manual. O pipeline:

1. Valida os 253 manifests e o plano de 233.
2. Prepara as definições editoriais do catálogo, mantendo o indicador
   `certification: not_assessed`, e executa o preflight de Compose.
3. Constrói **uma vez** a distribuição oficial de 233 apps.
4. Verifica o conjunto exato de IDs, os ficheiros ZimaOS e as legendas PT.
5. Reempacota e verifica cada marco: índices JSON, diretórios
   `apps/`, arquivo `metadata.tar.gz` e hash `metadata.sha256`.
6. Publica cada marco no `gh-pages` como commit separado. Confirma que
   o estado anterior corresponde ao marco esperado, detém-se se não
   corresponder e pede rebuild de GitHub Pages.
7. Conserva os reports como artifacts para diagnóstico.

Se falhar qualquer passo, a execução **interrompe-se**. Nunca fabrica
resultados de CVE para contornar um bloqueio. A publicação incremental
fica no último marco concluído e uma nova execução pode prosseguir.

## Segurança e limitações
**Estar listado não significa estar certificado.** As 233 entradas
editoriais não são equivalentes às aplicações validadas pela auditoria
com Trivy por imagem e arquitetura. Os avisos da montra devem identificar
sempre o estado `not_assessed`.

O gate de `scripts/release_catalog.py` continua independente para
uma versão **certificada**, com reports completos, digests fixos e
verificações de segurança.

O pipeline não instala apps nos dispositivos, não toca em dados ZimaOS
e não elimina as definições das 20 aplicações adiadas.

Não publicar uma contagem como concluída até confirmar o `index.json`
de `gh-pages` e o resultado do GitHub Pages.

## Verificação local

```bash
python -m unittest discover -s tests -p 'test_rollout_233.py' -v
python scripts/rollout_233.py --plan data/rollout-233.json
```

A primeira publicação tem de partir de exatamente seis aplicações no
índice público. Se outra automação alterar o catálogo entretanto, o
workflow interrompe-se em vez de publicar um estado divergente.

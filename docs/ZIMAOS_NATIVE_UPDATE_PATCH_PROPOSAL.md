# Proposta de correção nativa do ZimaOS App Management

Este documento descreve alterações para manutenção **no código do ZimaOS**.
Não substitui testes do binário ZimaOS 1.7.1 nem altera o sistema através
da MrStore. Foi preparado a partir dos problemas
[#591](https://github.com/IceWhaleTech/ZimaOS/issues/591),
[#592](https://github.com/IceWhaleTech/ZimaOS/issues/592) e do código
**público do CasaOS** que pode partilhar conceitos, mas não é uma cópia
verificada da implementação ZimaOS 1.7.1.

## Falha 1 — nomes dos contentores

O ZimaOS pode procurar `x-casaos.main` como nome de contentor, apesar de
o Docker Compose poder usar `container_name` ou um nome gerado como
`<project>-<service>-1`.

**Algoritmo proposto:**

1. Ler o nome do projeto e o serviço principal da definição **instalada**.
2. Resolver por labels Docker:
   `com.docker.compose.project` e `com.docker.compose.service`.
   Usar as labels para encontrar o contentor efetivo e verificar se
   corresponde à instalação e ao serviço pretendidos.
3. Se houver múltiplos contentores ou nomes ambíguos, devolver
   `unknown_container_ambiguous`, não escolher silenciosamente.
4. Usar `container_name` apenas como compatibilidade/fallback.
5. Não procurar apenas pelo nome curto do serviço; não reinstalar
   nem renomear contentores automaticamente.

## Falha 2 — ausência de RepoDigests

O problema #591 mostra `RepoDigests == []` em imagens instaladas.
Isso **não prova que não haja atualização**. O ZimaOS deve evitar converter
falhas de inspeção em `update_available=false`.

**Algoritmo proposto (tri-state):**

```text
container = resolve_by_compose_labels(project, main_service)
if container ambiguous or missing:
    return UNKNOWN(container_error)

local = docker_container_inspect(container).Image # sha256: OCI config digest
platform = docker_image_inspect(local).Os/Architecture[/Variant]
if platform unsupported or local invalid:
    return UNKNOWN(local_error)

remote_manifest = registry_manifest(approved_target_image, platform)
if registry failed, missing or unsupported manifest:
    return UNKNOWN(registry_error)

remote_id = remote_manifest.config.digest
if local == remote_id:
    return CURRENT
else:
    return CANDIDATE_UPDATE
```

A comparação deve selecionar **a arquitetura instalada** para não
comparar um índice multi-plataforma ao digest de uma imagem AMD64/ARM64
individual. O digest da configuração é o Image ID local do Docker.

`CANDIDATE_UPDATE` não significa que a imagem remota é livre de CVEs,
nem que o upgrade do Compose/volumes está aprovado. Separar os sinais
`remote_image_changed` e `installable_update_approved`.

## Segurança e integridade

- Não usar `docker pull` como mera operação de deteção: a tag local
  pode passar a apontar para uma imagem nova enquanto o contentor
  **continua a executar o ID antigo**. Isso criaria falsos negativos.
- Não executar contentores, não reiniciar serviços nem alterar volumes
  durante a verificação.
- Respeitar credenciais do registry pelo mecanismo oficial do Docker;
  não guardar tokens nos logs nem enviar URL de registos privados ao UI.
- Definir timeouts de registry e proteção contra excesso de pedidos.
- Para imagens `@sha256`, não declarar que estão «atualizadas» por serem
  imutáveis; comparar com **uma referência-alvo aprovada** da loja.
- Manter versão de pacote `x-casaos.version` e identidade real de imagem
  como sinais diferentes.
- Se o UI atual só suporta booleanos, não mapear `UNKNOWN` para falso;
  criar status `check_failed`/«Não foi possível verificar».

## Casos de teste de regressão a exigir no ZimaOS

| Cenário | Resultado esperado |
| --- | --- |
| `RepoDigests=[]`, Image ID local = config digest remoto | CURRENT |
| `RepoDigests=[]`, Image ID local != config digest remoto | CANDIDATE_UPDATE |
| `docker pull` recente, tag local nova, contentor antigo | CANDIDATE_UPDATE |
| Serviço `app`, `container_name=portainer-agent` | Resolução por labels |
| Nome Compose gerado `big-bear-ntfy-app-1` | Resolução por labels |
| Duas réplicas, múltiplos contentores | UNKNOWN se ambíguo |
| Registry indisponível / autenticação falhou | UNKNOWN |
| Imagem ARM64 instalada e índice remoto AMD64+ARM64 | Comparar apenas ARM64 |
| Imagem de múltiplos serviços, principal sem atualização | Indicar estado por serviço, evitar afirmar Compose totalmente atualizado |
| Sem ligação à loja ou versão instalada desatualizada no catálogo | UNKNOWN/contexto explícito, nunca atualização fictícia |

## Referência executável

A MrStore tem um protótipo read-only desta comparação na
[PR #90](https://github.com/mrpiracy94/MrStore/pull/90). Foi também
preparada uma Action com fixture Docker real (contentor criado mas nunca
iniciado) para confirmar os estados `same_image` e
`candidate_update`.

Uma correção nativa só ficará comprovada depois de integração pelos
responsáveis do ZimaOS e execução dos testes num NAS com interface
de atualização real.

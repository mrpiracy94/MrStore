# ZimaOS — detetar atualizações reais mesmo sem RepoDigests

## Porque isto existe

No ZimaOS 1.7.1 os problemas conhecidos
[#591](https://github.com/IceWhaleTech/ZimaOS/issues/591) e
[#592](https://github.com/IceWhaleTech/ZimaOS/issues/592) podem impedir o
gestor nativo de detetar atualizações. Alterar `x-casaos.version` ou
`content_hash` numa loja externa **não repara** o gestor de containers
instalados.

O comando `scripts/oci_installed_update_check.py` recolhe de forma
**só leitura** o `Image ID` exato que o contentor instalado utiliza
(`docker container inspect`) e a arquitetura da respetiva imagem
(`docker image inspect`). Obtém do registry o
`manifest.config.digest` **para a mesma plataforma** usando
`crane manifest --platform`, sem executar `docker pull`.

O Docker Image ID é o digest da configuração OCI; os dois valores são
comparáveis para a mesma imagem/plataforma, inclusive com
`RepoDigests == []`.

## Uso no NAS com Docker CLI

Requer Python 3 e a ferramenta `crane` instalada na máquina de
diagnóstico. Exige acesso **de leitura aos metadados Docker**;
considere que acesso ao Docker socket é altamente privilegiado.
Não expor o socket em rede nem montar o socket em contentores apenas
para esta verificação.

```bash
python scripts/oci_installed_update_check.py --container sonarr
```

Com `--target` pode indicar explicitamente a referência de substituição
da mesma origem:

```bash
python scripts/oci_installed_update_check.py \
  --container sonarr \
  --target lscr.io/linuxserver/sonarr:latest \
  --output out/sonarr-update-evidence.json
```

Atenção: uma imagem aprovada e publicada na MrStore costuma estar
**fixada por digest**, para manter a compatibilidade com os scans de
segurança. Quando a referência usada pelo contentor é imutável, o modo
sem `--target` devolve `unknown` e
`immutable_reference_no_floating_target` de propósito. Passar
`--target latest` verifica uma **candidata** no registry, mas não
significa que passou os scans de segurança da MrStore. Para validar uma
substituição aprovada, deve indicar o digest efetivamente aprovado no
catálogo publicado.

## Interpretação

| `status` | Significado |
| --- | --- |
| `candidate_update` | A configuração da imagem remota, para a arquitetura do NAS, é diferente da imagem efetivamente usada pelo contentor. Candidata a atualização, ainda não aprovada |
| `same_image` | IDs das configurações iguais. Sem alteração de imagem entre as duas referências verificadas |
| `unknown` | Não é seguro declarar o estado; verificar `reason` (registry indisponível, conteúdo imutável, referência ou plataforma ambígua, etc.) |

**Importante:** esta ferramenta **não cria notificações nativas** no ZimaOS.
Não repara bugs do binário fechado, não altera apps instaladas,
não efetua operações de escrita no Docker, não executa aplicações
não verificadas nem interpreta igualdade de hash como garantia de
ausência de CVEs. Não compara versões semânticas de aplicações; compara
identidade da imagem realmente instalada contra a candidata remota.

## Verificações e evidência

- Testes de regressão sem Docker ou acesso a redes verificam
  `RepoDigests` ausentes, arquiteturas ARM64, diferenças, resultados
  iguais, manifest inválido, falhas de acesso e proibição de comandos
  que alterem contentores.
- `docker image inspect --format '{{.RepoDigests}}'` pode devolver `[]`,
  mas a identidade OCI da configuração continua disponível através de
  `docker container inspect <name> --format '{{.Image}}'`.
- [crane manifest (documentação oficial)](https://github.com/google/go-containerregistry/blob/main/cmd/crane/doc/crane_manifest.md)
- [Docker container inspect](https://docs.docker.com/reference/cli/docker/container/inspect/)
- [Docker image inspect](https://docs.docker.com/reference/cli/docker/image/inspect/)

Próxima etapa no ZimaOS nativo: o App Management deve passar a resolver
os contentores de acordo com os nomes/labels do Compose e a reportar
`unknown` quando não consegue obter a informação local, ao invés
de declarar `update_available=false`.

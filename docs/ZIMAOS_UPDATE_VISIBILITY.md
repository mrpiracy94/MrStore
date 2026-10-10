# ZimaOS — porque não aparece a atualização de uma app?

A MrStore tem **dois circuitos separados**: a atualização do catálogo ZimaOS v2
(`index.json`, `content_hash`, versão do pacote MrStore) e a decisão do
**ZimaOS instalado** de mostrar a ação "Atualizar". Uma alteração da versão do
pacote no catálogo não obriga o gestor do ZimaOS a mostrar um novo update.

## Problemas documentados no ZimaOS 1.7.1

- [#591](https://github.com/IceWhaleTech/ZimaOS/issues/591): para uma imagem
  `:latest`, se `docker image inspect ... .RepoDigests` estiver vazio, o
  gestor pode concluir erradamente "sem atualização". Não é possível inferir a
  versão instalada só pela tag.
- [#592](https://github.com/IceWhaleTech/ZimaOS/issues/592): em alguns cenários
  o gestor procura um contentor com o **nome do serviço principal**, ignorando
  o `container_name` ou o nome gerado pelo Docker Compose. A verificação falha
  antes de consultar o digest.
- [#570](https://github.com/IceWhaleTech/ZimaOS/issues/570): a equipa indicou
  que a lógica de atualizações ainda pode comparar referências de imagens em
  vez de comparar `x-casaos.version`. Atualizar metadados não é uma correção
  garantida para o gestor nativo.

## Auditoria de catálogo (sem NAS)

No checkout da MrStore, com Python e as dependências de `requirements.txt`:

```bash
python scripts/zimaos_update_visibility.py
```

A Action `Validate MrStore` também executa esta auditoria e disponibiliza os
artefactos `zimaos-update-visibility` em JSON e Markdown.

A auditoria identifica quais os manifests cujo serviço `x-casaos.main`
não tem `container_name` explícito ou não coincide com ele, e quais as
imagens principais que usam `:latest`. **São riscos de compatibilidade**,
não garantias de erro nem prova de desatualização.

## Prevenir novas apps invisíveis às atualizações

A Action `Validate MrStore` executa também
`python scripts/zimaos_update_visibility.py --strict-main-name`.
Bloqueia **novos** manifests cujo `x-casaos.main` não tem
`container_name` explícito igual ao serviço principal, porque são
incompatíveis com o comportamento reportado no ZimaOS 1.7.1 (#592).
Esta regra não cria CVEs, não altera contentores existentes e **não**
bloqueia apps apenas por usarem `:latest` — isso é uma condição
diagnosticada no NAS, não uma prova de falha no repositório.

## Diagnóstico voluntário num ZimaOS real (só leitura)

É necessário executar no **próprio NAS** com o repositório MrStore acessível,
Python 3 e PyYAML instalados e Docker CLI acessível. Executar apenas numa app
existente (exemplo: Sonarr):

```bash
python scripts/zimaos_update_visibility.py --runtime --app sonarr
```

Esta opção usa apenas consultas de leitura (`docker ps -a`,
`docker container inspect` e `docker image inspect`). Primeiro procura o
contentor através das etiquetas Docker Compose
`com.docker.compose.project` + `com.docker.compose.service`.
**Não inspeciona contentores encontrados apenas pelo nome**: um contentor
chamado `app` pode pertencer a outra aplicação. Se faltar a identidade
Compose, a ferramenta informa **estado desconhecido** e exige diagnóstico
manual, sem assumir atualização disponível ou ausência dela.
A existência de várias réplicas é reportada como ambígua, sem adivinhar uma
imagem a comparar. Instalações antigas com nomes de projeto diferentes
também podem necessitar de diagnóstico manual.
Compara o digest da
**imagem efetivamente usada pelo contentor** através do seu ID imutável
(`docker container inspect ... --format '{{.Image}}'`) — não a tag
`:latest`, que pode ter mudado após um `docker pull` sem recriar o
contentor. Se o ID não for obtido, o estado é **desconhecido**, nunca
«atualizado». Não executa `docker pull`, `docker compose up`, instalação,
atualização ou restart.

Para consultar também o digest remoto, sem fazer pull, quando o binário
[`crane`](https://github.com/google/go-containerregistry/tree/main/cmd/crane)
estiver instalado:

```bash
python scripts/zimaos_update_visibility.py --runtime --app sonarr --registry-check
```

Se for conhecida a porta **local** do serviço `zimaos-app-management`, também
é possível observar a listagem nativa (a API pode exigir autenticação):

```bash
python scripts/zimaos_update_visibility.py --runtime --app sonarr --api-base http://127.0.0.1:PORT
```

A porta `PORT` é um marcador; confirmar a porta real antes de executar.
Nunca usar endereço público ou credenciais nessa opção. O resultado
`not_listed_not_proof_of_current` **não** significa que a imagem esteja
atualizada. O comando não altera os dados nem corrige o serviço nativo do
ZimaOS.

## Como interpretar o relatório

| Sinal | Significado | Abordagem |
| --- | --- | --- |
| `main_container_name_differs_from_service` | Possível bug #592; ZimaOS pode procurar o nome errado | Rever caso a caso; não renomear contentores de apps instaladas em massa |
| `main_container_name_not_explicit` | Nome gerado pelo Compose pode ser diferente do serviço | Validar como o ZimaOS resolve a app instalada |
| `latest_requires_usable_local_repodigest` | Possível bug #591 **se** faltar o digest no Docker local | Inspecionar `RepoDigests`; não presumir update |
| `unknown_missing_repodigests` | Não há prova local suficiente para comparar digests | Falha de deteção possível; confirmar registos do App Management |
| `unknown_ambiguous_main_containers` | Várias réplicas partilham o serviço principal | Não escolher um contentor aleatório; comparar todas as réplicas num teste dedicado |
| `container_resolution=unverified_named_container_ignored` | Existe um nome esperado mas não há labels Compose que confirmem a identidade | Contentor deliberadamente não inspecionado; confirmar manualmente o projeto/serviço |
| `unknown_no_matching_repository_digest` | O ID da imagem tem RepoDigests, mas nenhum pertence ao mesmo repositório do catálogo | Não comparar digests de repositórios diferentes; rever a origem da imagem |
| `digest_differs_review_required` | Hash remoto e local diferem; requer revisão da plataforma/imagem | Não atualizar sem confirmar segurança e compatibilidade |
| `listed_as_upgradable` | API nativa devolve entrada correspondente | Confirmar também que a UI reflete esse resultado |
| `not_listed_not_proof_of_current` | App ausente da listagem da API | **Não é** prova de que esteja na versão mais recente |
| `candidate_native_false_negative_review_required` | Digest da imagem em execução difere do digest consultado, mas a app não surge na API nativa | Possível falso negativo; confirmar arquitetura, referência aprovada e política CVE antes de atualizar |
| `possible_main_service_lookup_bug_592` | Labels Docker Compose identificam o contentor, mas não existe contentor com o nome do serviço principal e a API não mostra update | Comparar logs do ZimaOS; não renomear contentores em massa |
| `possible_missing_repodigests_bug_591` | Faltam RepoDigests e a API não mostra update | Estado indeterminado; não assumir que existe upgrade nem que está atualizado |

Para diagnóstico adicional, verificar os logs de forma manual:

```bash
grep -E 'no digests found|no latest digest found|failed to inspect container' /var/log/casaos/mod-management.log | tail -n 20
```

Os `RepoDigests` associados ao mesmo ID podem incluir vários repositórios.
O diagnóstico normaliza aliases do Docker Hub e compara **apenas o repositório
pretendido**. Se só encontrar digests de outros repositórios, o estado fica
desconhecido em vez de falso «atualizado». A comparação de digest remoto
também pode variar por arquitetura/manifest list; diferenças são **candidatas
a revisão**, não ordens de atualização automática.

## Limite atual

Sem um NAS ligado ao processo, esta ferramenta não pode validar o badge no
dashboard real. O código-fonte fechado/serviço instalado do ZimaOS não é
alterado por uma loja externa. Não vamos falsificar tags, fazer pull
silencioso nem ignorar CVEs para produzir o botão "Atualizar".

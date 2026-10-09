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

## Diagnóstico voluntário num ZimaOS real (só leitura)

É necessário executar no **próprio NAS** com o repositório MrStore acessível,
Python 3 e PyYAML instalados e Docker CLI acessível. Executar apenas numa app
existente (exemplo: Sonarr):

```bash
python scripts/zimaos_update_visibility.py --runtime --app sonarr
```

Esta opção usa somente `docker ps -a` e `docker image inspect`. Não executa
`docker pull`, `docker compose up`, instalação, atualização ou restart.

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
| `digest_differs_review_required` | Hash remoto e local diferem; requer revisão da plataforma/imagem | Não atualizar sem confirmar segurança e compatibilidade |
| `listed_as_upgradable` | API nativa devolve entrada correspondente | Confirmar também que a UI reflete esse resultado |
| `not_listed_not_proof_of_current` | App ausente da listagem da API | **Não é** prova de que esteja na versão mais recente |

Para diagnóstico adicional, verificar os logs de forma manual:

```bash
grep -E 'no digests found|no latest digest found|failed to inspect container' /var/log/casaos/mod-management.log | tail -n 20
```

A comparação de digest remoto pode variar por arquitetura/manifest list,
portanto diferenças devem ser tratadas como **candidatas a atualização**,
não como ordem para atualizar automaticamente.

## Limite atual

Sem um NAS ligado ao processo, esta ferramenta não pode validar o badge no
dashboard real. O código-fonte fechado/serviço instalado do ZimaOS não é
alterado por uma loja externa. Não vamos falsificar tags, fazer pull
silencioso nem ignorar CVEs para produzir o botão "Atualizar".

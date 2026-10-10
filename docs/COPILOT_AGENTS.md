# Agentes GitHub Copilot da MrStore

A MrStore tem **6 agentes especializados** em `.github/agents/`: `coordinator`, `security-cve`, `dependency-updates`, `platform-compatibility`, `storefront-ui` e `operations-ci`. As instruções comuns vivem em `.github/copilot-instructions.md`.

## Trabalho automático existente e o que foi acrescentado

Ações existentes: CVEs Trivy (`cve-scan.yml`), auditoria de release e publicação (`publish.yml`), atualizações de imagens (`update-monitor.yml`), atualidade dos builds (`image-freshness.yml`), watchdog de manutenção e descoberta de novas apps. O Renovate já propõe PRs de versões/digests. Não substituímos nem duplicámos estes workflows.

Novo workflow: **MrStore Copilot agent queue**, diário às 08:13 UTC, agendamento + execução manual. Lê Issues e PRs abertos; classifica CVEs, atualizações, plataformas, montra e operações; ignora tarefas que exigem testes em equipamento real, migrações e backups; ignora issues já com PR, delegadas ou atribuídas. Emite relatórios JSON/Markdown nos artefactos e no Job summary. Máximo **2 atribuições por execução**, nunca faz merge, deploy nem fecha issues.

## Ativar trabalho autónomo com Copilot

1. É necessário **GitHub Copilot pago**, Copilot cloud agent ativado para o utilizador e repositório. Os perfis só ficam selecionáveis no GitHub depois do merge para `main`.
2. Criar um **personal access token de utilizador** (não `GITHUB_TOKEN` de Actions) com as permissões de atribuição requeridas pela API Copilot: Metadata (read); Actions, Contents, Issues e Pull Requests (read/write). Nunca escrever o token no repositório ou em issues.
3. Guardar o token em **Settings → Secrets and variables → Actions → New repository secret**, com o nome `COPILOT_ASSIGN_TOKEN`.
4. A partir desse momento, o agendamento diário passa do modo auditoria para o modo `auto` (até 2 issues elegíveis/dia). Sem secret, só há auditoria: **nenhum agente é efetivamente executado**.
5. Para experimentar sem delegar: Actions → **MrStore Copilot agent queue** → Run workflow → `audit`. Para delegar um issue elegível: selecionar `assign` e o número do issue, depois verificar a atribuição e a PR criada.

O workflow usa a API REST oficial para `copilot-swe-agent[bot]` com `agent_assignment.custom_agent`. A API está em preview e pode evoluir; qualquer erro na confirmação da atribuição faz o job falhar. A etiqueta `agent:delegated` impede recolocar a mesma issue na fila depois de uma execução concluída. Removê-la é uma decisão humana.

## Limites e provas

- Uma PR gerada por IA é **proposta de código**, não prova de CVE corrigida, plataforma instalada, testes C3 ou publicação.
- Uma release só pode avançar com auditoria completa e aprovação do gate existente em `publish.yml`. Nunca confundir jobs `skipped` com testes aprovados.
- A existência de PRs relacionadas com um issue bloqueia a delegação para evitar duplicação; verificar a fila bloqueada quando se quiser retomar.
- Para suspender a atribuição, remover/rodar o secret `COPILOT_ASSIGN_TOKEN` ou usar modo `audit` manual. O agendamento sem secret mantém somente a fila informativa.
- Em casos de dados persistentes, permissões elevadas ou testes no NAS, é obrigatória uma revisão humana.

Referências: [Custom agents](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/create-custom-agents) · [API Copilot cloud agent](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/cloud-agent/use-cloud-agent-via-the-api).

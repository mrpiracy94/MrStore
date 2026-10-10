# MrStore — caixa de ferramentas de diagnóstico no GitHub Actions

A workflow **MrStore issue diagnostics toolbox** permite identificar, por issue,
quais os workflows relacionados, os estados dos últimos runs na branch principal
e os jobs/passos que falharam. Não instala aplicações, não atualiza containers
e não esconde vulnerabilidades. Não faz merges nem fecha issues.

## Executar manualmente

1. Abrir **Actions → MrStore issue diagnostics toolbox → Run workflow**.
2. Escolher a área: **all**, **cve**, **publication**, **updates**, **maintenance**,
   **security**, **migrations**, **compatibility**, **dependencies** ou **ci**.
3. Opcionalmente indicar um **issue_number** (por exemplo: 94, 95 ou 19). Para
   investigar apenas um issue, usar uma área correspondente ou **all**.
4. Abrir o **Job summary** do run para ver os próximos passos, e descarregar
   o artifact **mrstore-issue-diagnostics** com report.json e report.md.

A workflow corre também semanalmente, às segundas-feiras às 08:37 UTC.
Quando for aberta uma PR que altera o diagnóstico, são executados **apenas
testes offline**; o levantamento de issues via API não corre nas PRs.

## Exemplos

| Foco | Issue exemplo | O que aparece |
| --- | --- | --- |
| publication | #94 | Runs de catalog-uptime e publish, link para os checks e guia de evidência |
| maintenance | #95 | Estado do watchdog e da verificação de disponibilidade |
| cve | #19 | Identificação do shard e acesso à auditoria CVE e às tentativas de scan |
| updates | #8 | Estado dos relatórios de alterações de digests e builds antigos |
| migrations | #58 | Gates de migração e exigência de backup/restore |
| security | #53 | Workflow de prova da API read-only e gate de migração |
| compatibility | #45 | Testes estáticos disponíveis; validação real C3 no ZimaOS ainda é manual |

## O que mede, e o que NÃO mede

- Consulta a API do GitHub com o **GITHUB_TOKEN** concedido automaticamente
  pelo Actions, com permissões estritamente de leitura.
- Consulta a listagem de issues e PRs abertos, e até 5 execuções recentes
  por workflow relevante, restritas à branch **main**.
- Se o último run falhou, lê só os **metadados dos jobs e nomes dos passos
  falhados**, não descarrega logs brutos que podem conter segredos.
- O relatório pode indicar "concluido": **isso não significa CVE=0 nem que
  a aplicação funciona no ZimaOS**. Não transforma uma CI verde em prova C3.
- Se a API estiver indisponível, gera um relatório de estado "incomplete"
  e o workflow falha. Não declara falsamente ausência de issues.
- Não executa scans Trivy duplicados (para isso usar cve-scan.yml /
  trivy-dualarch-inventory.yml quando este estiver aprovado), não instala
  nem publica imagens, não cria nem fecha issues e não modifica manifests.

A lista de categorias e workflows associados é controlada em
scripts/actions_issue_triage.py e coberta em tests/test_actions_issue_triage.py.
Se o repositório ganhar workflows novos, atualizar esse mapa e os testes,
sem introduzir referências a workflows ainda não publicados.

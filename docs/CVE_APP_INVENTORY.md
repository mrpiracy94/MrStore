# Auditoria CVE por aplicação A–Z (254 manifests)

## Porque existe

A MrStore usa 254 manifests Docker Compose, mas várias aplicações podem
compartilhar uma das 258 referências de imagens. Os workflows Trivy produzem
relatórios **por imagem e por arquitetura**, organizados em 8 shards. Este
relatório converte essa evidência para uma listagem **alfabética de todas as
aplicações** e mostra quais ainda carecem de prova, sem executar novos scans.

## Como executar no GitHub Actions

1. Executar ou concluir a auditoria Trivy que cria oito artifacts
   \`release-cves-shard-0.json\` ... \`release-cves-shard-7.json\`.
2. Copiar o **Run ID** dessa execução.
3. Abrir **Actions → MrStore CVE per-app inventory A-Z → Run workflow**.
4. Selecionar a mesma branch/commit e preencher \`scan_run_id\`.
   **Se o commit da auditoria e o commit da execução do relatório forem
   diferentes, o workflow recusa a comparação**.
5. Descarregar o artifact \`mrstore-cve-app-inventory-a-z\`:
   - \`cve-apps.md\` — tabela A–Z e pendências
   - \`cve-apps.csv\` — folha para filtrar e ordenar
   - \`cve-apps.json\` — resultados por app, por referência de imagem e CVEs

É possível usar o workflow enquanto parte dos oito shards ainda estão em
fila. Os shards em falta aparecem explicitamente em \`shard_warnings\`;
as aplicações que precisam dessas imagens ficam \`PENDING_EVIDENCE\`.

## Estados e decisões

| Estado | Significado |
| --- | --- |
| CVE_DETECTED | HIGH/CRITICAL detetada numa imagem referenciada pela app |
| SCAN_ERROR | Scanner, digest ou cobertura de plataforma falhou |
| PENDING_EVIDENCE | Falta pelo menos uma imagem no conjunto dos relatórios |
| CLEAN_IN_AVAILABLE_EVIDENCE | Todas as imagens da app têm observações limpas no conjunto recebido |

**CLEAN_IN_AVAILABLE_EVIDENCE não é aprovação de publicação.** O campo
\`final_release_approved\` permanece sempre \`false\`. A autorização de
publicação é competência exclusiva do \`scripts/release_catalog.py\` com
validação completa dos oito shards, digests exatos, permissões e Compose.
Não se deve interpretar uma pipeline verde de diagnóstico como CVE zero,
compatibilidade física ou ausência de riscos futuros.

Os totais HIGH/CRITICAL agregam observações **por arquitetura**, podendo
repetir a mesma CVE em AMD64 e ARM64. A coluna \`cves\` apresenta IDs
deduplicados para a app na evidência consultada. Quando uma imagem partilhada
é vulnerável, todas as aplicações que a utilizam necessitam de revalidação.

Os relatórios são de diagnóstico, sem modificações a apps, ZimaOS,
segredos ou dados persistentes. O workflow tem apenas permissões de leitura
e não descarrega logs de acesso privado.

## Validação local sem rede

\`\`\`bash
python -m unittest discover -s tests -p 'test_cve_app_inventory.py' -v
python scripts/cve_app_inventory.py --evidence out/release-evidence --output out/cve-apps
\`\`\`

O script exige as dependências do projeto em \`requirements.txt\`, mas
não executa Docker, Trivy ou instalações. Ficheiros ausentes, malformados
ou incompatíveis com o inventário fonte nunca são contados como limpos.

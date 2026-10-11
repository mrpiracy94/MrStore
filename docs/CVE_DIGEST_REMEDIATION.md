# MrStore — redução real de CVEs pela atualização de digests

Esta verificação não troca o fornecedor nem altera os manifestos. Para seis
aplicações com interesse operacional (qBittorrent, FreshRSS, Obsidian, Homarr,
Glances e RPCS3), compara a imagem fixada por SHA256 em Apps/ com o digest
atual da mesma tag publicada pelo mesmo fornecedor.

Executar numa máquina com crane, Trivy e PyYAML:

python scripts/cve_digest_refresh.py --app freshrss

A pipeline .github/workflows/cve-digest-remediation.yml permite repetir a
medição em GitHub Actions sem instalar contentores e grava JSON/Markdown
por aplicação.

Critérios:
- O digest de partida tem de coincidir com data/image-digests.json;
  divergências bloqueiam a comparação.
- Se a tag ainda aponta para o mesmo digest, classificar unchanged.
- Se mudou, analisar os dois digests em AMD64 e ARM64 por Trivy.
- Apenas classificar como redução observada se as CVEs HIGH e CRITICAL
  não aumentam, e alguma diminui, em TODAS as arquiteturas declaradas.
- Falhas de registry, resultados inválidos ou ausência de arquitetura são
  inconclusivos; não declarar CVEs iguais a zero.
- Não aplicar automaticamente: as contagens não revelam introdução de
  vulnerabilidades diferentes, risco de exploração, nem compatibilidade.

Depois de um candidato com melhoria:
1. Verificar release notes do fornecedor e eventual atualização de major.
2. Fazer backup da configuração/volumes e teste de persistência/rollback.
3. Inspecionar mudanças em entrypoints, dados e arquitetura.
4. Atualizar APENAS os Compose afetados e data/image-digests.json,
   mantendo tags rastreáveis e identificadores das 254 aplicações.
5. Validar scripts/verify_source_digests.py e toda a pipeline. Repetir
   Trivy com o digest final para demonstrar a diferença antes/depois.

O total anterior de CVEs não diminui pelo facto de ter sido criado
um comparador. Só uma imagem efetivamente substituída e novamente
analisada conta como remediação confirmada.

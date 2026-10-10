# Gitea — remediação focalizada de CVEs Alpine

Esta experiência conserva a variante **rootful** de `gitea/gitea:latest` e aplica `apk upgrade --no-cache` aos pacotes vulneráveis da imagem base. Não muda a pasta persistente `/DATA/AppData/gitea:/data`, nem as portas externas 30000/30001, nem o SSH interno 22. A variante *rootless* oficial não é diretamente compatível com os diretórios/SSH do manifesto antigo (documentação Gitea).

A auditoria do grupo CVE #19 encontrou **0 CRITICAL/4 HIGH**, todos com correções reportadas, mas o resultado desta candidata é desconhecido até terminarem os testes Trivy em **AMD64 e ARM64**. Este PR não altera apps, não publica a imagem e não fecha issues CVE antes de uma versão corrigida, digest imutável e smoke test funcionais. Uma atualização de segurança nunca deve converter rootful em rootless apenas para eliminar alertas.

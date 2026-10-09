# SteamOS descontinuado — bloqueio de publicação segura

A imagem `lscr.io/linuxserver/steamos:latest` foi formalmente descontinuada pelo LinuxServer.io e a auditoria AMD64 identificou falta de plataforma disponível. Fonte: https://info.linuxserver.io/issues/2025-12-13-steamosdep/

Esta imagem permanece na **origem** do catálogo MrStore para não eliminar dados nem disfarçar a pendência de manutenção. Contudo, `scripts/release_catalog.py` deve sempre manter a app em **quarentena**, independentemente de algum scanner devolver zero vulnerabilidades. Um resultado Trivy limpo não prova que software abandonado seja seguro ou instalável.

- O bloqueio é específico à referência descontinuada, em vez de negar todas as apps antigas.
- O `release-status.json` indica os motivos concretos da quarentena; nada é silenciosamente excluído.
- Uma futura alternativa à imagem requer validação real de compatibilidade, funcionalidades e arquitetura, e testes CVE em AMD64/ARM64 com imagem fixada por digest.
- Não equivale a remediação das outras imagens do [issue #64](https://github.com/mrpiracy94/MrStore/issues/64), nem a instalação comprovada no ZimaOS.

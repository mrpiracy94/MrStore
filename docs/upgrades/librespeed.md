# librespeed — atualização de segurança por SHA256

## Evidência
GitHub Actions: https://github.com/mrpiracy94/MrStore/actions/runs/38252296826

Resultado Trivy por arquitetura (12 de outubro de 2026): 9 HIGH → 0 HIGH; 0 CRITICAL em AMD64 e ARM64.
A imagem e a tag do fornecedor original desta instalação não mudam; apenas o digest.
A medição CVE não certifica ausência de vulnerabilidades nem compatibilidade real.

## Backup
Guardar o Compose atual, o digest anterior `sha256:cebf3af16a406cbdaa49a27266371fa21228901c3d5e5efad54bbd56350335f6` e uma cópia integral de `/DATA/AppData/librespeed/config` se existir, incluindo base de dados e definições. Confirmar que o backup pode ser recuperado. Não remover volumes.

## Migração
Apenas atualizar o digest da imagem mantendo as portas, volumes, ambiente, UID/GID e identificador de aplicação existentes. Em ambiente isolado, verificar release notes do fornecedor antes de atualizar a instalação e testar o eventual esquema de dados.

## Testes
Validar arranque, login, interface, funcionalidades principais, persistência após reinício e funcionamento AMD64/ARM64. O Trivy foi executado; testes em NAS/ZimaOS real ainda estão pendentes.

## Rollback
Parar o contentor de teste, recuperar o digest anterior e restaurar a configuração e/ou dados do backup se tiver ocorrido uma migração incompatível. Não eliminar dados persistentes.

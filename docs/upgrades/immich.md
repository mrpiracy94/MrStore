# immich — fixação imutável da imagem por digest

## Backup
PostgreSQL 14 + VectorChord e a biblioteca de imagens/vídeos em /DATA/AppData/immich. Antes de atualizar, guardar cópia consistente da base de dados e das fotografias. Confirmar DB_PASSWORD e POSTGRES_PASSWORD iguais; nunca atualizar major PostgreSQL sobre a pasta existente. Guardar uma cópia fora do NAS, verificar que é legível e registar o digest de origem.

## Migração
Esta alteração acrescenta @sha256 à MESMA tag de imagem no Compose, sem modificar volumes, serviços, portas ou variáveis. A tag antiga era móvel: o conteúdo efetivo que executava anteriormente pode não coincidir com o digest agora aprovado. Confirmar arquitetura, suporte upstream e notas de migração específicas ANTES de atualizar. Nunca executar migrações automáticas de base de dados por causa desta fixação.

## Testes
Em host/VM de ensaio com cópias dos dados, testar instalação e reinício, interface/login, leitura e escrita, serviços dependentes, manutenção de permissões e integridade dos dados. Testar AMD64 e ARM64 quando aplicável. Estes testes de runtime ainda não são prova de execução na máquina do utilizador.

## Rollback
Guardar previamente o Compose e o digest antigos juntamente com o backup. Se ocorrer falha, parar o contentor, restaurar a imagem anterior por digest conhecido e, se necessário, os dados a partir do backup consistente. Não usar docker compose down -v. Testar o restauro antes de voltar a disponibilizar o serviço.

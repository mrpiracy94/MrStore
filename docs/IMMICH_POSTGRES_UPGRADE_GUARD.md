# Immich — bloqueio de upgrades diretos PostgreSQL 14 → 16

O manifesto atual utiliza `ghcr.io/immich-app/postgres:14-vectorchord0.4.3-pgvectors0.2.0`
e monta `/DATA/AppData/immich/postgres` em `/var/lib/postgresql/data`.
O script de revisão de PRs deteta upgrades **major** nesta imagem e rejeita
automaticamente mudar a tag para PG15/PG16/PG17 enquanto reutiliza o mesmo
diretório de dados ou omite o volume. Também bloqueia downgrades major in-place.

## Porquê

Os formatos internos de um diretório PostgreSQL de uma versão principal não são
automaticamente compatíveis com outra versão. Apontar PG16 para o PG14 original
pode impedir arranque ou causar danos. A imagem atual já usa VectorChord,
mas as extensões e índices devem ser comparados e testados após migração.

## Caminho correto de migração

1. Recolher versões reais de Immich, PostgreSQL, VectorChord/pgvector, arquitetura
   e ficheiros de dados de uma instalação ZimaOS de ensaio.
2. Garantir backups consistentes da base e da biblioteca de fotos, isolados
   do volume ativo. Verificar que a recuperação do backup funciona.
3. Criar um **novo** diretório persistente para PG16; nunca reutilizar o diretório
   PG14 em comandos de PG16 sem procedimento oficialmente comprovado.
4. Fazer dump/restore ou migração compatível segundo documentação PostgreSQL e
   Immich num ambiente **descartável** com dados sintéticos. Testar criação
   e consulta de fotos, índice vetorial, extensões e persistência após reinício.
5. Revisar CVEs HIGH/CRITICAL nas arquiteturas AMD64/ARM64 e fixar digest imutável.
6. Propor em PR individual o novo caminho/digest, com `docs/upgrades/immich.md`
   contendo **backup, migração, testes e rollback** com provas reais.
7. Em rollback, reinstalar PG14 somente com o diretório PG14 preservado,
   **não** tentar apontá-lo ao diretório PG16 migrado.

## Limites

O teste novo é estático e offline. Não executa containers nem acessa dados.
Alterar o caminho do volume elimina apenas o bloqueio específico de reutilizar
o diretório anterior; **não prova backup, restore, compatibilidade ou C3 no ZimaOS**.
O gate geral `Review risky app migrations` continua a exigir documentação da
migração e revisão. O issue #58 só fecha após testes operacionais.

Documentação oficial:
- https://docs.immich.app/install/upgrading/
- https://docs.immich.app/administration/backup-and-restore/
- https://docs.immich.app/administration/postgres-standalone/

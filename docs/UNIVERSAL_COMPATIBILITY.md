# MrStore Universal — fase 1: CasaOS e Homeio (pré-visualização)

A origem `Apps/<slug>/docker-compose.yml` continua única. A integração oficial
ZimaOS v2 **não é alterada**. A nova exportação é um pacote ZIP de origem
CasaOS/Homeio, com `Apps/`, `x-casaos` e metadados na raiz.

## Segurança (obrigatória)

**Não** usar o ZIP da branch `main` do GitHub: essa origem inclui apps
com CVEs, configuração incompleta ou em quarentena.

O novo exportador **só aceita** `release-source` e
`out/release-selection.json` gerados pela auditoria de oito shards Trivy.
Verifica que o conjunto de apps coincide exatamente com o aprovado, que todas
as imagens têm digest SHA256 e que não existem segredos `CHANGE_ME`,
volumes com Docker socket, `privileged`, host networking ou symlinks.
Falha sem produzir um ZIP quando algo diverge.

Após uma publicação segura e bem-sucedida, o pacote provisório estará em:

`https://mrpiracy94.github.io/MrStore/store/casaos-homeio-preview.zip`

A ausência do ZIP significa que **ainda não há** uma edição compatível aprovada.
Nunca fazer fallback para o ZIP com as 254 apps não filtradas.

## Estado de compatibilidade

- **ZimaOS:** mantém-se o processo atual de release, sem alterações.
- **Homeio:** suporta arquivos da loja CasaOS. O formato `Apps/` com
  `x-casaos` é um candidato. Ainda faltam testes reais de importação,
  instalação, persistência e atualização.
- **CasaOS:** a exportação é um **pacote de origem de pré-visualização**, não
  uma certificação de arquivo legado v1 (que pode requerer `build/sysroot`
  e setup específicos). O importador de cada versão precisa de ensaio real.
- **UmbrelOS:** será desenvolvido num segundo adaptador, com manifestos
  `umbrel-app-store.yml`, `umbrel-app.yml` e Compose, em PR separada.
  Não reutilizar diretamente este ZIP como loja Umbrel.

## Testar numa máquina de ensaio

1. Confirmar o SHA, `release-status.json` e a seleção de apps publicada.
2. Importar o ZIP provisório em Homeio/CasaOS de **teste**, nunca com dados
   de produção. Se a importação falhar, registar o erro e versão exata.
3. Para cada app testar: importação, configuração de volumes e permissões,
   segredos, arranque, UI, persistência após reinício e atualização com backup.
4. Documentar por sistema e arquitetura (AMD64/ARM64) antes de declarar
   compatibilidade.

## Execução local para desenvolvimento

```bash
python -m pip install -r requirements.txt
python -m unittest tests.test_export_universal -v
python scripts/export_universal.py --source release-source \
  --selection out/release-selection.json \
  --output dist/store/casaos-homeio-preview.zip
```

O comando **não** analisa CVEs: consome apenas evidência previamente gerada.
Uma aprovação estática não é prova de funcionamento real.

Referências: [formato CasaOS](https://github.com/IceWhaleTech/CasaOS-AppStore/blob/main/docs/specs/compose-and-x-casaos.md),
[compatibilidade declarada pelo Homeio](https://github.com/doctor-io/homeio),
[exemplo Umbrel](https://github.com/getumbrel/umbrel-community-app-store).

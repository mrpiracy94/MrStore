# Organização e manutenção do catálogo MrStore

## Fontes de verdade e separação de responsabilidades

- `Apps/<slug>/docker-compose.yml`: única fonte para os 254 manifests de origem,
  nomes, `x-casaos.category`, arquitetura declarada, id estável e versão.
- `category-list.json`: categorias expostas ao builder; deve refletir
  rigorosamente os nomes e contagens reais dos manifests.
- `recommend-list.json` e, quando existir, `featured-apps.json`: seleções
  editoriais; **não constituem** autorizações de publicação.
- `scripts/catalog.py`: leitura como dados inertes e regras básicas; não arranca
  Docker.
- `scripts/catalog_index.py`: inventário agrupado, pesquisa e deteção de
  categorias em falta, contagens obsoletas e recomendações inválidas.
- `scripts/release_catalog.py`: único seletor da edição distribuída; aplica
  os scans CVE completos, digest imutável, plataformas e quarentena.
- `scripts/compatibility.py`: análise estática do lançador ZimaOS, nunca
  prova C2/C3/C4.

**Regra:** o inventário dos 254 manifests nunca deve ser confundido com a
edição pública aprovada. Uma aplicação retirada por quarentena continua visível
na origem, mas não fica recomendada na edição publicada.

## Gerar um índice navegável

```bash
python -m pip install -r requirements.txt
python scripts/catalog_index.py
python scripts/catalog_index.py --category Media --architecture amd64
python scripts/catalog_index.py --search "música"
```

Os resultados ficam em `out/catalog-index.json` e
`out/catalog-index.md` (não são versionados). O GitHub Actions disponibiliza
os dois no artifact `mrstore-catalog-navigation`.

O índice evita exportar variáveis de ambiente, volumes Docker ou passwords.
Indica categoria, título, arquitetura declarada e estatuto **estático**.
Não testa CVEs, não instala aplicações e não altera dados persistentes.

## Taxonomia e divergências existentes

A distribuição deve ser medida nos **manifests**, nunca inferida apenas de
`category-list.json`. O comando avisa quando há categorias não utilizadas,
categorias de manifests não listadas e contagens desatualizadas. Esses avisos
são visíveis durante a migração da taxonomia na PR #85; não devem ser
mascarados com contagens fictícias. Após a taxonomia estar sincronizada,
ativar `python scripts/catalog_index.py --strict-taxonomy` na CI.

Nomes e IDs das aplicações são contratos estáveis: uma simples mudança de
categoria não justifica migrar volumes, mudar nomes de containers, versões,
digests ou portas.

## Acrescentar ou reorganizar uma aplicação

1. Criar ou alterar **apenas** o manifest respetivo; conservar
   `x-casaos.id`, dados persistentes e nomes dos serviços quando existentes.
2. Confirmar que `x-casaos.category` pertence ao catálogo oficial em
   `category-list.json`; recalcular contagens a partir dos manifests.
3. Definir título, resumo, descrições PT-PT/EN quando possível, arquiteturas
   realmente suportadas, icon, `port_map` e índice correto.
4. Incluir entradas em recomendações/destaques só quando o slug existe e há
   revisão editorial. A quarentena da publicação continua obrigatória.
5. Executar `python scripts/validate.py`,
   `python scripts/catalog_index.py`,
   `python scripts/compatibility.py` e
   `python -m unittest discover -s tests -v`.
6. Para mudanças de imagem, exigir scan Trivy HIGH/CRITICAL em todas as
   arquiteturas declaradas, digest imutável e testes de migração quando
   existem dados persistentes.

A publicação v2 e o funcionamento num ZimaOS real são assuntos separados.

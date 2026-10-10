# Contribuir para a MrStore

A MrStore é um catálogo comunitário ZimaOS v2. Aceitam-se correções de
metadados, aplicações novas, testes e remediações **com prova verificável**.

Leia [a organização do catálogo](docs/CATALOG_ORGANIZATION.md) e a
[política de publicação](docs/SAFE_RELEASE_POLICY.md) antes de alterar
um manifesto. Para cada PR:

- Conserve o identificador `x-casaos.id`, volumes persistentes e nomes de
  containers de instalações existentes; explique qualquer migração inevitável.
- Coloque a aplicação na categoria que existe no `category-list.json`.
  Não duplique categorias nem escreva contagens arbitrárias.
- Inclua arquitetura suportada, portas, UI real, ícones e metadados em português.
- Não adicione passwords reais, `CHANGE_ME` como credencial operacional,
  acessos privilegiados ou montagens de `docker.sock` sem análise específica.
- Documente testes e limitações. CI estática não demonstra que corre num NAS.
- Não declare uma imagem livre de CVEs sem Trivy completo AMD64/ARM64,
  digest fixado e evidência; as apps inseguras permanecem em quarentena.

Testes locais:

```bash
python -m pip install -r requirements.txt
python scripts/validate.py
python scripts/catalog_index.py
python scripts/compatibility.py
python -m unittest discover -s tests -v
```

A `main` mantém todas as definições para manutenção. Apenas o seletor de
publicação seguro pode determinar que imagens entram na edição `gh-pages`.

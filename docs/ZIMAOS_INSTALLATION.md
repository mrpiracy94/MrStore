# Integração de loja externa — ZimaOS App Store v2

A MrStore tem uma **identidade universal** para o ecossistema homelab.
Este guia documenta **apenas o formato de integração atualmente existente**,
não uma certificação universal nem a garantia de funcionamento de cada aplicação.

## Adicionar a loja

1. No ZimaOS, abre a App Store e procura a opção **adicionar loja externa** compatível com o protocolo v2.
2. Adiciona o URL base:

   ```text
   https://mrpiracy94.github.io/MrStore
   ```

3. Antes de instalar, confirma arquitetura, permissões, serviços auxiliares, portas,
   volumes e credenciais exigidas pela aplicação.

Os ficheiros do protocolo encontram-se em
[store.json](https://mrpiracy94.github.io/MrStore/store.json)
e [index.json](https://mrpiracy94.github.io/MrStore/index.json).

**A montra web é informativa:** não instala nem atualiza contentores por si só.
A existência de um catálogo no formato v2 não garante instalação funcional
em todas as versões e configurações de hardware.

## Testes reais e cobertura

Os testes estáticos do GitHub Actions são diferentes dos ensaios efetuados num NAS.
O relatório de cobertura por aplicação e por arquitetura AMD64/ARM64 pode ser gerado com:

```bash
python scripts/zimaos_coverage.py
```

O registo de evidências está em
[data/zimaos-device-tests.json](../data/zimaos-device-tests.json).
**Ausência de registo não comprova incompatibilidade nem certifica funcionamento.**

Consulta [Compatibilidade ZimaOS e evidências reais](ZIMAOS_COMPATIBILITY.md)
para as instruções de teste, checklist C2–C4 e submissão de resultados.

## Outras plataformas

UmbrelOS, Homeio, CasaOS, Cosmos, Portainer, HomeDock OS, Olares, Dockge,
Runtipi e Docker/Linux integram o plano de evolução. Não é seguro anunciar
o URL deste guia como instalador nativo para esses sistemas sem adaptadores,
testes de instalação e validação de atualizações.

[Voltar à apresentação universal da MrStore](../README.md)

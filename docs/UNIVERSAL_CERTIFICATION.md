# MrStore Verified — execução e provas de compatibilidade (11 plataformas)

**Objetivo:** validar instalação, função principal, persistência, upgrade, backup e
rollback de *cada aplicação* no sistema e arquitetura declarados. O selo
**MrStore Verified** é uma avaliação comunitária do projeto, **não**
uma certificação emitida por ZimaOS, CasaOS, UmbrelOS ou outros fabricantes.

A auditoria CVE, o `docker compose config`, os formatos OAC/HDS e os testes
com fixtures sintéticas nunca equivalem a um teste de instalação real.

## Situação verificável

O ficheiro `data/universal-device-tests.json` começa com `tests: []`.
O workflow `Validate MrStore` apresenta o inventário por plataforma e níveis
C2/C3/C4, e arquiva `universal-device-coverage`. O release publicado poderá
incluir `/universal/device-evidence.json`, caso exista um catálogo aprovado.
Os contadores são sempre zero sem registos atuais e revistos.

## Regras de prova

| Nível | Testes numa instalação real |
| --- | --- |
| C2 | Importação **nativa** da loja ou pacote e instalação no SO exato |
| C3 | C2, função principal testada e dados persistentes após reinício |
| C4 | C3, upgrade, backup/restauro, rollback e revisão de segurança |

Para adicionar uma observação devem existir:
- App/slug e arquitetura AMD64/ARM64 declarada no manifesto.
- Nome/versão exata do SO de destino.
- Data real de ensaio e SHA-256 atual de `Apps/<slug>/docker-compose.yml`.
- Um issue/PR público da MrStore com resumo **anonimizado** de instalação,
  função verificada, backup, atualização e possíveis regressões.
- Revisão manual por **duas pessoas diferentes** indicada em `reviewed_by`.
- Todos os oito campos de `checks` definidos com booleanos (não usar strings).
- Nenhuma password, token, endereço IP privado, conteúdo de Docker inspect,
  backups, dados pessoais ou credenciais anexados ao issue.

A entrada só é contada quando a versão do manifesto **não mudou**;
observações obsoletas ficam em `stale_records`. O reporte não valida
automaticamente a identidade dos revisores nem a exatidão da evidência
remota. A revisão humana da PR com as provas é indispensável.

## Processo de ensaio por plataforma

1. Criar uma VM ou servidor **de ensaio** isolado com o SO e versão indicados.
   Para os onze sistemas é preciso acesso efetivo a cada plataforma, incluindo
   máquinas ARM64 onde as aplicações anunciem ARM64.
2. Importar a MrStore usando o mecanismo específico: ZimaOS v2; fonte CasaOS
   em CasaOS/Homeio; repositórios Git dedicados em Umbrel/Runtipi; OAC/Helm
   em Olares; HDS/HDStore em HomeDock; Stack/Compose em Cosmos, Portainer,
   Dockge ou Docker/Linux. Uma instalação manual com Compose não demonstra
   importação *nativa* noutro SO.
3. Instalar uma aplicação com imagem aprovada pelo scanner. Configurar caminhos
   de volumes e segredos para dados fictícios. Não usar o NAS de produção.
4. Testar o serviço principal e todos os serviços dependentes; fazer uma operação
   representativa (não basta HTTP 200).
5. Reiniciar a aplicação e o host de teste e confirmar dados persistentes.
6. Gerar backup, efetuar upgrade e comprovar os dados e a função principal.
   Reverter/restaurar e verificar que os dados continuam íntegros.
7. Publicar os resultados anonimizados num issue/PR e pedir revisão por duas
   pessoas. Após aprovação de ambas, registar em
   `data/universal-device-tests.json`, nunca diretamente na branch publicada.
8. Executar `python scripts/universal_device_coverage.py` e os testes:
   `python -m unittest tests.test_universal_device_coverage -v`.
   Confirmar C4 por app/arquitetura e verificar que não existe
   `stale_records`.

## O que ainda falta para atingir 100%

Não existe atualmente infraestrutura ligada a este workflow que instale, use,
faça backup e atualize automaticamente aplicações nos onze sistemas.
É necessário provisionar as plataformas de teste (preferencialmente VMs/sistemas
isolados AMD64 e ARM64) e ligar runners ou processos de recolha comprováveis.

**A elegibilidade por formato não significa certificado.** A matriz pública
só deverá exibir **C4 revisto** para a combinação exacta de
aplicação × plataforma × arquitetura que tenha passado o protocolo.
Alterações de imagem/digest, manifest, sistema ou runtime exigem revalidação
também — o hash do manifesto não é prova suficiente de digest da imagem
instalada.

## Exemplo esquemático de registo (NÃO copiar sem teste real)

```json
{
  "app": "nome-da-app",
  "platform": "docker-linux",
  "platform_version": "versao-exata",
  "architecture": "amd64",
  "tested_at": "AAAA-MM-DD",
  "compose_sha256": "sha256-hex-de-64-caracteres-sem-prefixo",
  "evidence_url": "https://github.com/mrpiracy94/MrStore/issues/NUMERO",
  "reviewed_by": ["revisor-1", "revisor-2"],
  "checks": {
    "native_import": false,
    "installed_on_target": false,
    "core_function": false,
    "restart_persistence": false,
    "upgrade": false,
    "backup_restore": false,
    "rollback": false,
    "security_review": false
  }
}
```

Os exemplos são deliberadamente inválidos para certificação até serem
preenchidos a partir de instalações reais.


## Piloto de runtime Docker/Linux em GitHub-hosted Ubuntu

O job docker_live_pilot usa o mesmo release aprovado pela auditoria de oito
shards, importando a imagem imutável da IT-Tools e executando-a num contentor
verdadeiro no Ubuntu descartável do GitHub Actions. A porta HTTP é local
127.0.0.1, não são montados volumes nem passados segredos. Faz um pedido à
aplicação, reinicia o contentor e repete o pedido. Em seguida remove os
contentores, redes e volumes transitórios.

O artifact mrstore-docker-live-pilot contém prova de arranque, digest, SHA
do manifesto, versões Docker/Compose e resposta HTTP. A app pode ficar em
quarentena pelo Trivy, caso em que o piloto regista que não foi executado.
Resultados positivos são apenas candidatos C2 a revisão; não constituem C3
(persistência/função completa), C4 (backup/upgrade/rollback), nem comprovam
outras plataformas como CasaOS, ZimaOS, Umbrel ou Olares. Não acrescentar
o registro à lista C4 sem ensaio e dupla revisão humana.

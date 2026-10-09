# MrStore — prova de compatibilidade real com ZimaOS

**Regra:** um build bem-sucedido, manifestos válidos ou uma página HTTP acessível NÃO comprovam que uma app funciona no ZimaOS. Rever as CVEs antes de instalar imagens num NAS.

## Níveis de evidência

| Nível | Prova necessária |
| --- | --- |
| C0 — publicado | Entrada no índice v2 e ficheiros presentes na branch gh-pages |
| C1 — estático | Main service, porta publicada, esquema, URL e configurações verificadas sem executar containers |
| C2 — runtime observado | Num NAS real: container instalado e a correr, porta publicada observada, resposta HTTP quando houver UI |
| C3 — funcional no ZimaOS | Instalação através da loja, configuração, função principal, persistência após reinício e evidência manual |
| C4 — atualização segura | Backup, upgrade, migração e recuperação de dados comprovados num ambiente de teste |

**Nenhuma aplicação é marcada como C2/C3/C4 automaticamente.** Testar uma arquitetura ou versão não prova as restantes.

## C1 — inventário estático

Executar a partir da raiz do repositório:

    python -m pip install -r requirements.txt
    python scripts/compatibility.py

O relatório de cada aplicação fica em out/compatibility.json e out/compatibility.md. O workflow Validate MrStore arquiva-os no artefacto zimaos-compatibility-static.

- static_consistent: launch plausível; **não** é prova de instalação.
- configuration_required: segredos CHANGE_ME, URLs ou outras configurações por preencher.
- static_review_required: porta de UI, network_mode, scheme ou path a rever.
- headless_not_runtime_tested: serviço sem interface web (porta zero).

O script nunca executa Docker nem consulta instalações ZimaOS reais.

## C2 — smoke test opt-in, só de leitura

1. Num ZimaOS de **teste** e após revisão de CVEs, instalar uma app através da MrStore. Rever permissões, volumes e credenciais.
2. Na máquina com Docker CLI ligado ao mesmo NAS, com uma cópia do repositório, Python e PyYAML, executar (substituir o endereço):

       python scripts/zimaos_runtime_probe.py --app actual-budget --host 192.168.1.10

3. O comando executa **somente docker inspect e um pedido HTTP**, sem instalar, executar, atualizar ou remover containers. O JSON devolvido nunca inclui hostname/IP, valores de variáveis de ambiente ou credenciais.
4. Um resultado smoke_pass true significa apenas container em execução, porta publicada observada e endpoint HTTP acessível. Resposta 401/403 pode provar presença de endpoint mas **não** login nem funcionalidade.
5. Para aplicações headless, a execução verifica o container; a função real deve ser testada separadamente.
6. Para HTTPS com certificado autoassinado (por exemplo Nextcloud), o pedido HTTP pode falhar a verificação do certificado. Confirmar o comportamento no browser local. A opção --skip-http permite inspecionar Docker sem efetuar HTTPS e **não conta como prova HTTP**.
7. Se o ZimaOS renomear o container ou o acesso Docker não estiver disponível, a falha deste script não prova incompatibilidade da aplicação.

**Não partilhar URLs privados, tokens, ficheiros de inspect completos, IPs internos ou capturas com dados pessoais nos issues públicos.**

## C3 — checklist de teste numa instalação real

- [ ] Versão exata do ZimaOS e arquitetura CPU anotadas.
- [ ] Imagem Docker (digest/tag) e commit do manifesto registados.
- [ ] Loja importada e app instalada pela interface do ZimaOS, sem alterações manuais.
- [ ] Serviço principal e dependências arrancam sem erros.
- [ ] O botão de abertura usa protocolo, porta e caminho corretos.
- [ ] Setup inicial e função principal testados; não basta abrir a página.
- [ ] Dados de teste sobrevivem a um reinício controlado.
- [ ] Limitações e credenciais obrigatórias documentadas sem revelar segredos.
- [ ] Resultado guardado num issue ou PR com prova anonimizada.

Criar backups antes de qualquer teste de upgrade. Não instalar imagens com riscos conhecidos inaceitáveis em produção.

## Piloto sugerido — AINDA NÃO TESTADO num NAS

| App | Verificação principal |
| --- | --- |
| Actual Budget | UI na porta 5006, criar orçamento fictício, reiniciar e confirmar dados |
| Uptime Kuma | UI 30004, configurar monitor de teste e verificar persistência |
| Nextcloud | HTTPS na porta 20019 e persistência de /config e /data |
| Vaultwarden | UI 30003, HTTPS e cofres de teste sem dados pessoais |
| Paperless-ngx | App + Redis, OCR e persistência de documentos de teste |
| Karakeep | URL externa/porta 30002, autenticação e ligação ao Meilisearch |
| Immich | Password DB consistente, Redis, fotos de teste e backups |

O bloqueio de CVEs deve ser respeitado antes de usar estas imagens de terceiros.

## Registo de evidência (sem dados sensíveis)

    App: actual-budget
    Data: AAAA-MM-DD
    ZimaOS: versão exata
    Arquitetura: amd64 / arm64
    Manifest SHA: commit exato
    Imagem: tag/digest
    C0: sim/não
    C1: sim/não e findings
    C2: sim/não e JSON anonimizado
    C3: sim/não + função testada e persistência
    C4: não testado / sim / falhou
    Resultado: confirmado / parcial / falhou

Mudanças de imagem, arquitetura, manifest ou ZimaOS pedem revalidação.

## Achados concretos desta ronda

- **Nextcloud:** a imagem LinuxServer.io expõe HTTPS na porta interna 443; a MrStore publica essa porta como 20019. Foi adicionada a configuração scheme: https, ainda a comprovar no NAS.
- **Karakeep:** NEXTAUTH_URL foi alinhada com a porta 30002, mas o hostname de exemplo zimaos.local tem de ser ajustado para o hostname ou domínio real do NAS.
- **Serviços sem UI:** port_map de zero é uma indicação headless, não um endpoint HTTP.

Fontes: https://github.com/IceWhaleTech/CasaOS-AppStore/blob/main/docs/specs/compose-and-x-casaos.md e https://docs.linuxserver.io/images/docker-nextcloud/

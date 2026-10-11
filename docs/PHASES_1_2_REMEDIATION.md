# MrStore — Remediação das Fases 1 e 2

A política cobre TODAS as 254 aplicações e imagens Docker, sem depender de
um NAS ou do ZimaOS v2. A integração GitHub desta fase protege o catálogo
publicado e os seus workflows; não modifica sistemas já instalados.

## Segurança efetivamente reforçada

1. Todas as GitHub Actions de terceiros foram fixadas em SHA de commit
   completo verificado. `scripts/verify_action_pins.py` impede novos usos
   de tags móveis nos workflows (incluindo jobs que compilam e publicam
   imagens com credenciais de GitHub Container Registry).
2. A montra web passa a carregar `security-inventory.json`, verificar a
   correspondência exata das 254 aplicações e apresentar avisos individuais.
   O link de download direto de Compose é ocultado quando existem
   `credential_placeholder`, `weak_example_secret` ou faltam evidências.
   A ligação ao repositório continua visível para revisão humana.
3. `scripts/secure_install_compose.py` permite gerar um ficheiro Compose
   único por instalação Docker, com segredos criptograficamente aleatórios.
   O ficheiro é criado fora do repositório, sem sobreposição e com permissões
   0600. Os valores NÃO entram no GitHub, na CI nem nos relatórios.
   Os segredos partilhados em várias entidades são mantidos consistentes:
   Immich DB_PASSWORD/POSTGRES_PASSWORD e Karakeep MEILI_MASTER_KEY.
4. Para Cloudflared, Frigate e aplicações com bases de dados externas, tokens,
   passwords e endereços externos têm de ser fornecidos pelo utilizador
   através de um terminal de confiança; não são inventados por script.
5. O inventário já distingue portas de serviço dos painéis de administração:
   tráfego do proxy em 80/443 e peers BitTorrent em 6881 não são falsamente
   classificados como interfaces administrativas.

## Exemplo: Docker genérico (não um instalador Windows)

```sh
python scripts/secure_install_compose.py --app immich --output /caminho-privado/immich.yml
docker compose -f /caminho-privado/immich.yml config
```

Usar apenas um diretório privado, com backup e permissões do utilizador.
O comando apenas escreve o ficheiro; NÃO inicia contentores, instala apps,
atualiza versões, altera volumes ou migra bases de dados. NUNCA enviar o
Compose gerado com passwords para Issues/PRs, nem guardar no Git.

Para apps com serviços externos (ex.: BookStack, NetBox, HedgeDoc,
Cloudflared) o comando pede os valores necessários interativamente.
URLs como NEXTAUTH_URL, domínio, firewall, redes e credenciais de contas
externas ainda devem ser revistos antes da instalação.

## Limitações e riscos que exigem migração/testes reais

- O instalador nativo ZimaOS não dispõe de integração verificada com este
  gerador. A montra web BLOQUEIA downloads inseguros, mas a importação
  direta de um manifesto a partir de GitHub continua possível e exige
  revisão humana. Não confundir a listagem editorial com instalação segura.
- Kasm continua a depender de `privileged: true`. Dockge precisa de
  acesso de escrita à API Docker. Isolamento do host, autenticação e
  rede administrativa dependem da infraestrutura real.
- A exposição de portas na LAN não implica exposição WAN. Não trocar todas
  por localhost sem conhecimento das necessidades das aplicações e da rede.
- 91 aplicações usam seccomp permissivo; a sua remoção em massa sem testes
  de runtime poderia quebrar aplicações GUI. Permanecem sinalizadas.
- As referências de imagem dos manifests originais podem continuar móveis;
  a publicação aplica uma etapa separada de fixação por digest. Um digest
  não comprova ausência de CVEs, e erros Trivy continuam pendentes.
- A auditoria dos Dockerfiles próprios não elimina CVEs nos respectivos
  artefactos finais.

## Testes e reversão

```sh
python scripts/verify_action_pins.py
python -m unittest discover -s tests -v
python scripts/security_inventory.py --base-sha HEAD^ --fail-new-high
```

A CI também verifica a sintaxe do JS da montra via `node --check`.
No caso de falha funcional, reverter o PR por GitHub após análise, validar
o build e a publicação. Nunca usar `docker compose down -v` para reverter.

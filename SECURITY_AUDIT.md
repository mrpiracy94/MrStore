# MrStore — Auditoria preliminar de segurança

**Data:** 09/10/2026  
**Âmbito:** análise offline dos manifestos Docker Compose fornecidos, não de containers em execução.  
**Método:** parsing YAML e regras estáticas em `scripts/audit_store.py`; **não foram consultados feeds de CVE nesta fase**.

| Indicador | Resultado |
|---|---:|
| Aplicações / serviços | 254 / 260 |
| Imagens distintas | 258 |
| Erros de esquema após migração v2 | **0** |
| Avisos estáticos (ocorrências, não apps distintas) | **406** |
| Referências a tags não imutáveis | 250 serviços |
| `seccomp:unconfined` | 93 serviços |
| `privileged: true` | 2 apps |
| Montagem do socket Docker | 7 apps |
| Capacidades adicionadas (`cap_add`) | 5 apps |
| Redes host | 2 apps |
| Segredos por preencher (`CHANGE_ME`) | 26 ocorrências |
| Apps sem UI web mapeada | 19 apps |
| Colisões de portas entre apps | 2 portas |

## Prioridades de revisão

1. **Acesso administrativo ao host:** `frigate` e `kasm` incluem `privileged: true`. Confirmar necessidade, isolar rede e dados e reduzir privilégios quando o projeto o permitir.
2. **Acesso ao Docker daemon:** `dockge`, `dozzle`, `glances`, `homarr`, `homepage`, `netdata` e `socket-proxy` montam `/var/run/docker.sock`. Qualquer processo com acesso suficientemente permissivo ao socket pode controlar o host Docker. Confirmar se montagens são só de leitura, usar proxies com permissões mínimas e evitar exposição pública sem autenticação.
3. **Isolamento de processos:** 93 serviços utilizam `seccomp:unconfined`. Este sinal é frequente em apps desktop remotas mas diminui as restrições impostas ao container; rever caso a caso.
4. **Segredos:** 26 valores de ambiente usam `CHANGE_ME`. Não instalar sem definir segredos únicos e fortes; nunca colocá-los no repositório público.
5. **Portas conflituosas:** host `21027` usado por `brave` e `syncthing`, host `30000` por `gitea` e `luanti`. Se instalados simultaneamente, alterar as portas publicadas.
6. **Atualizações silenciosas:** tags mutáveis, sobretudo `latest`, podem passar a apontar para outra imagem. Digest monitor deteta alterações na origem; não garante que a versão instalada no ZimaOS tenha sido atualizada.
7. **19 apps sem UI web:** foram preenchidos os metadados obrigatórios `port_map: "0"` e `index: /`, mas não foi criada UI inexistente. A publicação v2 e o comportamento do cliente precisam de verificação num ZimaOS real.

## Alcance dos resultados CVE

Trivy, executado pelo workflow `cve-scan.yml`, usa uma base de vulnerabilidades e analisa imagens Docker por lotes. O scanner poderá identificar CVEs HIGH/CRITICAL em pacotes presentes nas imagens, mas **não existe uma contagem de CVE verificada nesta análise inicial**. A visão completa do catálogo depende do ciclo de 8 dias, da disponibilidade das imagens e de scans sem erros. Resultados ficam nos artifacts da execução correspondente; falhas aparecem explicitamente.

**Importante:** os avisos são *pistas de revisão*, não 406 vulnerabilidades. O scanner não avalia configuração em produção, a exposição real da rede, credenciais ou uma instalação ZimaOS específica. Fazer backup dos dados antes de atualizar ou instalar.
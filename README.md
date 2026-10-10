<div align="center">
  <img src="web/assets/mrstore-hero.webp" alt="MrStore — O teu homelab. As tuas apps. Uma só loja. Um ecossistema, múltiplas plataformas." width="100%">

  <h1>MrStore · The Homelab App Hub</h1>

  <p><strong>O teu homelab. As tuas apps. Uma só loja.</strong><br>Descobre aplicações self-hosted num catálogo comunitário pensado para unir sistemas, servidores e plataformas. Uma identidade independente do teu sistema operativo.</p>

  <p>
    <a href="https://mrpiracy94.github.io/"><strong>🌐 Explorar a loja</strong></a>
    &nbsp; · &nbsp;
    <a href="#-plataformas-e-compatibilidade"><strong>🌍 Plataformas</strong></a>
    &nbsp; · &nbsp;
    <a href="#-segurança-e-transparência"><strong>🛡️ Segurança</strong></a>
    &nbsp; · &nbsp;
    <a href="https://github.com/mrpiracy94/MrStore/issues"><strong>💬 Issues e sugestões</strong></a>
  </p>
</div>

---

## ✨ O que é a MrStore?

A **MrStore** reúne aplicações **self-hosted** para servidores, NAS e projetos homelab, independentemente da marca ou sistema utilizado. **Todas as 254 aplicações atuais** são apresentadas na montra pública e na loja técnica ZimaOS v2, a partir do mesmo inventário `Apps/`. A presença no catálogo é editorial: não prova ausência de CVEs nem compatibilidade de instalação.

**A montra web é universal para descoberta, não para instalação automática.** A instalação nativa depende do adaptador e da validação de cada plataforma.

| 🔍 Exploração fácil | 📦 Aplicações self-hosted | 🛡️ Segurança por aplicação |
|:---|:---|:---|
| Pesquisa por nome, categoria, arquitetura e favoritos na montra web. | Inventário completo das apps em `Apps/`, com IDs estáveis. | Auditorias CVE e de configurações separadas da listagem editorial. |

**[Abrir a montra da MrStore →](https://mrpiracy94.github.io/)**

> **Nota:** a montra em GitHub Pages permite descobrir aplicações e consultar o catálogo real, mas não instala contentores. Só considera uma edição validada quando os relatórios da publicação correspondem ao índice apresentado.

## 🌍 Plataformas e compatibilidade

A visão da MrStore abrange **UmbrelOS, Homeio, CasaOS, ZimaOS, Cosmos, Portainer, HomeDock OS, Olares, Dockge, Runtipi e Docker/Linux**.

**A descoberta de aplicações e a instalação nativa são coisas diferentes.**

| Capacidade | Estado atual | Limites |
|:---|:---|:---|
| **Montra web** | Disponível | Pesquisa e filtros acessíveis num navegador, independentemente do sistema. |
| **Definições Docker Compose** | Disponíveis no repositório | Cada manifesto tem requisitos e dependências próprios. |
| **Integração de loja externa** | Formato ZimaOS App Store v2 | O formato está implementado; o funcionamento exige validação por versão, equipamento e aplicação. |
| **Integração nativa nas restantes plataformas** | Em desenvolvimento | Não assumir suporte sem adaptador e testes reais. |

A identidade *multiplataforma* traduz a visão do projeto, **não uma certificação de funcionamento em todos os sistemas**. O URL público não é um instalador universal.

📖 [Guia técnico de instalação da integração disponível](docs/ZIMAOS_INSTALLATION.md) · [Relatórios e ensaios em equipamento](docs/ZIMAOS_COMPATIBILITY.md)

## ⭐ Catálogo completo — 254 aplicações

A MrStore apresenta **todas as aplicações com manifestos em `Apps/`**, incluindo Home Assistant, Jellyfin, Immich, Nextcloud, qBittorrent e Vaultwarden. As futuras adições entram automaticamente na publicação editorial quando os respectivos manifestos e metadados forem válidos.

- **Loja técnica ZimaOS v2:** https://mrpiracy94.github.io/MrStore/
- **Homepage e pesquisa:** https://mrpiracy94.github.io/
- **Website separado:** https://mrpiracy94.github.io/MrStore-Web/ (requer ativação GitHub Pages neste repositório)

A listagem não filtra apps com avisos CVE. O ficheiro `release-status.json` apresenta `certification: not_assessed` nas edições editoriais; as auditorias continuam independentes da descoberta.

## 🧭 Descobrir aplicações

A montra web foi concebida para facilitar o uso:

- **Pesquisar** por nome, descrição e categoria.
- **Filtrar** por categoria e arquitetura AMD64/ARM64.
- **Guardar favoritos** localmente no navegador, sem criar conta.
- **Consultar fichas** com a versão do pacote, serviço e link para o manifesto Docker.
- **Distinguir publicação verificada de edições antigas**, com alertas caso o relatório de seleção segura esteja ausente.

Para consultar os manifestos e configurações de todas as aplicações, abre a pasta [Apps/](Apps/).

## 🛡️ Segurança e transparência

A **publicação editorial** inclui todas as aplicações, independentemente do resultado CVE. Uma edição editorial não é uma certificação de instalação ou segurança.

As **auditorias técnicas opcionais para releases verificados** continuam a analisar imagens Docker, arquitetura, digests e configurações. Os seus relatórios identificam riscos, sem apagar apps da montra. Uma edição técnica filtrada não pode substituir o catálogo completo por uma seleção menor.

**Não afirmamos ausência de CVEs.** Antes de instalar, confirma os requisitos, credenciais, permissões e dependências da aplicação.

📖 [Política de publicação segura](docs/SAFE_RELEASE_POLICY.md) · [Validação técnica](docs/ZIMAOS_COMPATIBILITY.md) · [Avisos de segurança](SECURITY.md)

## ⚙️ Tecnologias e automação

| Componente | Finalidade |
|:---|:---|
| **Builder de catálogo v2** | Exportação para o protocolo atualmente integrado. |
| **Docker Compose** | Definir as aplicações, serviços, volumes e portas. |
| **Python + PyYAML** | Validar metadados, arquiteturas, segurança e catálogos. |
| **Trivy + crane** | Auditar vulnerabilidades e consultar digests das imagens. |
| **GitHub Actions** | Verificações, testes de regressão, monitorização e publicação. |
| **HTML + CSS + JavaScript** | Montra leve e responsiva no GitHub Pages, sem dependências CDN. |

## 🗂️ Estrutura do projeto

```text
MrStore/
├── Apps/                 # Manifests de todas as apps listadas na MrStore
├── web/                  # Montra e recursos visuais GitHub Pages
│   ├── index.html
│   └── assets/
├── scripts/              # Validação, auditoria CVE, publicação e monitorização
├── security/images/      # Imagens de segurança corrigidas quando justificadas
├── tests/                # Testes offline e regressões
├── docs/                 # Guias, política de segurança e migrações
├── .github/workflows/    # Validação CI, publicação e verificações programadas
├── category-list.json
├── recommend-list.json
└── store-config.json
```

## 🧪 Desenvolvimento e testes

```bash
python -m pip install -r requirements.txt
python scripts/validate.py
python -m unittest discover -s tests -v
python scripts/compatibility.py
```

A homepage pública é mantida em [`mrpiracy94.github.io`](https://github.com/mrpiracy94/mrpiracy94.github.io) e sincroniza automaticamente **todos os manifests** da MrStore. O catálogo técnico em `gh-pages` é publicado separadamente com o inventário completo e a indicação `not_assessed` nas edições editoriais; não altera os Compose instalados nos servidores.

📖 [Como funciona a montra](docs/STORE_FRONTEND.md) · [GitHub Actions](https://github.com/mrpiracy94/MrStore/actions) · [Guia de integração](docs/ZIMAOS_INSTALLATION.md)

---

<div align="center">
  <strong>MrStore</strong> · Feita para a comunidade, com paixão por self-hosting. 🧡<br>
  <sub>Projeto comunitário independente, sem afiliação aos fabricantes das plataformas ou aos autores das aplicações.</sub>
</div>

"use strict";
(function () {
  const STORE_URL = "https://mrpiracy94.github.io/MrStore";
  const PREFIX = "io.github.mrpiracy94.";
  const BATCH_SIZE = 12;
  const CATEGORY_LABELS = {
    Media: "Multimédia", Productivity: "Produtividade", Home: "Casa",
    Networking: "Redes", Network: "Redes", Cloud: "Cloud",
    Browser: "Navegadores", Downloader: "Downloads", Games: "Jogos",
    Graphics: "Gráficos", Developer: "Desenvolvimento", AI: "Inteligência artificial",
    Finance: "Finanças", Social: "Social", Utilities: "Utilitários",
    Others: "Outras"
  };
  const CATEGORY_SYMBOLS = { "": "▦", Media: "▣", Productivity: "◈", Home: "⌂", Networking: "⛨", Network: "⛨", Cloud: "☁", Browser: "◉", Downloader: "↓", Games: "✦", Graphics: "▧", Developer: "</>", AI: "✺", Finance: "▤", Social: "◎", Utilities: "⚙", Others: "◇" };
  const $ = (id) => document.getElementById(id);
  const state = { apps: [], filtered: [], category: "", query: "", arch: "",
    favoritesOnly: false, limit: BATCH_SIZE, saved: new Set(), validated: false };
  const base = new URL("./", window.location.href);
  // One audited manifest source, separate user instructions per target platform.
  // A portable Compose file is NOT proof of native store integration.
  const PLATFORM_GUIDES = {
    zimaos: ["ZimaOS", "Loja externa ZimaOS v2", ["Abre a App Store do ZimaOS.", "Adiciona a URL base da MrStore como loja externa v2.", "Confirma arquitetura, permissões e backup antes de instalar."]],
    homeio: ["Homeio", "Fonte ZIP CasaOS em pré-visualização", ["Abre as fontes da App Store no Homeio.", "Adiciona a URL do ZIP experimental aprovado.", "Testa em ambiente de ensaio: instalação, portas e persistência."]],
    casaos: ["CasaOS", "Formato CasaOS em pré-visualização", ["Verifica se a tua versão aceita a fonte ZIP.", "Experimenta a importação em ambiente de teste (não é ZIP legado v1 certificado).", "Revê volumes /DATA, segredos e portas antes de instalar."]],
    umbrelos: ["umbrelOS", "Loja nativa pendente", ["A Community App Store do umbrelOS requer um repositório Git próprio.", "O exportador de manifestos Umbrel ainda não foi validado.", "Não adiciones o URL da MrStore ZimaOS como se fosse uma loja Umbrel."]],
    cosmos: ["Cosmos", "Importação Docker Compose", ["Escolhe uma aplicação e descarrega o Compose aprovado.", "Em ServApps, seleciona Import Docker Compose.", "Verifica a conversão, redes, volumes e exposição de portas antes de criar."]],
    portainer: ["Portainer", "Stacks a partir de Compose", ["Escolhe uma aplicação e descarrega o Compose aprovado.", "Vai a Stacks → Add stack → Web editor ou Upload.", "Corrige os caminhos dos volumes, valida variáveis e faz Deploy."]],
    homedock: ["HomeDock OS", "Pacotes HDS e loja HDStore (pré-visualização)", ["Abre o Packager do HomeDock OS e seleciona importar .hdstore.", "Se o pacote aprovado estiver publicado, copia a ligação e importa o bundle.", "Verifica dados, configurações e atualização numa instância de testes antes de usar em produção."]],
    olares: ["Olares", "Olares Application Charts (pré-visualização)", ["Abre a ficha de uma aplicação elegível e descarrega o OAC experimental.", "Valida o Helm chart e o OlaresManifest na versão instalada do Olares.", "Instala primeiro numa instância de teste. O pacote ainda não foi validado no Market oficial."]],
    dockge: ["Dockge", "Stacks Docker Compose", ["Escolhe uma aplicação e descarrega o Compose aprovado.", "Cria uma nova stack ou coloca o ficheiro na pasta de stacks.", "Revê caminhos de volumes/portas e inicia depois da validação."]],
    runtipi: ["Runtipi", "Loja Git Runtipi pendente", ["Runtipi v4+ aceita lojas externas como repositórios Git.", "Faltam config.json, x-runtipi, logo e testes por aplicação.", "O endereço ZimaOS/ZIP não substitui uma loja Runtipi."]],
    "docker-linux": ["Docker / Linux", "Docker Compose (CLI)", ["Escolhe uma aplicação e descarrega o Compose aprovado.", "Personaliza os volumes e as variáveis em ambiente seguro.", "Executa docker compose config e, depois de rever o resultado, docker compose up -d."]]
  };
  const COMPOSE_TARGETS = new Set(["cosmos", "portainer", "dockge", "docker-linux"]);
  let universalApps = new Map();
  let universalReady = false;
  let previewZipReady = false;
  let portainerTemplatesReady = false;
  let homedockPackages = new Set();
  let homedockReady = false;
  let olaresCharts = new Map();
  let olaresReady = false;
  let selectedStoreURL = STORE_URL;

  function renderPlatform() {
    const id = $("platform-select").value;
    const guide = PLATFORM_GUIDES[id] || PLATFORM_GUIDES.zimaos;
    const steps = $("platform-steps");
    steps.replaceChildren();
    guide[2].forEach(function (line, index) {
      const item = element("li");
      item.appendChild(element("span", "", String(index + 1).padStart(2, "0")));
      const inner = element("div");
      inner.appendChild(element("strong", "", ["Preparar", "Importar", "Validar"][index]));
      inner.appendChild(element("p", "", line));
      item.appendChild(inner); steps.appendChild(item);
    });
    selectedStoreURL = "";
    if (id === "zimaos") selectedStoreURL = STORE_URL;
    else if (id === "portainer" && portainerTemplatesReady) selectedStoreURL = STORE_URL + "/universal/portainer-templates.json";
    else if (id === "homedock" && homedockReady) selectedStoreURL = STORE_URL + "/homedock/mrstore.hdstore";
    else if ((id === "homeio" || id === "casaos") && previewZipReady) {
      selectedStoreURL = STORE_URL + "/store/casaos-homeio-preview.zip";
    }
    const intro = id === "homedock"
      ? (homedockReady ? "Bundle HDStore experimental disponível. Os pacotes ainda exigem validação no HomeDock OS real." : "O bundle HDStore ainda não está disponível nesta publicação.")
      : id === "olares"
      ? (olaresReady ? "Existem OACs experimentais para algumas apps. Descarrega o chart na ficha da app; ainda não são aplicações certificadas Olares." : "Os charts Olares ainda não estão disponíveis nesta publicação.")
      : COMPOSE_TARGETS.has(id)
      ? (universalReady
        ? (id === "portainer" && portainerTemplatesReady ? "O endereço contém apenas templates seguros de contentor único; para stacks com dependências usa o Compose aprovado na ficha da app." : "Seleciona uma aplicação e usa «Descarregar Compose aprovado» na respetiva ficha. Não é uma loja nativa integrada neste sistema.")
        : "O catálogo Compose aprovado ainda não está disponível nesta publicação.")
      : ((id === "casaos" || id === "homeio") && !previewZipReady
        ? "O ZIP experimental não está publicado nesta edição. Não uses o ZIP da branch main, que inclui apps em quarentena."
        : guide[1] + ". Suporte por formato não equivale a teste real de instalação.");
    $("platform-help").textContent = guide[0] + " · " + intro;
    $("store-address").textContent = selectedStoreURL ||
      (COMPOSE_TARGETS.has(id) ? "Escolhe uma app → Descarregar Compose aprovado" : "Integração nativa ainda indisponível");
    $("copy-store").disabled = !selectedStoreURL;
    $("copy-feedback").textContent = "";
  }

  async function checkUniversalPublication() {
    // Match the EXACT security-selected app set; do not advertise older partial artifacts.
    if (!state.validated) { renderPlatform(); return; }
    try {
      const response = await fetch("./universal/catalog.json", { cache: "no-store" });
      if (!response.ok) throw new Error("Universal catalog missing");
      const catalog = await response.json();
      const expected = new Set(state.apps.map(function (app) { return app.id; }));
      if (catalog.version !== 1 || catalog.approved_count !== expected.size ||
          !Array.isArray(catalog.apps) || catalog.apps.length !== expected.size) throw new Error("Mismatch");
      const verified = new Map();
      for (const item of catalog.apps) {
        if (!item || typeof item.slug !== "string" ||
            !/^[a-z0-9][a-z0-9._-]*$/.test(item.slug) ||
            item.id !== PREFIX + item.slug || !expected.has(item.id) ||
            item.compose !== "universal/compose/" + item.slug + ".yml" ||
            verified.has(item.slug)) throw new Error("Invalid app reference");
        verified.set(item.slug, item);
      }
      if (verified.size !== expected.size) throw new Error("Missing apps");
      universalApps = verified;
      universalReady = true;
      portainerTemplatesReady = Number.isInteger(catalog.portainer_template_count) && catalog.portainer_template_count > 0;
    } catch (_) { universalApps = new Map(); universalReady = false; portainerTemplatesReady = false; }
    renderPlatform();
  }

  async function checkPreviewZip() {
    if (!state.validated) return;
    try {
      const response = await fetch("./store/casaos-homeio-preview.zip", {
        method: "HEAD", cache: "no-store"
      });
      previewZipReady = response.ok;
    } catch (_) { previewZipReady = false; }
    renderPlatform();
  }
  async function checkNativePackages() {
    if (!state.validated) { renderPlatform(); return; }
    const expected = new Set(state.apps.map(function (app) {
      return app.id.slice(PREFIX.length);
    }));
    try {
      const response = await fetch("./homedock/catalog.json", {cache: "no-store"});
      if (!response.ok) throw new Error("HomeDock catalog missing");
      const info = await response.json();
      if (info.version !== 1 || info.source_approved !== expected.size ||
          !Array.isArray(info.packages) || info.packages.length !== info.exported_count ||
          info.packages.length < 1 || info.runtime_verified !== false ||
          info.bundle !== "homedock/mrstore.hdstore") throw new Error("Invalid HomeDock release");
      const names = new Set();
      for (const app of info.packages) {
        if (!app || typeof app.slug !== "string" || !expected.has(app.slug) ||
            app.url !== "homedock/" + app.slug + ".hds" || names.has(app.slug)) {
          throw new Error("HomeDock app set mismatch");
        }
        names.add(app.slug);
      }
      homedockPackages = names;
      homedockReady = true;
    } catch (_) { homedockPackages = new Set(); homedockReady = false; }

    try {
      const response = await fetch("./olares/catalog.json", {cache: "no-store"});
      if (!response.ok) throw new Error("Olares catalog missing");
      const info = await response.json();
      if (info.version !== 1 || info.source_approved !== expected.size ||
          !Array.isArray(info.packages) || info.packages.length !== info.chart_count ||
          info.chart_count < 1 || info.runtime_verified !== false) throw new Error("Invalid Olares release");
      const verified = new Map();
      for (const item of info.packages) {
        if (!item || typeof item.slug !== "string" || !expected.has(item.slug) ||
            typeof item.chart !== "string" || !/^mr[a-z0-9]{7,24}$/.test(item.chart) ||
            item.url !== "olares/" + item.chart + ".tgz" || verified.has(item.slug)) {
          throw new Error("Olares chart set mismatch");
        }
        verified.set(item.slug, item.chart);
      }
      olaresCharts = verified;
      olaresReady = true;
    } catch (_) { olaresCharts = new Map(); olaresReady = false; }
    renderPlatform();
  }
  function readFavorites() {
    try {
      const value = JSON.parse(localStorage.getItem("mrstore-favorites-v1") || "[]");
      if (Array.isArray(value)) {
        state.saved = new Set(value.filter(function (x) {
          return typeof x === "string" && x.startsWith(PREFIX) && x.length < 160;
        }).slice(0, 300));
      }
    } catch (_) { state.saved = new Set(); }
  }
  function saveFavorites() {
    try { localStorage.setItem("mrstore-favorites-v1", JSON.stringify(Array.from(state.saved))); }
    catch (_) { /* Private mode may reject storage. Favorites still work this session. */ }
  }
  function safePath(value, extension) {
    if (typeof value !== "string" || !value.startsWith("/apps/") ||
        value.includes("..") || value.includes("\\") || value.includes("?") ||
        value.includes("#") || !/^\/apps\/[a-z0-9._-]+\/[a-zA-Z0-9._/-]+$/.test(value)) return null;
    if (extension && !value.toLowerCase().endsWith(extension)) return null;
    const candidate = new URL("." + value, base);
    if (candidate.origin !== base.origin ||
        !candidate.pathname.startsWith(base.pathname + "apps/")) return null;
    return candidate.href;
  }
  function element(tag, className, textValue) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (textValue !== undefined) node.textContent = String(textValue);
    return node;
  }
  function appTitle(app) { return app.title && typeof app.title === "string" ? app.title : app.id.slice(PREFIX.length); }
  function categoryLabel(name) { return CATEGORY_LABELS[name] || name || "Outras"; }
  function setNotice(message, error) {
    const item = $("catalog-alert"); item.hidden = !message;
    item.textContent = message || ""; item.classList.toggle("is-error", Boolean(error));
  }
  function iconNode(app, className) {
    const wrap = element("div", className);
    const src = safePath(app.icon);
    if (src) {
      const img = document.createElement("img");
      img.src = src; img.alt = ""; img.loading = "lazy";
      img.addEventListener("error", function () { img.remove(); wrap.textContent = "✦"; }, { once: true });
      wrap.appendChild(img);
    } else wrap.textContent = "✦";
    return wrap;
  }
  function categoryList() {
    const counts = new Map();
    state.apps.forEach(function (app) { counts.set(app.category, (counts.get(app.category) || 0) + 1); });
    const list = $("categories"); list.replaceChildren();
    const all = [["", "Todas", state.apps.length]].concat(
      Array.from(counts).sort(function (a, b) {
        return categoryLabel(a[0]).localeCompare(categoryLabel(b[0]), "pt");
      }).map(function (entry) { return [entry[0], categoryLabel(entry[0]), entry[1]]; })
    );
    all.forEach(function (entry) {
      const button = element("button", "chip" + (state.category === entry[0] ? " active" : ""));
      button.type = "button"; button.dataset.category = entry[0];
      button.setAttribute("aria-pressed", String(state.category === entry[0]));
      button.appendChild(element("span", "chip-symbol", CATEGORY_SYMBOLS[entry[0]] || "◇"));
      button.appendChild(element("span", "chip-label", entry[1]));
      button.appendChild(element("span", "count", entry[2] + " aplicações"));
      button.addEventListener("click", function () {
        state.category = entry[0]; state.limit = BATCH_SIZE; categoryList(); render();
      });
      list.appendChild(button);
    });
    $("total-categories").textContent = String(counts.size);
  }
  function fold(value) {
    return String(value).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("pt");
  }
  function scoreSearch(app, query) {
    const title = fold(app.title || "");
    const slug = fold(app.id.slice(PREFIX.length));
    const label = fold(app.tagline || "");
    return title.includes(query) || slug.includes(query) ||
      label.includes(query) || fold(categoryLabel(app.category)).includes(query);
  }
  function makeCard(app) {
    const card = element("article", "app-card"), head = element("div", "app-card-head");
    // Screenshot from index.json, with a local icon fallback when unavailable.
    const cover = element("div", "app-card-cover");
    const screenshotURL = safePath(app.thumbnail);
    function coverFallback() {
      cover.classList.add("cover-placeholder");
      cover.replaceChildren(iconNode(app, "cover-placeholder-icon"));
    }
    if (screenshotURL && /\.(?:png|jpe?g|webp|avif)$/i.test(new URL(screenshotURL).pathname)) {
      const shot = document.createElement("img");
      shot.src = screenshotURL;
      shot.loading = "lazy"; shot.decoding = "async"; shot.alt = "";
      shot.addEventListener("error", coverFallback, { once: true });
      cover.appendChild(shot);
    } else coverFallback();
    card.appendChild(cover);
    head.appendChild(iconNode(app, "app-icon"));
    const copy = element("div", "app-header-copy");
    copy.appendChild(element("h3", "", appTitle(app)));
    copy.appendChild(element("span", "app-category", categoryLabel(app.category)));
    head.appendChild(copy);
    const favorite = element("button", "favorite-btn", state.saved.has(app.id) ? "★" : "☆");
    favorite.type = "button";
    favorite.setAttribute("aria-label", (state.saved.has(app.id) ? "Remover dos favoritos: " : "Adicionar aos favoritos: ") + appTitle(app));
    favorite.setAttribute("aria-pressed", String(state.saved.has(app.id)));
    favorite.addEventListener("click", function () {
      if (state.saved.has(app.id)) state.saved.delete(app.id);
      else state.saved.add(app.id);
      saveFavorites(); render();
    });
    head.appendChild(favorite); card.appendChild(head);
    card.appendChild(element("p", "app-desc", app.tagline || "Conhece esta aplicação no catálogo MrStore."));
    const footer = element("div", "app-footer"), arches = element("div", "architectures");
    (app.architectures || []).forEach(function (arch) {
      arches.appendChild(element("span", "architecture", arch.toUpperCase()));
    });
    footer.appendChild(arches);
    const details = element("button", "details-button", "Ver detalhes →");
    details.type = "button"; details.addEventListener("click", function () { openDetails(app); });
    footer.appendChild(details); card.appendChild(footer);
    return card;
  }
  function render() {
    const needle = fold(state.query.trim());
    state.filtered = state.apps.filter(function (app) {
      return (!state.category || app.category === state.category) &&
        (!state.arch || (app.architectures || []).includes(state.arch)) &&
        (!state.favoritesOnly || state.saved.has(app.id)) &&
        (!needle || scoreSearch(app, needle));
    });
    const grid = $("app-grid"), fragment = document.createDocumentFragment();
    state.filtered.slice(0, state.limit).forEach(function (app) { fragment.appendChild(makeCard(app)); });
    grid.replaceChildren(fragment);
    const shown = Math.min(state.limit, state.filtered.length);
    $("results-summary").textContent = state.filtered.length + " resultado(s)";
    $("catalog-state").hidden = state.filtered.length > 0;
    if (!state.filtered.length) {
      $("catalog-state").textContent = "Não encontrámos aplicações com estes filtros. Experimenta outra pesquisa ou categoria.";
    }
    const more = $("load-more"); more.hidden = shown >= state.filtered.length;
    if (!more.hidden) more.textContent = "Mostrar mais aplicações (" + (state.filtered.length - shown) + " restantes) ↓";
  }
  function openDetails(app) {
    $("details-icon").replaceChildren(iconNode(app, "detail-icon-inner"));
    $("details-title").textContent = appTitle(app);
    $("details-tagline").textContent = app.tagline || "Aplicação self-hosted";
    $("details-category").textContent = categoryLabel(app.category);
    $("details-arches").textContent = (app.architectures || []).map(function (x) { return x.toUpperCase(); }).join(" / ") || "Não indicado";
    $("details-version").textContent = app.version || "Não indicada";
    $("details-developer").textContent = app.developer || "Não indicado";
    // Preview a real screenshot from the verified local catalog, never a remote URL.
    const preview = $("details-preview");
    preview.replaceChildren();
    preview.hidden = true;
    const thumbnail = safePath(app.thumbnail);
    if (thumbnail && /\.(?:png|jpe?g|webp|avif)$/i.test(new URL(thumbnail).pathname)) {
      const screenshot = document.createElement("img");
      screenshot.alt = "Pré-visualização de " + appTitle(app);
      screenshot.loading = "eager"; // Hidden preview containers cannot trigger lazy loads reliably.
      screenshot.decoding = "async";
      screenshot.addEventListener("load", function () { preview.hidden = false; }, { once: true });
      screenshot.addEventListener("error", function () { preview.hidden = true; screenshot.remove(); }, { once: true });
      screenshot.src = thumbnail;
      preview.appendChild(screenshot);
    }
    const compose = $("details-compose"), url = safePath(app.compose_url, ".yml");
    compose.hidden = !url; if (url) compose.href = url;
    const slug = app.id.slice(PREFIX.length);
    const portable = $("details-universal");
    const selected = $("platform-select").value;
    let downloadable = "";
    let title = "Descarregar Compose aprovado ↓";
    if (state.validated && selected === "homedock" && homedockPackages.has(slug)) {
      downloadable = "./homedock/" + encodeURIComponent(slug) + ".hds";
      title = "Descarregar pacote HDS experimental ↓";
    } else if (state.validated && selected === "olares" && olaresCharts.has(slug)) {
      downloadable = "./olares/" + olaresCharts.get(slug) + ".tgz";
      title = "Descarregar OAC experimental ↓";
    } else if (state.validated && selected !== "olares" &&
               selected !== "homedock" && universalApps.has(slug)) {
      downloadable = "./universal/compose/" + encodeURIComponent(slug) + ".yml";
    }
    portable.hidden = !downloadable;
    portable.textContent = title;
    if (downloadable) portable.href = new URL(downloadable, base).href;
    $("details-github").href = "https://github.com/mrpiracy94/MrStore/tree/main/Apps/" + encodeURIComponent(slug);
    $("details").showModal();
  }
  function validateIndex(data) {
    if (!data || data.version !== 2 || !Array.isArray(data.apps) ||
        !Number.isInteger(data.app_count) || data.app_count !== data.apps.length) {
      throw new Error("Índice v2 incompleto ou inválido.");
    }
    const seen = new Set();
    for (const app of data.apps) {
      if (!app || typeof app.id !== "string" ||
          !/^io\.github\.mrpiracy94\.[a-z0-9._-]+$/.test(app.id) ||
          seen.has(app.id) || typeof app.title !== "string" ||
          typeof app.category !== "string" || !Array.isArray(app.architectures)) {
        throw new Error("Existem entradas inválidas ou duplicadas no catálogo.");
      }
      seen.add(app.id);
    }
    // Display the original concept's examples first only when they genuinely
    // exist in the approved published index. Never inject extra app records.
    const preferred = ["plex", "immich", "nextcloud", "jellyfin"];
    function rank(app) {
      const index = preferred.indexOf(app.id.slice(PREFIX.length));
      return index < 0 ? preferred.length : index;
    }
    return data.apps.slice().sort(function (a, b) {
      return rank(a) - rank(b) || appTitle(a).localeCompare(appTitle(b), "pt");
    });
  }
  function verifyRelease(release, appList) {
    if (!release || !Array.isArray(release.approved) ||
        !Number.isInteger(release.approved_count) ||
        release.approved_count !== release.approved.length ||
        release.approved_count !== appList.length) return false;
    const expected = new Set(release.approved.map(function (s) { return PREFIX + s; }));
    return expected.size === appList.length && appList.every(function (app) { return expected.has(app.id); });
  }
  async function initialize() {
    $("store-address").textContent = STORE_URL;
    let index;
    try {
      const response = await fetch("./index.json", { cache: "no-store" });
      if (!response.ok) throw new Error("HTTP " + response.status);
      index = await response.json(); state.apps = validateIndex(index);
    } catch (_) {
      setNotice("Não foi possível carregar o índice da MrStore. O catálogo público pode ainda estar a ser publicado. Consulta o GitHub Actions para o estado do release.", true);
      $("catalog-state").textContent = "Catálogo indisponível.";
      $("results-summary").textContent = "Indisponível"; return;
    }
    $("total-apps").textContent = String(state.apps.length);
    try {
      const reply = await fetch("./release-status.json", { cache: "no-store" });
      if (!reply.ok) throw new Error("Sem relatório de publicação");
      state.validated = verifyRelease(await reply.json(), state.apps);
    } catch (_) { state.validated = false; }
    if (state.validated) {
      setNotice("Catálogo publicado a partir da seleção aprovada pelo processo automático de verificação do MrStore. Um scan sem alertas conhecidos não garante ausência absoluta de vulnerabilidades; confirma os requisitos antes de instalar.", false);
    } else {
      setNotice("Esta edição pública não inclui evidência completa de quarentena, ou existe uma divergência entre o índice e os relatórios. Podes consultar as fichas, mas NÃO interpretes estas aplicações como aprovadas pelos scanners atuais. Verifica os relatórios no GitHub antes de instalar.", true);
    }
    categoryList(); render();
    checkUniversalPublication(); checkPreviewZip(); checkNativePackages();
  }
  $("search").addEventListener("input", function (event) { state.query = event.target.value; state.limit = BATCH_SIZE; render(); });
  $("architecture").addEventListener("change", function (event) { state.arch = event.target.value; state.limit = BATCH_SIZE; render(); });
  $("favorites-toggle").addEventListener("click", function () {
    state.favoritesOnly = !state.favoritesOnly;
    $("favorites-toggle").setAttribute("aria-pressed", String(state.favoritesOnly));
    state.limit = BATCH_SIZE; render();
  });
  $("load-more").addEventListener("click", function () { state.limit += BATCH_SIZE; render(); });
  $("details-close").addEventListener("click", function () { $("details").close(); });
  document.addEventListener("keydown", function (event) {
    if (event.key !== "/" || event.ctrlKey || event.metaKey || event.altKey) return;
    if (document.activeElement && ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) return;
    if ($("details").open) return;
    event.preventDefault(); $("search").focus();
  });
  $("platform-select").addEventListener("change", renderPlatform);
  $("copy-store").addEventListener("click", async function () {
    try {
      if (!navigator.clipboard || !navigator.clipboard.writeText) throw new Error("Clipboard não disponível");
      if (!selectedStoreURL) return;
      await navigator.clipboard.writeText(selectedStoreURL);
      $("copy-feedback").textContent = "Endereço copiado!";
    } catch (_) { $("copy-feedback").textContent = "Seleciona e copia o endereço manualmente."; }
  });
  renderPlatform(); readFavorites(); initialize();
})();

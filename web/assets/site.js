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

  const slugOf = (app) => app.id.slice(PREFIX.length);
  const photoApp = (app) => /^(immich|photoprism|piwigo|lychee|librephotos|ente|chevereto|photostructure)$/.test(slugOf(app));
  const filesApp = (app) => /^(nextcloud|seafile|filebrowser|filebrowser-quantum|filestash|owncloud|pydio|sftpgo|samba|copyparty)$/.test(slugOf(app));
  const backupApp = (app) => /^(duplicati|syncthing|restic|resticprofile|borgmatic|urbackup|kopia|duplicacy|backrest)$/.test(slugOf(app)) || /backup/.test(slugOf(app));
  const COLLECTIONS = [
    {key:"",name:"Todas",description:"Ver todas as aplicações",glyph:"▦",match:()=>true},
    {key:"media",name:"Multimédia",description:"Filmes, séries e música",glyph:"▣",match:(a)=>a.category==="Media"&&!photoApp(a)},
    {key:"photos",name:"Fotografias",description:"Organiza as tuas fotos",glyph:"▧",match:photoApp},
    {key:"files",name:"Ficheiros",description:"Armazenamento e partilha",glyph:"▱",match:filesApp},
    {key:"backup",name:"Cópias de segurança",description:"Protege os teus dados",glyph:"⟳",match:backupApp},
    {key:"utilities",name:"Utilitários",description:"Ferramentas úteis",glyph:"⚒",match:(a)=>["Productivity","Utilities","Others","Home","Social"].includes(a.category)&&!filesApp(a)&&!backupApp(a)},
    {key:"development",name:"Desenvolvimento",description:"Para programadores",glyph:"⌘",match:(a)=>a.category==="Developer"},
    {key:"network",name:"Rede e segurança",description:"Monitoriza e protege",glyph:"⬡",match:(a)=>["Networking","Network","Security"].includes(a.category)}
  ];
  function displayCategory(app) {
    if (photoApp(app)) return "Fotografias";
    if (filesApp(app)) return "Ficheiros";
    if (backupApp(app)) return "Cópias de segurança";
    return categoryLabel(app.category);
  }
  const $ = (id) => document.getElementById(id);
  const state = { apps: [], filtered: [], category: "", query: "", arch: "",
    favoritesOnly: false, limit: BATCH_SIZE, expanded: false, saved: new Set(), validated: false };
  const base = new URL("./", window.location.href);
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
    const list = $("categories"); list.replaceChildren();
    COLLECTIONS.forEach(function (collection) {
      const count = state.apps.filter(collection.match).length;
      const active = state.category === collection.key;
      const button = element("button", "chip" + (active ? " active" : ""));
      button.type = "button"; button.dataset.category = collection.key;
      button.setAttribute("aria-pressed", String(active));
      button.setAttribute("aria-label", collection.name + ": " + count + " aplicações");
      button.title = count + " aplicações nesta categoria";
      button.appendChild(element("span", "chip-symbol", collection.glyph));
      const content = element("span", "chip-copy");
      content.appendChild(element("strong", "chip-label", collection.name));
      content.appendChild(element("small", "chip-desc", collection.description));
      button.appendChild(content);
      button.addEventListener("click", function () {
        state.category = collection.key;
        state.expanded = true;
        state.limit = BATCH_SIZE;
        $("catalog-tools").hidden = false;
        categoryList(); render();
        $("catalog-title").scrollIntoView({behavior: "smooth",block:"start"});
      });
      list.appendChild(button);
    });
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
    footer.appendChild(element("span", "app-category app-category-pill", displayCategory(app)));
    footer.appendChild(arches);
    const details = element("button", "details-button", "♧ Instalar");
    details.setAttribute("aria-label", "Como instalar " + appTitle(app));
    details.type = "button"; details.addEventListener("click", function () { openDetails(app); });
    footer.appendChild(details); card.appendChild(footer);
    return card;
  }
  function render() {
    const needle = fold(state.query.trim());
    const collection = COLLECTIONS.find(function (c) {return c.key===state.category;}) || COLLECTIONS[0];
    state.filtered = state.apps.filter(function (app) {
      return collection.match(app) &&
        (!state.arch || (app.architectures || []).includes(state.arch)) &&
        (!state.favoritesOnly || state.saved.has(app.id)) &&
        (!needle || scoreSearch(app, needle));
    });
    const maxVisible = state.expanded ? state.limit : 4;
    const grid = $("app-grid"), fragment = document.createDocumentFragment();
    state.filtered.slice(0, maxVisible).forEach(function (app) { fragment.appendChild(makeCard(app)); });
    grid.replaceChildren(fragment);
    const shown = Math.min(maxVisible, state.filtered.length);
    $("catalog-title").textContent = state.expanded ? "Explorar aplicações" : "Aplicações em destaque";
    $("catalog-subtitle").textContent = state.expanded
      ? "Pesquisa as aplicações disponíveis nesta edição da MrStore"
      : "As aplicações em destaque disponíveis nesta edição da MrStore";
    $("catalog-tools").hidden = !state.expanded;
    const showAll = $("show-all");
    showAll.setAttribute("aria-expanded", String(state.expanded));
    showAll.textContent = state.expanded ? "Voltar aos destaques ↑" : "Ver todas as aplicações →";
    $("results-summary").hidden = !state.expanded;
    $("results-summary").textContent = state.filtered.length + " resultado(s)";
    $("catalog-state").hidden = state.filtered.length > 0;
    if (!state.filtered.length) {
      $("catalog-state").textContent = "Não encontrámos aplicações com estes filtros. Experimenta outra pesquisa ou categoria.";
    }
    const more = $("load-more");
    more.hidden = !state.expanded || shown >= state.filtered.length;
    if (!more.hidden) more.textContent = "Mostrar mais aplicações (" + (state.filtered.length - shown) + " restantes) ↓";
  }
  function openDetails(app) {
    $("details-icon").replaceChildren(iconNode(app, "detail-icon-inner"));
    $("details-title").textContent = appTitle(app);
    $("details-tagline").textContent = app.tagline || "Aplicação self-hosted";
    $("details-category").textContent = displayCategory(app);
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
  }
  $("show-all").addEventListener("click", function () {
    state.expanded = !state.expanded;
    if (!state.expanded) {
      state.category = ""; state.query = ""; state.arch = ""; state.favoritesOnly = false;
      $("search").value = ""; $("architecture").value = "";
      $("favorites-toggle").setAttribute("aria-pressed", "false");
      categoryList();
    }
    state.limit = BATCH_SIZE; render();
  });
  $("show-install-guide").addEventListener("click", function () {
    $("como-instalar").hidden = false;
    $("como-instalar").scrollIntoView({behavior:"smooth",block:"start"});
  });
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
    event.preventDefault(); state.expanded = true; render(); $("search").focus();
  });
  $("copy-store").addEventListener("click", async function () {
    try {
      if (!navigator.clipboard || !navigator.clipboard.writeText) throw new Error("Clipboard não disponível");
      await navigator.clipboard.writeText(STORE_URL);
      $("copy-feedback").textContent = "Endereço copiado!";
    } catch (_) { $("copy-feedback").textContent = "Seleciona e copia o endereço manualmente."; }
  });
  readFavorites(); initialize();
})();

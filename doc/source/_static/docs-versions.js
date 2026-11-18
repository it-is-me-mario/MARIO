/* Keep the reading position when switching documentation channels. */
(function () {
  const galleryChannel = "model_gallery";
  const channelParameter = "mario_channel";
  const galleryRoot = "https://www.marioproject.com/en/model_gallery/";
  const sharedSites = new Set(["tutorials.marioproject.com", "explorer.marioproject.com"]);
  const librarySites = new Set(["www.marioproject.com", "marioproject.com"]);
  const galleryPages = new Set([
    "", "index.html", "changelog.html",
    "get_started/index.html", "get_started/table_formats.html", "get_started/scenarios.html",
    "user_guide/index.html", "user_guide/parsers/index.html", "user_guide/inspection/index.html",
    "user_guide/analysis/index.html", "user_guide/transformations/index.html",
    "user_guide/configuration/index.html", "user_guide/configuration/model_setups.html",
    "reference/api_library.html", "reference/api_model_methods.html",
    "api_document/mario.models.install.html", "api_document/mario.model_setup.html",
    "api_document/pv_hlca.project.Project.html",
    "resources/teaching.html", "resources/projects_publications.html", "resources/material.html",
  ]);

  function isGalleryContext(location, channel) {
    return channel === galleryChannel || (
      (sharedSites.has(location.hostname) || librarySites.has(location.hostname)) &&
      location.searchParams.get(channelParameter) === galleryChannel
    );
  }

  function markGallery(target) {
    target.searchParams.set(channelParameter, galleryChannel);
    return target;
  }

  // Keep data files and notebook downloads at their ordinary URLs.
  function isPage(target) {
    const filename = target.pathname.split("/").pop();
    return ["https:", "http:"].includes(target.protocol) &&
      (!filename.includes(".") || filename.endsWith(".html"));
  }

  function withGalleryContext(target) {
    if (!isPage(target)) return;
    if (sharedSites.has(target.hostname)) {
      return markGallery(target);
    }
    if (!librarySites.has(target.hostname)) return;
    const libraryPath = target.pathname === "/" ? "" :
      target.pathname.match(/^\/en\/(?:latest|dev)\/(.*)$/)?.[1];
    if (!galleryPages.has(libraryPath)) return;
    const destination = new URL(libraryPath === "index.html" ? "" : libraryPath, galleryRoot);
    destination.search = target.search;
    destination.searchParams.delete(channelParameter);
    if (target.hash) destination.hash = target.hash;
    return destination;
  }

  function addGalleryMenuLink(section, label, page, index) {
    const list = document.querySelector(`[data-nav-section=${section}] .mario-nav__panel ul`);
    if (!list) return;
    const item = document.createElement("li");
    const link = document.createElement("a");
    link.textContent = label;
    link.href = new URL(page, galleryRoot).href;
    item.append(link);
    list.insertBefore(item, list.children[index] || null);
  }

  function applyGalleryContext(menu) {
    const usingExistingPage = menu.dataset.channel !== galleryChannel;
    if (usingExistingPage) {
      menu.dataset.channel = galleryChannel;
      const summary = menu.querySelector("summary");
      const label = menu.querySelector("[data-docs-channel-label]");
      if (label) label.textContent = "Model Gallery";
      summary.setAttribute("aria-label", "Documentation, Model Gallery");
      for (const choice of menu.querySelectorAll("a[data-docs-version]")) {
        if (choice.dataset.docsVersion === galleryChannel) choice.setAttribute("aria-current", "page");
        else choice.removeAttribute("aria-current");
      }
      const setup = "user_guide/configuration/model_setups.html";
      addGalleryMenuLink("get_started", "Install a model", setup + "#install-a-model");
      addGalleryMenuLink("get_started", "Open a project", setup + "#open-a-project");
      addGalleryMenuLink("docs", "Model guides", "");
      addGalleryMenuLink("resources", "Model Gallery", "", 1);
    }

    function decorate(link) {
      if (link.hasAttribute("data-docs-version") || link.hasAttribute("download")) return;
      const href = link.getAttribute("href");
      if (!href || href.startsWith("#")) return;
      const target = new URL(href, window.location.href);
      const destination = withGalleryContext(target);
      if (destination) link.setAttribute("href", destination.href);
      else if (usingExistingPage && librarySites.has(target.hostname) &&
               /^\/en\/(?:latest|dev)\//.test(target.pathname)) {
        const item = link.closest(".mario-nav__panel li");
        if (item) item.remove();
        else if (isPage(target)) {
          link.setAttribute("href", markGallery(target).href);
        }
      }
    }

    document.querySelectorAll("a[href]").forEach(decorate);
    // Search results and some Explorer links are created after the initial render.
    const followLink = (event) => {
      const link = event.target.closest?.("a[href]");
      if (link) decorate(link);
    };
    document.addEventListener("click", followLink, true);
    document.addEventListener("auxclick", followLink, true);
  }

  function updateLinks(menu, catalogue, location) {
    const page = menu.dataset.document;
    let anchor = location.hash.slice(1);
    try { anchor = decodeURIComponent(anchor); } catch (error) { /* Keep literal fragments. */ }
    menu.querySelectorAll("a[data-docs-version]").forEach((link) => {
      const key = link.dataset.docsVersion;
      const version = catalogue?.versions[key];
      const anchors = version?.redirects?.includes(page) ? undefined : version?.documents[page];
      let target;
      if (key === galleryChannel && !anchors &&
          (sharedSites.has(location.hostname) || librarySites.has(location.hostname))) {
        target = new URL(location.href);
        if (!target.pathname.startsWith("/en/model_gallery/")) markGallery(target);
      } else if (version) {
        target = new URL(anchors ? page + ".html" : "index.html", version.url);
        if (anchors) {
          target.search = location.search;
          target.searchParams.delete(channelParameter);
          if (anchors.includes(anchor)) target.hash = location.hash;
        }
      } else {
        return;
      }
      link.href = target.href;
      link.target = "_self";
    });
  }

  if (typeof module === "object") module.exports = {updateLinks, isGalleryContext, withGalleryContext};
  if (typeof document === "undefined") return;
  const menu = document.querySelector("[data-docs-versions]");
  if (!menu) return;
  const location = new URL(window.location.href);
  if (isGalleryContext(location, menu.dataset.channel)) applyGalleryContext(menu);
  let catalogue;
  const refresh = () => updateLinks(menu, catalogue, new URL(window.location.href));
  refresh();
  window.addEventListener("hashchange", refresh);
  menu.addEventListener("toggle", refresh);
  fetch(menu.dataset.catalogue)
    .then((response) => {
      if (!response.ok) throw new Error("Version catalogue unavailable");
      return response.json();
    })
    .then((versions) => {
      catalogue = versions;
      refresh();
    })
    .catch(() => { /* The current page remains available in Gallery context. */ });
  document.addEventListener("click", (event) => {
    if (!menu.contains(event.target)) menu.open = false;
  });
  menu.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      menu.open = false;
      menu.querySelector("summary").focus();
    }
  });
})();

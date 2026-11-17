/* Native home links remain available while matching pages are resolved. */
(function () {
  const galleryChannel = "model_gallery";
  const channelParameter = "mario_channel";
  const galleryRoot = "https://www.marioproject.com/en/model_gallery/";
  const sharedSites = new Set(["tutorials.marioproject.com", "explorer.marioproject.com"]);
  const galleryPages = new Map([
    ["", ""],
    ["index.html", ""],
    ["get_started/index.html", "user_guide/configuration/model_setups.html#install-a-model"],
    ["user_guide/index.html", "user_guide/index.html"],
    ["user_guide/configuration/index.html", "user_guide/configuration/model_setups.html"],
    ["user_guide/configuration/model_setups.html", "user_guide/configuration/model_setups.html"],
    ["reference/api_library.html", "reference/api_model_methods.html"],
    ["reference/api_model_methods.html", "reference/api_model_methods.html"],
    ["api_document/mario.models.install.html", "api_document/mario.models.install.html"],
    ["api_document/mario.model_setup.html", "api_document/mario.model_setup.html"],
    ["api_document/pv_hlca.project.Project.html", "api_document/pv_hlca.project.Project.html"],
    ["resources/teaching.html", "resources/teaching.html"],
    ["resources/projects_publications.html", "resources/projects_publications.html"],
    ["resources/material.html", "resources/material.html"],
    ["changelog.html", "https://github.com/it-is-me-mario/MARIO/releases"],
  ]);

  function isGalleryContext(location, channel) {
    return channel === galleryChannel || (
      sharedSites.has(location.hostname) && location.searchParams.get(channelParameter) === galleryChannel
    );
  }

  function withGalleryContext(target) {
    if (sharedSites.has(target.hostname)) {
      // Keep data files and notebook downloads at their ordinary URLs.
      const filename = target.pathname.split("/").pop();
      if (filename.includes(".") && !filename.endsWith(".html")) return;
      target.searchParams.set(channelParameter, galleryChannel);
      return target;
    }
    if (!["www.marioproject.com", "marioproject.com"].includes(target.hostname)) return;
    const libraryPath = target.pathname === "/" ? "" :
      target.pathname.match(/^\/en\/(?:latest|dev)\/(.*)$/)?.[1];
    if (!galleryPages.has(libraryPath)) return;
    const destination = new URL(galleryPages.get(libraryPath), galleryRoot);
    destination.search = target.search;
    if (target.hash) destination.hash = target.hash;
    return destination;
  }

  function applyGalleryContext(menu, location) {
    if (sharedSites.has(location.hostname)) {
      menu.dataset.channel = galleryChannel;
      const summary = menu.querySelector("summary");
      const label = menu.querySelector("[data-docs-channel-label]");
      if (label) label.textContent = "Model Gallery";
      summary.setAttribute("aria-label", "Documentation, Model Gallery");
      for (const choice of menu.querySelectorAll("a[data-docs-version]")) {
        if (choice.dataset.docsVersion === galleryChannel) choice.setAttribute("aria-current", "page");
        else choice.removeAttribute("aria-current");
      }
    }

    const onSharedSite = sharedSites.has(location.hostname);
    function decorate(link) {
      if (link.hasAttribute("data-docs-version") || link.hasAttribute("download")) return;
      const href = link.getAttribute("href");
      if (!href || href.startsWith("#")) return;
      const target = new URL(href, window.location.href);
      const destination = withGalleryContext(target);
      if (destination) link.setAttribute("href", destination.href);
      else if (onSharedSite && target.hostname === "www.marioproject.com" &&
               /^\/en\/(?:latest|dev)\//.test(target.pathname)) {
        link.closest(".mario-nav__panel li")?.remove();
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
    const current = catalogue.versions[menu.dataset.channel];
    let anchor = location.hash.slice(1);
    try { anchor = decodeURIComponent(anchor); } catch (error) { /* Keep literal fragments. */ }
    menu.querySelectorAll("a[data-docs-version]").forEach((link) => {
      const version = catalogue.versions[link.dataset.docsVersion];
      if (!version) return; // An external section can keep its native link.
      const crossesGallery = (current?.kind === "gallery") !== (version.kind === "gallery");
      const anchors = crossesGallery ? undefined : version.documents[page];
      const filename = anchors ? page + ".html" : "index.html";
      const target = new URL(crossesGallery ? "" : filename, version.url);
      if (anchors && anchors.includes(anchor)) target.hash = location.hash;
      link.href = target.href;
      link.target = "_self";
    });
  }

  if (typeof module === "object") module.exports = {updateLinks, isGalleryContext, withGalleryContext};
  if (typeof document === "undefined") return;
  const menu = document.querySelector("[data-docs-versions]");
  if (!menu) return;
  const location = new URL(window.location.href);
  if (isGalleryContext(location, menu.dataset.channel)) applyGalleryContext(menu, location);
  fetch(menu.dataset.catalogue)
    .then((response) => {
      if (!response.ok) throw new Error("Version catalogue unavailable");
      return response.json();
    })
    .then((catalogue) => {
      const refresh = () => updateLinks(menu, catalogue, window.location);
      refresh();
      window.addEventListener("hashchange", refresh);
    })
    .catch(() => { /* The native links continue to open each version's home. */ });
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

/* Native matrix links work without JS; enhancement shows one definition. */
document.addEventListener("DOMContentLoaded", () => {
  const legacyLink = Array.from(document.querySelectorAll("[data-format-legacy-links] a"))
    .find((link) => `#${link.id}` === window.location.hash);
  if (legacyLink) {
    window.location.replace(legacyLink.href);
    return;
  }
  document.querySelectorAll("[data-table-map]").forEach((map) => {
    const links = Array.from(map.querySelectorAll("[data-matrix-link]"));
    const definitions = Array.from(map.querySelectorAll("[data-matrix-definition]"));
    if (!links.length || links.some((link) => !definitions.some((node) => node.id === link.dataset.matrixLink))) return;
    const panels = Array.from(map.querySelectorAll('[data-table-mode]'));
    const buttons = Array.from(map.querySelectorAll('[data-table-mode-button]'));
    let mode = 'flows';
    let selected = links[0];
    const showMode = (value) => {
      mode = value;
      panels.forEach((panel) => { panel.hidden = panel.dataset.tableMode !== mode; });
      buttons.forEach((button) => { button.setAttribute('aria-pressed', String(button.dataset.tableModeButton === mode)); });
      map.classList.toggle('is-coefficients', mode === 'coefficients');
    };
    const select = (id) => {
      const link = links.find((node) => node.dataset.matrixLink === id);
      if (!link) return;
      selected = link;
      showMode(link.closest('[data-table-mode]').dataset.tableMode);
      definitions.forEach((node) => { node.hidden = node.id !== id; });
      links.forEach((link) => {
        if (link.dataset.matrixLink === id) link.setAttribute("aria-current", "true");
        else link.removeAttribute("aria-current");
      });
    };
    map.classList.add("is-enhanced");
    const controls = map.querySelector('[data-table-mode-controls]');
    if (controls) controls.hidden = false;
    buttons.forEach((button) => button.addEventListener('click', () => {
      const panel = panels.find((node) => node.dataset.tableMode === button.dataset.tableModeButton);
      const match = Array.from(panel.querySelectorAll('[data-matrix-link]'))
        .find((link) => link.dataset.flowName === selected.dataset.flowName) || panel.querySelector('[data-matrix-link]');
      if (match) {
        select(match.dataset.matrixLink);
        window.history.replaceState(null, '', match.hash);
      }
    }));
    select(links[0].dataset.matrixLink);
    select(window.location.hash.slice(1));
    links.forEach((link) => link.addEventListener("click", (event) => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      select(link.dataset.matrixLink);
      window.history.replaceState(null, "", link.hash);
    }));
    window.addEventListener("hashchange", () => select(window.location.hash.slice(1)));
  });
});

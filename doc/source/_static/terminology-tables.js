// Filterable tables (nomenclature tables from doc/scripts/generate_nomenclature_tables.py).
// Tables with data-preview-rows show only their first rows plus a toggle row
// to expand the rest; typing in a filter searches every row.
document.addEventListener("DOMContentLoaded", () => {
  const chevron =
    '<svg class="terminology-toggle__icon" aria-hidden="true" viewBox="0 0 24 24"><path d="m6 9 6 6 6-6"/></svg>';

  document.querySelectorAll(".terminology-table").forEach((table) => {
    const body = table.tBodies[0];
    const rows = Array.from(body ? body.rows : []);
    const columnInputs = Array.from(table.querySelectorAll(".terminology-column-filter"));
    const preview = Number(table.dataset.previewRows || 0);
    const label = table.dataset.previewLabel || "rows";
    const collapsible = preview > 0 && rows.length > preview + 1;
    let expanded = false;

    let toggleRow = null;
    let toggleButton = null;
    if (collapsible) {
      toggleRow = document.createElement("tr");
      toggleRow.className = "terminology-toggle-row";
      const cell = document.createElement("td");
      cell.colSpan = table.tHead ? table.tHead.rows[0].cells.length : rows[0].cells.length;
      toggleButton = document.createElement("button");
      toggleButton.type = "button";
      toggleButton.className = "terminology-toggle";
      toggleButton.setAttribute("aria-controls", table.id);
      cell.appendChild(toggleButton);
      toggleRow.appendChild(cell);
      body.appendChild(toggleRow);
      table.classList.add("is-collapsible");
    }

    const renderToggle = (filtering) => {
      if (!toggleRow) {
        return;
      }
      toggleRow.hidden = filtering;
      table.classList.toggle("is-collapsed", !expanded && !filtering);
      toggleButton.setAttribute("aria-expanded", expanded ? "true" : "false");
      toggleButton.innerHTML = expanded
        ? `<span class="terminology-toggle__text">Show fewer ${label}</span>${chevron}`
        : `<span class="terminology-toggle__dots" aria-hidden="true">…</span>` +
          `<span class="terminology-toggle__text">Show all ${rows.length} ${label}</span>${chevron}`;
    };

    const applyFilter = () => {
      const columnQueries = columnInputs.map((input) => ({
        index: Number(input.dataset.colIndex),
        query: input.value.trim().toLowerCase(),
      }));
      const filtering = columnQueries.some(({ query }) => query);

      let shown = 0;
      rows.forEach((row) => {
        const cells = Array.from(row.children);
        const matchesColumns = columnQueries.every(({ index, query }) => {
          if (!query) {
            return true;
          }
          const cell = cells[index];
          const text = cell ? cell.textContent.toLowerCase() : "";
          return text.includes(query);
        });
        const inPreview = !collapsible || expanded || filtering || shown < preview;
        row.style.display = matchesColumns && inPreview ? "" : "none";
        if (matchesColumns) {
          shown += 1;
        }
      });
      renderToggle(filtering);
    };

    if (toggleButton) {
      toggleButton.addEventListener("click", () => {
        expanded = !expanded;
        applyFilter();
        if (!expanded) {
          const box = toggleRow.getBoundingClientRect();
          if (box.top < 0 || box.bottom > window.innerHeight) {
            toggleRow.scrollIntoView({ block: "center" });
          }
        }
      });
    }

    columnInputs.forEach((input) => input.addEventListener("input", applyFilter));
    applyFilter();
  });
});

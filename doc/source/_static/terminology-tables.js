document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".terminology-table").forEach((table) => {
    const rows = Array.from(table.querySelectorAll("tbody tr"));
    const columnInputs = Array.from(table.querySelectorAll(".terminology-column-filter"));

    const applyFilter = () => {
      const columnQueries = columnInputs.map((input) => ({
        index: Number(input.dataset.colIndex),
        query: input.value.trim().toLowerCase(),
      }));

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

        row.style.display = matchesColumns ? "" : "none";
      });
    };

    columnInputs.forEach((input) => input.addEventListener("input", applyFilter));
    applyFilter();
  });
});

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".parser-coverage-query").forEach((container) => {
    const dataNode = container.querySelector(".parser-coverage-data");
    if (!dataNode) {
      return;
    }

    const countrySelect = container.querySelector('select[name="country"]');
    const yearSelect = container.querySelector('select[name="year"]');
    const form = container.querySelector(".parser-coverage-form");
    const resetButton = container.querySelector('[data-action="reset"]');
    const resultsWrapper = container.querySelector(".parser-coverage-results");
    const resultsBody = container.querySelector(".parser-coverage-results-table tbody");
    const summary = container.querySelector(".parser-coverage-summary");
    const message = container.querySelector(".parser-coverage-message");

    let rows = [];
    try {
      rows = JSON.parse(dataNode.textContent);
    } catch (error) {
      message.textContent = `Could not load parser coverage data: ${error.message}`;
      return;
    }

    const uniqueSortedText = (values) =>
      Array.from(new Set(values.filter(Boolean))).sort((left, right) => left.localeCompare(right));

    const uniqueSortedYears = (values) =>
      Array.from(new Set(values.filter(Boolean))).sort((left, right) => Number(left) - Number(right));

    const resolveParserPageHref = (page) => {
      if (!page) {
        return "";
      }

      if (
        page.startsWith("http://") ||
        page.startsWith("https://") ||
        page.startsWith("../") ||
        page.startsWith("./") ||
        page.startsWith("/") ||
        page.endsWith(".html")
      ) {
        return page;
      }

      if (page === "exiobase") {
        return "../../notebooks/parsers/exiobase/monetary.html";
      }

      if (page.includes("/")) {
        return `../../notebooks/parsers/${page}.html`;
      }

      return `../../notebooks/parsers/${page}/walkthrough_${page}.html`;
    };

    const fillSelect = (select, values, placeholder, keepValue = "") => {
      select.innerHTML = "";
      const blank = document.createElement("option");
      blank.value = "";
      blank.textContent = placeholder;
      select.appendChild(blank);

      values.forEach((value) => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        if (value === keepValue) {
          option.selected = true;
        }
        select.appendChild(option);
      });

      if (keepValue && !values.includes(keepValue)) {
        select.value = "";
      }
    };

    const allCountries = uniqueSortedText(rows.map((row) => row.country));
    const allYears = uniqueSortedYears(rows.flatMap((row) => row.year_values || []));

    const makeLinkedCell = (text, href = "") => {
      const td = document.createElement("td");
      if (href && text) {
        const link = document.createElement("a");
        link.href = href;
        link.textContent = text;
        td.appendChild(link);
      } else {
        td.textContent = text || "";
      }
      return td;
    };

    const matchingRows = ({ country = countrySelect.value, year = yearSelect.value } = {}) =>
      rows.filter((row) => {
        const countryMatch = !country || row.country === country;
        const yearMatch = !year || (row.year_values || []).includes(year);
        return countryMatch && yearMatch;
      });

    const syncOptions = (changedField) => {
      const selectedCountry = countrySelect.value;
      const selectedYear = yearSelect.value;

      const rowsForCountry = rows.filter((row) => !selectedCountry || row.country === selectedCountry);
      const rowsForYear = rows.filter((row) => !selectedYear || (row.year_values || []).includes(selectedYear));

      const yearValues = uniqueSortedYears(rowsForCountry.flatMap((row) => row.year_values || []));
      const countryValues = uniqueSortedText(rowsForYear.map((row) => row.country));

      fillSelect(
        yearSelect,
        yearValues,
        "All years",
        changedField === "country" ? selectedYear : yearSelect.value
      );
      fillSelect(
        countrySelect,
        countryValues,
        "All countries",
        changedField === "year" ? selectedCountry : countrySelect.value
      );
    };

    const renderResults = (filteredRows) => {
      resultsBody.innerHTML = "";
      if (!countrySelect.value && !yearSelect.value) {
        resultsWrapper.hidden = true;
        message.textContent = "No query submitted yet.";
        return;
      }

      message.textContent = "";
      resultsWrapper.hidden = false;
      summary.textContent = `${filteredRows.length} matching row${filteredRows.length === 1 ? "" : "s"}.`;

      if (!filteredRows.length) {
        const emptyRow = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 10;
        cell.textContent = "No matching coverage rows.";
        emptyRow.appendChild(cell);
        resultsBody.appendChild(emptyRow);
        return;
      }

      filteredRows.forEach((row) => {
        const tr = document.createElement("tr");
        const parserPageHref = resolveParserPageHref(row.parser_page);
        tr.appendChild(makeLinkedCell(row.source, parserPageHref));
        tr.appendChild(makeLinkedCell(row.parser, parserPageHref));
        [
          row.table,
          row.years,
          row.version,
          row.scope,
          row.country,
          row.iso3,
          row.source_code,
          row.notes,
        ].forEach((value) => {
          const td = document.createElement("td");
          td.textContent = value || "";
          tr.appendChild(td);
        });
        resultsBody.appendChild(tr);
      });
    };

    fillSelect(countrySelect, allCountries, "All countries");
    fillSelect(yearSelect, allYears, "All years");

    countrySelect.addEventListener("change", () => syncOptions("country"));
    yearSelect.addEventListener("change", () => syncOptions("year"));

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      renderResults(matchingRows());
    });

    resetButton.addEventListener("click", () => {
      fillSelect(countrySelect, allCountries, "All countries");
      fillSelect(yearSelect, allYears, "All years");
      renderResults([]);
    });
  });
});

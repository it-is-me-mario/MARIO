document.addEventListener("DOMContentLoaded", () => {
  const contentRoot =
    document.documentElement.getAttribute("data-content_root") ||
    (window.DOCUMENTATION_OPTIONS && DOCUMENTATION_OPTIONS.URL_ROOT) ||
    "./";
  const manifestUrl = `${contentRoot}_static/data/docs-assistant-manifest.json`;

  const root = document.createElement("div");
  root.className = "mario-doc-assistant pst-js-only";
  root.innerHTML = `
    <button type="button" class="mario-doc-assistant__toggle" aria-expanded="false" aria-controls="mario-doc-assistant-panel">
      Ask MARIO Docs
    </button>
    <section class="mario-doc-assistant__panel" id="mario-doc-assistant-panel" hidden>
      <div class="mario-doc-assistant__header">
        <div>
          <p class="mario-doc-assistant__eyebrow">Experimental</p>
          <h2>Ask MARIO Docs</h2>
          <p>Find the right page, workflow, or API entry point without leaving the docs.</p>
        </div>
        <button type="button" class="mario-doc-assistant__close" aria-label="Close assistant">&times;</button>
      </div>
      <form class="mario-doc-assistant__form">
        <label class="mario-doc-assistant__label" for="mario-doc-assistant-input">Ask a documentation question</label>
        <div class="mario-doc-assistant__input-row">
          <input id="mario-doc-assistant-input" name="query" type="search" placeholder="How do I convert a SUT to IOT?" autocomplete="off" />
          <button type="submit" class="btn btn-primary btn-sm">Search</button>
        </div>
      </form>
      <div class="mario-doc-assistant__prompts" aria-label="Suggested questions"></div>
      <div class="mario-doc-assistant__status" aria-live="polite">Loading assistant knowledge...</div>
      <div class="mario-doc-assistant__results"></div>
    </section>
  `;
  document.body.appendChild(root);

  const toggleButton = root.querySelector(".mario-doc-assistant__toggle");
  const closeButton = root.querySelector(".mario-doc-assistant__close");
  const panel = root.querySelector(".mario-doc-assistant__panel");
  const form = root.querySelector(".mario-doc-assistant__form");
  const input = root.querySelector("#mario-doc-assistant-input");
  const prompts = root.querySelector(".mario-doc-assistant__prompts");
  const status = root.querySelector(".mario-doc-assistant__status");
  const results = root.querySelector(".mario-doc-assistant__results");

  let manifest = [];
  const readyMessage = "Ask about installation, parsers, workflows, exports, or a specific MARIO method.";

  const openPanel = () => {
    panel.hidden = false;
    toggleButton.setAttribute("aria-expanded", "true");
    root.dataset.state = "open";
    input.focus();
  };

  const closePanel = () => {
    panel.hidden = true;
    toggleButton.setAttribute("aria-expanded", "false");
    root.dataset.state = "closed";
  };

  const normalize = (value) =>
    String(value || "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, " ")
      .trim();

  const tokenize = (value) =>
    normalize(value)
      .split(/\s+/)
      .filter((token) => token.length > 1);

  const buildHref = (href) => {
    if (!href) {
      return "#";
    }
    if (/^(https?:)?\/\//.test(href) || href.startsWith("#")) {
      return href;
    }
    return `${contentRoot}${href}`;
  };

  const createLink = (label, href) => {
    const link = document.createElement("a");
    link.href = buildHref(href);
    link.textContent = label;
    return link;
  };

  const clearResults = () => {
    results.innerHTML = "";
  };

  const renderQuickPrompts = () => {
    prompts.innerHTML = "";
    manifest
      .slice(0, 5)
      .filter((entry) => entry.example_query)
      .forEach((entry) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "mario-doc-assistant__prompt";
        button.textContent = entry.example_query;
        button.addEventListener("click", () => {
          input.value = entry.example_query;
          runQuery(entry.example_query);
        });
        prompts.appendChild(button);
      });
  };

  const scoreEntry = (entry, query) => {
    const normalizedQuery = normalize(query);
    const queryTokens = tokenize(query);
    if (!normalizedQuery || !queryTokens.length) {
      return 0;
    }

    let score = 0;
    const title = normalize(entry.title);
    const summary = normalize(entry.summary);
    const keywords = (entry.keywords || []).map(normalize);

    if (normalizedQuery === title) {
      score += 14;
    }
    if (normalizedQuery.includes(title) || title.includes(normalizedQuery)) {
      score += 8;
    }

    keywords.forEach((keyword) => {
      if (!keyword) {
        return;
      }
      if (normalizedQuery.includes(keyword)) {
        score += keyword.includes(" ") ? 6 : 4;
      }
    });

    queryTokens.forEach((token) => {
      if (title.includes(token)) {
        score += 3;
      }
      if (summary.includes(token)) {
        score += 1;
      }
      if (keywords.some((keyword) => keyword.split(" ").includes(token))) {
        score += 2;
      }
    });

    return score;
  };

  const renderSources = (entry) => {
    const wrapper = document.createElement("div");
    wrapper.className = "mario-doc-assistant__sources";

    const heading = document.createElement("p");
    heading.className = "mario-doc-assistant__section-label";
    heading.textContent = "Sources";
    wrapper.appendChild(heading);

    const list = document.createElement("ul");
    (entry.links || []).forEach((item) => {
      const listItem = document.createElement("li");
      const link = createLink(item.label, item.href);
      listItem.appendChild(link);

      if (item.reason) {
        const reason = document.createElement("span");
        reason.textContent = ` - ${item.reason}`;
        listItem.appendChild(reason);
      }

      list.appendChild(listItem);
    });

    wrapper.appendChild(list);
    return wrapper;
  };

  const renderWorkflowAnswer = (entry) => {
    const card = document.createElement("article");
    card.className = "mario-doc-assistant__card";

    const title = document.createElement("h3");
    title.textContent = entry.title;
    card.appendChild(title);

    const summary = document.createElement("p");
    summary.className = "mario-doc-assistant__summary";
    summary.textContent = entry.answer;
    card.appendChild(summary);

    const label = document.createElement("p");
    label.className = "mario-doc-assistant__section-label";
    label.textContent = "Recommended path";
    card.appendChild(label);

    const steps = document.createElement("ol");
    steps.className = "mario-doc-assistant__steps";
    (entry.links || []).forEach((item) => {
      const step = document.createElement("li");
      const link = createLink(item.label, item.href);
      step.appendChild(link);
      if (item.reason) {
        const reason = document.createElement("p");
        reason.textContent = item.reason;
        step.appendChild(reason);
      }
      steps.appendChild(step);
    });
    card.appendChild(steps);

    if (entry.snippets && entry.snippets.length) {
      const note = document.createElement("p");
      note.className = "mario-doc-assistant__note";
      note.textContent = entry.snippets[0];
      card.appendChild(note);
    }

    card.appendChild(renderSources(entry));
    return card;
  };

  const renderFactAnswer = (entry) => {
    const card = document.createElement("article");
    card.className = "mario-doc-assistant__card";

    const title = document.createElement("h3");
    title.textContent = entry.title;
    card.appendChild(title);

    const answer = document.createElement("p");
    answer.className = "mario-doc-assistant__summary";
    answer.textContent = entry.answer;
    card.appendChild(answer);

    if (entry.snippets && entry.snippets.length) {
      const list = document.createElement("ul");
      list.className = "mario-doc-assistant__snippets";
      entry.snippets.forEach((snippet) => {
        const item = document.createElement("li");
        item.textContent = snippet;
        list.appendChild(item);
      });
      card.appendChild(list);
    }

    card.appendChild(renderSources(entry));
    return card;
  };

  const renderRankedMatches = (matches, query) => {
    const wrapper = document.createElement("article");
    wrapper.className = "mario-doc-assistant__card";

    const title = document.createElement("h3");
    title.textContent = `Best matches for "${query}"`;
    wrapper.appendChild(title);

    const text = document.createElement("p");
    text.className = "mario-doc-assistant__summary";
    text.textContent = "The query matches multiple documentation paths. Start with one of these entry points.";
    wrapper.appendChild(text);

    const list = document.createElement("ul");
    list.className = "mario-doc-assistant__matches";

    matches.forEach(({ entry }) => {
      const item = document.createElement("li");
      const heading = createLink(entry.title, entry.primary_href || (entry.links && entry.links[0] && entry.links[0].href));
      item.appendChild(heading);

      const reason = document.createElement("p");
      reason.textContent = entry.summary;
      item.appendChild(reason);
      list.appendChild(item);
    });

    wrapper.appendChild(list);
    return wrapper;
  };

  const renderNoMatch = (query) => {
    const card = document.createElement("article");
    card.className = "mario-doc-assistant__card mario-doc-assistant__card--muted";

    const title = document.createElement("h3");
    title.textContent = `No grounded answer for "${query}"`;
    card.appendChild(title);

    const text = document.createElement("p");
    text.className = "mario-doc-assistant__summary";
    text.textContent = "I could not match that request confidently to the current MARIO documentation. Try one of the entry points below or rephrase with a parser, workflow, or method name.";
    card.appendChild(text);

    const fallbackLinks = document.createElement("ul");
    [
      { label: "Setup", href: "setup/index.html" },
      { label: "User guide", href: "user_guide/index.html" },
      { label: "Parsers", href: "user_guide/parsers/index.html" },
      { label: "API reference", href: "reference/api_library.html" },
    ].forEach((item) => {
      const listItem = document.createElement("li");
      listItem.appendChild(createLink(item.label, item.href));
      fallbackLinks.appendChild(listItem);
    });
    card.appendChild(fallbackLinks);
    return card;
  };

  function runQuery(query) {
    const trimmedQuery = String(query || "").trim();
    clearResults();

    if (!trimmedQuery) {
      status.textContent = "Ask about installation, parsers, workflows, exports, or a specific MARIO method.";
      return;
    }

    const matches = manifest
      .map((entry) => ({ entry, score: scoreEntry(entry, trimmedQuery) }))
      .filter((item) => item.score > 0)
      .sort((left, right) => right.score - left.score)
      .slice(0, 3);

    if (!matches.length) {
      status.textContent = "No confident grounding found in the curated assistant knowledge.";
      results.appendChild(renderNoMatch(trimmedQuery));
      return;
    }

    status.textContent = "Grounded answer from curated MARIO docs entry points.";

    if (matches.length > 1 && matches[0].score - matches[1].score < 3) {
      results.appendChild(renderRankedMatches(matches, trimmedQuery));
      return;
    }

    const best = matches[0].entry;
    if (best.type === "workflow") {
      results.appendChild(renderWorkflowAnswer(best));
      return;
    }

    results.appendChild(renderFactAnswer(best));
  }

  toggleButton.addEventListener("click", () => {
    if (panel.hidden) {
      openPanel();
      return;
    }
    closePanel();
  });

  closeButton.addEventListener("click", closePanel);

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    runQuery(input.value);
  });

  const initializeManifest = (data) => {
    manifest = Array.isArray(data) ? data : [];
    if (!manifest.length) {
      throw new Error("Assistant knowledge is empty");
    }
    renderQuickPrompts();
    status.textContent = readyMessage;
  };

  try {
    initializeManifest(window.MARIO_DOC_ASSISTANT_MANIFEST);
  } catch (_error) {
    fetch(manifestUrl)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        return response.json();
      })
      .then((data) => {
        initializeManifest(data);
      })
      .catch((error) => {
        status.textContent = `Could not load the assistant knowledge base: ${error.message}`;
      });
  }
});
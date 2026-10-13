/*
 * MARIO documentation theme behaviour.
 * Everything here is progressive: the pages work and read correctly without it.
 */
(function () {
  "use strict";

  const root = document.documentElement;
  const contentRoot = root.dataset.content_root || "./";
  const shortWindow = window.matchMedia("(max-height: 31.25em)");

  const storage = {
    get(key) {
      try {
        return window.localStorage.getItem(key);
      } catch (error) {
        return null;
      }
    },
    set(key, value) {
      try {
        window.localStorage.setItem(key, value);
      } catch (error) {
        /* private mode or blocked storage: the choice lasts for this page only */
      }
    },
  };

  const cellSize = () => parseFloat(getComputedStyle(root).getPropertyValue("--cell")) *
    parseFloat(getComputedStyle(root).fontSize) || 24;

  /* ------------------------------------------------------------ theme */

  function effectiveTheme() {
    if (root.dataset.theme === "light" || root.dataset.theme === "dark") {
      return root.dataset.theme;
    }
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function initThemeToggle() {
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      button.addEventListener("click", () => {
        const next = effectiveTheme() === "dark" ? "light" : "dark";
        root.dataset.theme = next;
        storage.set("mario-theme", next);
      });
    });
  }

  /* ------------------------------------------- header hides on scroll */

  function initHeader() {
    const header = document.querySelector("[data-header]");
    if (!header) {
      return;
    }
    let lastY = window.scrollY;
    let ticking = false;

    const update = () => {
      const y = window.scrollY;
      const delta = y - lastY;
      if (shortWindow.matches || y < header.offsetHeight || header.querySelector("[data-header-menu][data-open]")) {
        root.classList.remove("mario-header-hidden");
      } else if (delta > 6) {
        root.classList.add("mario-header-hidden");
      } else if (delta < -6) {
        root.classList.remove("mario-header-hidden");
      }
      lastY = y;
      ticking = false;
    };

    window.addEventListener(
      "scroll",
      () => {
        if (!ticking) {
          ticking = true;
          window.requestAnimationFrame(update);
        }
      },
      { passive: true }
    );

    header.addEventListener("focusin", () => root.classList.remove("mario-header-hidden"));
  }

  /* ------------------------------- header: hover, links and disclosures */

  function initHeaderMenus() {
    const menus = Array.from(document.querySelectorAll("[data-header-menu]"));
    const hoverPointer = window.matchMedia("(hover: hover) and (pointer: fine)");
    const timers = new Map();

    const clearClose = (menu) => {
      window.clearTimeout(timers.get(menu));
      timers.delete(menu);
    };
    const setOpen = (menu, open) => {
      clearClose(menu);
      if (open) {
        menus.filter((other) => other !== menu).forEach((other) => setOpen(other, false));
        document.querySelectorAll("details[data-pagebar-menu][open]").forEach((other) => { other.open = false; });
        root.classList.remove("mario-header-hidden");
      }
      menu.toggleAttribute("data-open", open);
      menu.querySelector("[data-header-menu-toggle]").setAttribute("aria-expanded", String(open));
      menu.querySelector(".mario-nav__panel").hidden = !open;
    };

    menus.forEach((menu) => {
      const button = menu.querySelector("[data-header-menu-toggle]");
      const mainLink = menu.querySelector(".mario-nav__link");
      const links = Array.from(menu.querySelectorAll(".mario-nav__panel a"));
      menu.addEventListener("pointerenter", (event) => {
        if (hoverPointer.matches && event.pointerType === "mouse") setOpen(menu, true);
      });
      menu.addEventListener("pointerleave", (event) => {
        if (event.pointerType !== "mouse") return;
        clearClose(menu);
        // Allow the pointer to cross the small gap before the dropdown.
        timers.set(menu, window.setTimeout(() => {
          timers.delete(menu);
          if (!menu.contains(document.activeElement)) setOpen(menu, false);
        }, 150));
      });
      button.addEventListener("click", () => setOpen(menu, !menu.hasAttribute("data-open")));
      [mainLink, button].forEach((control) => {
        control.addEventListener("keydown", (event) => {
          if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
          event.preventDefault();
          setOpen(menu, true);
          const link = event.key === "ArrowDown" ? links[0] : links[links.length - 1];
          if (link) link.focus();
        });
      });
      menu.querySelectorAll("a").forEach((link) => {
        link.addEventListener("click", () => {
          // Preserve native navigation, including Safari and modified clicks.
          window.setTimeout(() => setOpen(menu, false), 0);
        });
      });
      menu.addEventListener("focusin", () => {
        clearClose(menu);
        menus.filter((other) => other !== menu).forEach((other) => setOpen(other, false));
      });
      menu.addEventListener("focusout", (event) => {
        // A null destination can occur before pointer activation in Safari.
        if (event.relatedTarget && !menu.contains(event.relatedTarget)) setOpen(menu, false);
      });
    });
    document.addEventListener("click", (event) => {
      menus.filter((menu) => !menu.contains(event.target)).forEach((menu) => setOpen(menu, false));
    });
    document.addEventListener("keydown", (event) => {
      if (event.key !== "Escape") return;
      menus.forEach((menu) => {
        if (menu.hasAttribute("data-open") && menu.contains(document.activeElement)) {
          menu.querySelector("[data-header-menu-toggle]").focus();
        }
        setOpen(menu, false);
      });
    });
  }

  /* ----------------------------------- snap block heights to the grid */

  function initSnap() {
    const blocks = Array.from(document.querySelectorAll("[data-snap]"));
    if (!blocks.length) {
      return;
    }

    const snap = (element) => {
      const cell = cellSize();
      element.style.minHeight = "";
      const height = element.getBoundingClientRect().height;
      const target = Math.ceil(height / cell - 0.01) * cell;
      if (Math.abs(target - height) > 0.5) {
        element.style.minHeight = `${target}px`;
      }
    };

    const snapAll = () => {
      blocks.forEach(snap);
      updateHeatFade();
    };

    let timer = null;
    const schedule = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(snapAll, 80);
    };

    snapAll();
    window.addEventListener("resize", schedule);
    window.addEventListener("load", schedule);
    if ("ResizeObserver" in window) {
      const observer = new ResizeObserver(schedule);
      blocks.forEach((block) => observer.observe(block.firstElementChild || block));
    }
  }

  /* The heatmap is strongest behind the hero, then fades to a light, constant level. */
  function updateHeatFade() {
    const hero = document.querySelector("[data-hero]");
    const bg = document.querySelector(".mario-bg");
    if (!hero || !bg) {
      return;
    }
    const tabs = document.querySelector("[data-tabs]");
    const bottom = (tabs || hero).getBoundingClientRect().bottom + window.scrollY;
    bg.style.setProperty("--heat-fade-start", `${Math.round(bottom)}px`);
  }

  /* ------------------------- switching tabs keeps the tabs in place */

  // A tab opens another page. Remember where the tab row sat on screen and,
  // on the new page, scroll so it sits in the same place: only the content
  // below seems to change instead of the page starting again from the top.
  const TAB_NAV_KEY = "mario-tab-nav";

  function initTabMemory() {
    document.querySelectorAll("[data-tabs] a[href]").forEach((link) => {
      link.addEventListener("click", (event) => {
        if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
          return;
        }
        const target = new URL(link.href, window.location.href);
        if (target.origin !== window.location.origin || target.pathname === window.location.pathname) {
          return;
        }
        const tabs = link.closest("[data-tabs]");
        try {
          window.sessionStorage.setItem(
            TAB_NAV_KEY,
            JSON.stringify({
              to: target.pathname,
              y: tabs.getBoundingClientRect().top,
              headerHidden: root.classList.contains("mario-header-hidden"),
              t: Date.now(),
            })
          );
          root.classList.add("mario-tab-nav");
        } catch (error) {
          /* storage blocked: the new page simply opens at the top */
        }
      });
    });

    // Back/forward from the cache: drop the marker left by the click.
    window.addEventListener("pageshow", (event) => {
      if (event.persisted) {
        root.classList.remove("mario-tab-nav");
      }
    });

    // Cross-document view transitions run only between tabs.
    window.addEventListener("pageswap", (event) => {
      if (event.viewTransition && !root.classList.contains("mario-tab-nav")) {
        // An intentional skip rejects ready; consume that cancellation.
        event.viewTransition.ready.catch(() => {});
        event.viewTransition.skipTransition();
      }
    });
    window.addEventListener("pagereveal", (event) => {
      if (event.viewTransition && !root.classList.contains("mario-tab-nav")) {
        // An intentional skip rejects ready; consume that cancellation.
        event.viewTransition.ready.catch(() => {});
        event.viewTransition.skipTransition();
      }
    });

    let saved = null;
    try {
      saved = JSON.parse(window.sessionStorage.getItem(TAB_NAV_KEY) || "null");
      window.sessionStorage.removeItem(TAB_NAV_KEY);
    } catch (error) {
      saved = null;
    }
    const entry = performance.getEntriesByType ? performance.getEntriesByType("navigation")[0] : null;
    const tabs = document.querySelector("[data-tabs]");
    const arrivedFromTab =
      saved &&
      tabs &&
      saved.to === window.location.pathname &&
      Date.now() - saved.t < 15000 &&
      !window.location.hash &&
      (!entry || entry.type === "navigate");

    if (arrivedFromTab) {
      const top = tabs.getBoundingClientRect().top + window.scrollY;
      window.scrollTo({ top: Math.max(0, top - saved.y), behavior: "instant" });
      root.classList.toggle("mario-header-hidden", Boolean(saved.headerHidden) && window.scrollY > 0);
    }
    window.setTimeout(() => root.classList.remove("mario-tab-nav"), 700);
  }

  /* ------------- section menu: appears on phones once the hero tabs are gone */

  function initMenu() {
    const menu = document.querySelector("[data-menu]");
    const tabs = document.querySelector("[data-tabs]");
    if (!menu || !tabs) {
      return;
    }
    const details = menu.querySelector("details");
    const column = document.querySelector(".mario-content");
    const header = document.querySelector("[data-header]");

    // Same left edge as the content column, so it mirrors "On this page" on the right.
    const place = () => {
      if (column) {
        menu.style.setProperty("--mario-menu-left", `${Math.max(0, column.getBoundingClientRect().left)}px`);
      }
    };
    place();
    window.addEventListener("resize", place);

    const setVisible = (visible) => {
      menu.classList.toggle("is-visible", visible);
      if (!visible && details) {
        details.open = false;
      }
    };

    if ("IntersectionObserver" in window) {
      const headerHeight = header ? header.offsetHeight : 0;
      new IntersectionObserver(
        ([entry]) => setVisible(!entry.isIntersecting && entry.boundingClientRect.top < 0),
        { rootMargin: `-${headerHeight}px 0px 0px 0px` }
      ).observe(tabs);
    }
  }

  /* ---------------------------------------------- tabs that scroll */

  function initTabs() {
    document.querySelectorAll("[data-tabs]").forEach((tabs) => {
      const track = tabs.querySelector("[data-tabs-track]");
      if (!track) {
        return;
      }
      const update = () => {
        const max = track.scrollWidth - track.clientWidth;
        tabs.classList.toggle("has-more-left", track.scrollLeft > 2);
        tabs.classList.toggle("has-more-right", track.scrollLeft < max - 2);
      };
      const active = track.querySelector('[aria-current="page"]');
      if (active && track.scrollWidth > track.clientWidth) {
        const item = active.closest("li");
        track.scrollLeft = item.offsetLeft - (track.clientWidth - item.offsetWidth) / 2;
      }
      update();
      track.addEventListener("scroll", update, { passive: true });
      window.addEventListener("resize", update);

      // When the tabs wrap (phones), the first tab of each row loses its separator.
      const items = Array.from(track.querySelectorAll("li"));
      const markLineStarts = () => {
        for (let pass = 0; pass < 2; pass += 1) {
          let previousTop = null;
          items.forEach((item) => {
            const top = item.offsetTop;
            item.classList.toggle("is-line-start", previousTop !== null && Math.abs(top - previousTop) > 2);
            previousTop = top;
          });
        }
      };
      markLineStarts();
      window.addEventListener("resize", markLineStarts);
      if (document.fonts && document.fonts.ready) {
        document.fonts.ready.then(markLineStarts);
      }
    });
  }

  /* ------------------------------------ page bar: pages and sections */

  function initPagebar() {
    const menus = Array.from(document.querySelectorAll("[data-pagebar-menu]"));
    menus.forEach((menu) => {
      menu.addEventListener("toggle", () => {
        if (menu.open) {
          menus.filter((other) => other !== menu).forEach((other) => (other.open = false));
        }
      });
      menu.querySelectorAll("a").forEach((link) =>
        link.addEventListener("click", () => {
          // Keep the link visible through its native activation, including Safari.
          window.setTimeout(() => { menu.open = false; }, 0);
        })
      );
    });
    document.addEventListener("click", (event) => {
      menus.forEach((menu) => {
        if (menu.open && !menu.contains(event.target)) {
          menu.open = false;
        }
      });
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        menus.forEach((menu) => {
          if (menu.open && menu.contains(document.activeElement)) {
            menu.querySelector("summary").focus();
          }
          menu.open = false;
        });
      }
    });
    menus.forEach((menu) => {
      menu.addEventListener("focusout", (event) => {
        // A pointer click can blur a summary without focusing its link in Safari.
        // Only close for an actual focus transfer outside; clicks/Escape handle the rest.
        if (event.relatedTarget && !menu.contains(event.relatedTarget)) menu.open = false;
      });
    });

    // Highlight the section being read in the "On this page" list.
    const tocLinks = Array.from(document.querySelectorAll(".mario-localtoc a[href^='#']"));
    if (!tocLinks.length || !("IntersectionObserver" in window)) {
      return;
    }
    const targets = new Map();
    tocLinks.forEach((link) => {
      const id = decodeURIComponent(link.getAttribute("href").slice(1));
      const target = id && document.getElementById(id);
      if (target) {
        targets.set(target, link);
      }
    });
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            tocLinks.forEach((link) => link.classList.remove("is-current"));
            targets.get(entry.target).classList.add("is-current");
          }
        });
      },
      { rootMargin: "-20% 0px -70% 0px" }
    );
    targets.forEach((_, target) => observer.observe(target));
  }

  /* ------------------ switch: big buttons that reveal groups of sections */

  function initSwitch() {
    document.querySelectorAll("[data-switch]").forEach((group) => {
      const options = Array.from(group.querySelectorAll("[data-switch-targets]"));
      const hint = group.parentElement.querySelector("[data-switch-hint]");
      const idsOf = (option) => option.dataset.switchTargets.split(/\s+/).filter(Boolean);
      const panels = new Map(
        options.map((option) => [
          option,
          idsOf(option)
            .map((id) => document.getElementById(id))
            .filter(Boolean)
            .map((element) => element.closest("section") || element),
        ])
      );
      const allPanels = Array.from(new Set([].concat(...panels.values())));
      if (!allPanels.length) {
        return;
      }

      const select = (option, updateHash) => {
        options.forEach((other) => other.setAttribute("aria-pressed", other === option ? "true" : "false"));
        allPanels.forEach((panel) => {
          panel.hidden = !(option && panels.get(option).includes(panel));
        });
        if (hint) {
          hint.hidden = Boolean(option);
        }
        if (option && updateHash) {
          history.replaceState(null, "", `#${idsOf(option)[0]}`);
        }
      };

      const hashTarget = () => {
        const id = decodeURIComponent(window.location.hash.slice(1));
        return id ? document.getElementById(id) : null;
      };
      const optionFor = (target) =>
        target ? options.find((option) => panels.get(option).some((panel) => panel.contains(target))) || null : null;

      options.forEach((option) => option.addEventListener("click", () => select(option, true)));

      const initialTarget = hashTarget();
      const initial = optionFor(initialTarget);
      select(initial, false);
      if (initial && initialTarget) {
        window.requestAnimationFrame(() => initialTarget.scrollIntoView());
      }

      // Links to a hidden section (search results, "On this page", old URLs) open its group.
      window.addEventListener("hashchange", () => {
        const target = hashTarget();
        const option = optionFor(target);
        if (option && option.getAttribute("aria-pressed") !== "true") {
          select(option, false);
          target.scrollIntoView();
        }
      });
    });
  }

  /* --------------------------------- wide tables scroll in their box */

  function initScrollContainers() {
    document.querySelectorAll(".mario-article table").forEach((table) => {
      if (table.closest(".mario-scroll, .terminology-table-wrapper, .mario-api-index")) {
        return;
      }
      if (table.closest("div.output_area")) {
        return;
      }
      const wrapper = document.createElement("div");
      wrapper.className = "mario-scroll";
      table.parentNode.insertBefore(wrapper, table);
      wrapper.appendChild(table);
    });
  }

  /* ---------------------------------------------- copy install line */

  function initCopy() {
    document.querySelectorAll("[data-copy]").forEach((button) => {
      const source = button.parentElement.querySelector("[data-copy-source]");
      const label = button.querySelector("[data-copy-label]");
      if (!source || !navigator.clipboard) {
        return;
      }
      button.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(source.textContent.trim());
          if (label) {
            label.textContent = "Copied";
            window.setTimeout(() => (label.textContent = "Copy"), 1600);
          }
        } catch (error) {
          /* clipboard refused: the command stays selectable on screen */
        }
      });
    });
  }

  /* -------------------------------------------------- contact dialog */

  // Drafts an email in the visitor's own mail app; the site sends and stores nothing.
  function initContact() {
    const dialog = document.querySelector("[data-contact]");
    if (!dialog || typeof dialog.showModal !== "function") {
      return;
    }
    const recipients = dialog.dataset.recipients.split(";").map((pair) => pair.split("|").join("@")).join(",");
    const form = dialog.querySelector("[data-contact-form]");
    document.querySelectorAll("[data-contact-open]").forEach((button) =>
      button.addEventListener("click", () => {
        dialog.showModal();
        form.querySelector("input").focus();
      })
    );
    dialog.querySelector("[data-contact-close]").addEventListener("click", () => dialog.close());
    // A click on the backdrop lands on the dialog itself, outside the form box.
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) {
        dialog.close();
      }
    });
    // Required fields are checked by the browser before this runs.
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const data = new FormData(form);
      const value = (name) => String(data.get(name) || "").trim();
      const details = [
        ["Organisation", value("organisation")],
        ["Number of participants", value("participants")],
        ["Preferred format", value("format")],
      ].filter(([, text]) => text).map(([label, text]) => `${label}: ${text}`);
      const body = ["Hello,", "", "I would be interested in a MARIO course.", "", ...details, "", value("message"), "", ""].join("\n");
      const link = document.createElement("a");
      link.href = `mailto:${recipients}?subject=${encodeURIComponent(dialog.dataset.subject)}&body=${encodeURIComponent(body)}`;
      link.click();
      dialog.close();
    });
  }

  /* --------------------------------------------------- search palette */

  function normalise(text) {
    return String(text || "")
      .toLowerCase()
      .normalize("NFKD")
      .replace(/[̀-ͯ]/g, "")
      .replace(/[^a-z0-9_.]+/g, " ")
      .trim();
  }

  function initPalette() {
    const dialog = document.querySelector("[data-palette]");
    if (!dialog || typeof dialog.showModal !== "function") {
      return;
    }
    const input = dialog.querySelector("[data-palette-input]");
    const list = dialog.querySelector("[data-palette-results]");
    const searchUrl = dialog.dataset.searchUrl;
    const isMac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
    document.querySelectorAll("[data-shortcut]").forEach((node) => {
      node.textContent = isMac ? "⌘K" : "Ctrl K";
    });

    let entries = null;
    let results = [];
    let selected = 0;

    const load = () => {
      if (entries) {
        return Promise.resolve(entries);
      }
      return fetch(`${contentRoot}_static/mario-nav.json`)
        .then((response) => (response.ok ? response.json() : []))
        .catch(() => [])
        .then((data) => {
          entries = data.map((entry) => ({ ...entry, n: normalise(entry.t), ns: normalise(entry.s) }));
          return entries;
        });
    };

    const score = (entry, terms, phrase) => {
      let total = 0;
      for (const term of terms) {
        // Tolerate word endings: "aggregate" also finds "aggregation".
        const stem = term.length > 5 ? term.slice(0, -2) : term;
        let inTitle = entry.n.indexOf(term);
        let weight = 1;
        if (inTitle < 0 && stem !== term) {
          inTitle = entry.n.indexOf(stem);
          weight = 0.75;
        }
        if (inTitle === 0) {
          total += 12 * weight;
        } else if (inTitle > 0) {
          const before = entry.n[inTitle - 1];
          total += (before === " " || before === "." || before === "_" ? 8 : 4) * weight;
        } else if (entry.ns.includes(term) || entry.ns.includes(stem)) {
          total += 1;
        } else {
          return 0;
        }
      }
      if (entry.n === phrase) {
        total += 20;
      }
      if (entry.k === "page") {
        total += 2;
      }
      return total - entry.n.length / 200;
    };

    const render = () => {
      const query = input.value.trim();
      list.innerHTML = "";
      const fullText = { t: `Search the full text for “${query}”`, u: null, s: "All pages", k: "fulltext" };
      const items = query ? [...results, fullText] : results;
      if (!items.length) {
        const empty = document.createElement("li");
        empty.className = "mario-palette__empty";
        empty.textContent = "Type to search pages, sections and API methods.";
        list.appendChild(empty);
        return;
      }
      items.forEach((entry, index) => {
        const item = document.createElement("li");
        item.setAttribute("role", "option");
        item.setAttribute("aria-selected", index === selected ? "true" : "false");
        if (entry.k === "api") {
          item.classList.add("is-api");
        }
        const link = document.createElement("a");
        link.href = entry.u === null ? `${searchUrl}?q=${encodeURIComponent(query)}` : contentRoot + entry.u;
        const title = document.createElement("span");
        title.textContent = entry.t;
        const meta = document.createElement("small");
        meta.textContent = entry.k === "api" ? `API · ${entry.s}` : entry.s;
        link.append(title, meta);
        item.appendChild(link);
        list.appendChild(item);
      });
      const current = list.querySelector('[aria-selected="true"]');
      if (current) {
        current.scrollIntoView({ block: "nearest" });
      }
    };

    const update = () => {
      const phrase = normalise(input.value);
      const terms = phrase.split(" ").filter(Boolean);
      selected = 0;
      if (!terms.length || !entries) {
        results = [];
        render();
        return;
      }
      results = entries
        .map((entry) => ({ entry, value: score(entry, terms, phrase) }))
        .filter((item) => item.value > 0)
        .sort((a, b) => b.value - a.value)
        .slice(0, 12)
        .map((item) => item.entry);
      render();
    };

    const open = () => {
      if (dialog.open) {
        return;
      }
      dialog.showModal();
      input.select();
      load().then(update);
    };

    document.querySelectorAll("[data-palette-open]").forEach((button) => button.addEventListener("click", open));
    document.addEventListener("keydown", (event) => {
      const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(event.target.tagName) || event.target.isContentEditable;
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        open();
      } else if (event.key === "/" && !typing && !dialog.open) {
        event.preventDefault();
        open();
      }
    });

    input.addEventListener("input", update);
    input.addEventListener("keydown", (event) => {
      const count = list.querySelectorAll('[role="option"]').length;
      if (event.key === "ArrowDown") {
        event.preventDefault();
        selected = Math.min(selected + 1, count - 1);
        render();
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        selected = Math.max(selected - 1, 0);
        render();
      } else if (event.key === "Enter") {
        const link = list.querySelector('[aria-selected="true"] a');
        if (link) {
          event.preventDefault();
          window.location.href = link.href;
          dialog.close();
        }
      }
    });
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) {
        dialog.close();
      }
    });
    list.addEventListener("click", (event) => {
      if (event.target.closest("a")) {
        dialog.close();
      }
    });
    render();
  }

  /* ------------------------------------------------ API index filter */

  function initApiIndex() {
    document.querySelectorAll("[data-api-index]").forEach((index) => {
      const input = index.querySelector("[data-api-filter]");
      const chips = Array.from(index.querySelectorAll(".mario-chip"));
      const rows = Array.from(index.querySelectorAll("tbody tr"));
      const count = index.querySelector("[data-api-count]");
      const empty = index.querySelector("[data-api-empty]");
      let category = "";

      const apply = () => {
        const terms = normalise(input.value).split(" ").filter(Boolean);
        let visible = 0;
        rows.forEach((row) => {
          const haystack = row.dataset.search || "";
          const match =
            (!category || row.dataset.category === category) && terms.every((term) => haystack.includes(term));
          row.hidden = !match;
          visible += match ? 1 : 0;
        });
        count.textContent = `${visible} ${visible === 1 ? "method" : "methods"}`;
        empty.hidden = visible > 0;
      };

      chips.forEach((chip) =>
        chip.addEventListener("click", () => {
          category = chip.dataset.category;
          chips.forEach((other) => other.setAttribute("aria-pressed", other === chip ? "true" : "false"));
          apply();
        })
      );
      input.addEventListener("input", apply);
    });
  }

  /* ------------------------------------------------------------- start */

  function start() {
    initThemeToggle();
    initScrollContainers();
    initSwitch();
    initSnap();
    initTabMemory();
    initHeader();
    initHeaderMenus();
    initTabs();
    initMenu();
    initPagebar();
    initCopy();
    initContact();
    initPalette();
    initApiIndex();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();


/* Resources hero: a single disclosure for the Database explorer pages. */
(() => {
  const hoverPointer = window.matchMedia("(hover: hover) and (pointer: fine)");
  for (const menu of document.querySelectorAll("[data-tab-menu]")) {
    const button = menu.querySelector("[data-tab-toggle]");
    const panel = menu.querySelector(".mario-tab-panel");
    const links = Array.from(panel.querySelectorAll("a"));
    let pinned = false;
    let closeTimer;

    const setOpen = (open) => {
      window.clearTimeout(closeTimer);
      panel.hidden = !open;
      button.setAttribute("aria-expanded", String(open));
      if (!open) pinned = false;
    };
    button.addEventListener("click", () => {
      // Hover may already have opened the panel before pointer activation.
      // The first click keeps it open; a second explicit click closes it.
      const open = !pinned;
      setOpen(open);
      pinned = open;
    });
    menu.addEventListener("pointerenter", (event) => {
      if (hoverPointer.matches && event.pointerType === "mouse") setOpen(true);
    });
    menu.addEventListener("pointerleave", (event) => {
      if (event.pointerType !== "mouse") return;
      window.clearTimeout(closeTimer);
      closeTimer = window.setTimeout(() => {
        if (!pinned && !menu.contains(document.activeElement)) setOpen(false);
      }, 150);
    });
    menu.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
        button.focus();
      }
      if (event.target === button && ["ArrowDown", "ArrowUp"].includes(event.key)) {
        event.preventDefault();
        setOpen(true);
        (event.key === "ArrowDown" ? links[0] : links[links.length - 1])?.focus();
      }
    });
    menu.addEventListener("focusin", () => window.clearTimeout(closeTimer));
    menu.addEventListener("focusout", (event) => {
      // Safari can report a null destination before activating a clicked link.
      if (event.relatedTarget && !menu.contains(event.relatedTarget)) setOpen(false);
    });
    links.forEach((link) => link.addEventListener("click", () => {
      // Keep the target visible until native navigation has handled the click.
      window.setTimeout(() => setOpen(false), 0);
    }));
    document.addEventListener("click", (event) => {
      if (!menu.contains(event.target)) setOpen(false);
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") setOpen(false);
    });
  }
})();

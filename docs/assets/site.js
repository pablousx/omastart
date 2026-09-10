(() => {
  "use strict";
  const root = document.documentElement;
  const themeButton = document.querySelector("[data-theme-toggle]");
  function applyTheme(theme) {
    const forest = theme === "forest";
    root.dataset.theme = forest ? "forest" : "night";
    document.querySelector('meta[name="theme-color"]').content = forest
      ? "#272e29"
      : "#1a1b26";
    themeButton.querySelector("[data-theme-name]").textContent = forest
      ? "Everforest"
      : "Tokyo Night";
    themeButton.setAttribute(
      "aria-label",
      `Switch to ${forest ? "Tokyo Night" : "Everforest"} theme`,
    );
  }
  try {
    applyTheme(localStorage.getItem("omastart-theme"));
  } catch {
    applyTheme("night");
  }
  themeButton.hidden = false;
  themeButton.addEventListener("click", () => {
    applyTheme(root.dataset.theme === "night" ? "forest" : "night");
    try {
      localStorage.setItem("omastart-theme", root.dataset.theme);
    } catch {
      /* Optional preference. */
    }
  });

  const rows = [...document.querySelectorAll("[data-demo-row]")];
  if (rows.length) {
    const filters = [...document.querySelectorAll("[data-filter]")];
    const undo = document.querySelector("[data-undo]");
    const message = document.querySelector("[data-demo-message]");
    let filter = "all";
    let lastChange = null;
    function render() {
      const enabled = rows.filter(
        (row) => row.dataset.enabled === "true",
      ).length;
      document.querySelector("[data-enabled-count]").textContent = enabled;
      rows.forEach((row) => {
        const on = row.dataset.enabled === "true";
        row
          .querySelector('[role="switch"]')
          .setAttribute("aria-checked", String(on));
        row.hidden = filter !== "all" && on !== (filter === "enabled");
      });
      document.querySelector(".demo-empty").hidden = rows.some(
        (row) => !row.hidden,
      );
      filters.forEach((button) =>
        button.setAttribute(
          "aria-pressed",
          String(button.dataset.filter === filter),
        ),
      );
      undo.hidden = !lastChange;
    }
    rows.forEach((row) => {
      const button = row.querySelector("button");
      button.disabled = false;
      button.addEventListener("click", () => {
        lastChange = { row, enabled: row.dataset.enabled };
        row.dataset.enabled = String(row.dataset.enabled !== "true");
        message.textContent = `${row.querySelector("strong").textContent} ${row.dataset.enabled === "true" ? "enabled" : "disabled"} in demo.`;
        render();
        // A filtered row can disappear; keep keyboard focus in a visible control.
        if (row.hidden) undo.focus({ preventScroll: true });
      });
    });
    filters.forEach((button) => {
      button.disabled = false;
      button.addEventListener("click", () => {
        filter = button.dataset.filter;
        render();
        const visible = rows.filter((row) => !row.hidden).length;
        message.textContent = `${visible} ${visible === 1 ? "app" : "apps"} in this demo view.`;
      });
    });
    undo.addEventListener("click", () => {
      if (!lastChange) return;
      const row = lastChange.row;
      row.dataset.enabled = lastChange.enabled;
      lastChange = null;
      message.textContent = "Last demo change undone.";
      render();
      (row.hidden
        ? filters.find((button) => button.dataset.filter === filter)
        : row.querySelector("button")
      ).focus({ preventScroll: true });
    });
    render();
  }

  const copy = document.querySelector("[data-copy]");
  if (copy && navigator.clipboard && window.isSecureContext) {
    copy.hidden = false;
    copy.addEventListener("click", async () => {
      const status = document.querySelector("[data-copy-status]");
      try {
        await navigator.clipboard.writeText(
          document.querySelector("#install-command").textContent,
        );
        status.textContent = "Installation command copied.";
      } catch {
        status.textContent =
          "Copy unavailable. Select the command above to copy it manually.";
      }
    });
  }
})();

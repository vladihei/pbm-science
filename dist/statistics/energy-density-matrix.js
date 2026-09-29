(() => {
  const panel = document.querySelector("#energy-density");
  const headings = panel?.querySelector(".fluence-bin-head");
  const models = panel?.querySelector(".fluence-models");
  if (!panel || !headings || !models) return;

  const binLabels = Array.from(headings.querySelectorAll("span"), (node) => node.textContent.trim());
  const rows = Array.from(models.querySelectorAll(":scope > .fluence-model"));
  if (binLabels.length !== 6 || rows.length === 0) return;

  const matrix = document.createElement("div");
  matrix.className = "fluence-matrix";
  matrix.setAttribute("role", "table");
  matrix.setAttribute("aria-label", "Energy-density distribution by study model, in joules per square centimetre");
  panel.insertBefore(matrix, headings);
  matrix.append(headings, models);

  headings.classList.add("fluence-matrix-head");
  headings.setAttribute("role", "row");
  const modelHeading = document.createElement("span");
  modelHeading.className = "fluence-model-heading";
  modelHeading.textContent = "Study model / summary";
  modelHeading.setAttribute("role", "columnheader");
  headings.prepend(modelHeading);
  headings.querySelectorAll("span:not(.fluence-model-heading)").forEach((node) => {
    node.setAttribute("role", "columnheader");
  });

  models.setAttribute("role", "rowgroup");
  rows.forEach((row) => {
    const name = row.querySelector(".fluence-model-name h4")?.textContent.trim() ?? "Study model";
    const sampleSize = row.querySelector(".fluence-model-name span")?.textContent.trim() ?? "";
    const stats = Array.from(row.querySelectorAll(".fluence-stats > div"), (stat) => ({
      label: stat.querySelector("small")?.textContent.trim() ?? "",
      value: stat.querySelector("strong")?.textContent.trim() ?? "",
    }));
    const cells = Array.from(row.querySelectorAll(".fluence-grid > .fluence-cell"));

    const label = document.createElement("div");
    label.className = "fluence-model-label";
    label.setAttribute("role", "rowheader");

    const title = document.createElement("h4");
    title.textContent = name;
    const n = document.createElement("span");
    n.textContent = sampleSize;
    const summary = document.createElement("div");
    summary.className = "fluence-model-summary";

    const primaryStats = stats.slice(0, 2).map((stat) => `${stat.label} ${stat.value}`).join(" · ");
    const spread = stats[2] ? `${stats[2].label}: ${stats[2].value}` : "";
    [primaryStats, spread].filter(Boolean).forEach((value) => {
      const line = document.createElement("span");
      line.textContent = value;
      summary.append(line);
    });
    label.append(title, n, summary);

    row.replaceChildren(label);
    row.classList.add("fluence-matrix-row");
    row.setAttribute("role", "row");
    row.setAttribute("aria-label", `${name}, ${sampleSize}`);

    cells.forEach((oldCell, index) => {
      const count = oldCell.querySelector("strong")?.textContent.trim() ?? "";
      const percent = oldCell.querySelector("small")?.textContent.trim() ?? "";
      const share = Number.parseFloat(percent) || 0;
      const cell = document.createElement("div");
      cell.className = `fluence-cell fluence-matrix-cell ${Array.from(oldCell.classList).find((className) => className.startsWith("bin-")) ?? ""}`.trim();
      cell.setAttribute("role", "cell");
      cell.setAttribute("aria-label", oldCell.getAttribute("aria-label") ?? `${name}, ${binLabels[index]}: ${count} records, ${percent}`);
      cell.style.setProperty("--heat", `${Math.round(18 + (Math.min(share, 45) / 45) * 65)}%`);

      const bin = document.createElement("span");
      bin.className = "fluence-cell-label";
      bin.textContent = binLabels[index];
      const percentage = document.createElement("strong");
      percentage.textContent = percent;
      const records = document.createElement("small");
      records.textContent = `${count} records`;
      cell.append(bin, percentage, records);
      row.append(cell);
    });
  });

  const note = panel.querySelector(".fluence-note");
  if (note) note.append(" Darker cells indicate a larger share within that study-model group.");
})();

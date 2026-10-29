export const fmt = (x, digits = 3) =>
  Number.isFinite(x)
    ? x.toLocaleString("ru-RU", { maximumFractionDigits: digits })
    : "—";
export const escapeHTML = (x) =>
  String(x ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
export const statusLabel = {
  pass: "Выполнено",
  fail: "Не выполнено",
  pending: "Требует уточнения",
};

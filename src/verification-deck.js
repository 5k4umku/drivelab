const filters = [
  ["all", "Все"],
  ["pass", "Выполнено"],
  ["pending", "Уточнить"],
  ["fail", "Отказы"],
];
const lists = ["#checks-list", "#assembly-checks"];
const selections = new Map();

export function updateVerificationDecks() {
  for (const selector of lists) {
    const list = document.querySelector(selector);
    if (list) renderVerificationDeck(list);
  }
}

function renderVerificationDeck(list) {
  let deck = list.querySelector(":scope > .verification-deck");
  const checks = [...list.querySelectorAll(":scope > .check")];
  if (!checks.length) {
    deck?.remove();
    return;
  }
  if (!deck) {
    deck = document.createElement("div");
    deck.className = "verification-deck";
    deck.innerHTML = `
      <div class="verification-bar" aria-hidden="true">
        <span data-status="pass"></span><span data-status="pending"></span><span data-status="fail"></span>
      </div>
      <div class="verification-filters" role="group" aria-label="Фильтр проверок">
        ${filters.map(([key, name]) => `<button type="button" data-filter="${key}"><span>${name}</span> <strong></strong></button>`).join("")}
      </div>
      <p class="verification-empty" hidden>В этой группе проверок нет.</p>
    `;
    list.prepend(deck);
  }
  const categories = checks.map(check => {
    const mark = check.querySelector(".check-symbol");
    if (mark?.classList.contains("pass")) return "pass";
    if (mark?.classList.contains("fail")) return "fail";
    return "pending";
  });
  const summary = { all: checks.length, pass: 0, pending: 0, fail: 0 };
  for (const category of categories) summary[category]++;
  const buttons = [...deck.querySelectorAll("button")];
  const empty = deck.querySelector(".verification-empty");

  function show(key) {
    selections.set(list.id, key);
    buttons.forEach(button => button.setAttribute("aria-pressed", String(button.dataset.filter === key)));
    checks.forEach((check, index) => {
      check.hidden = key !== "all" && key !== categories[index];
    });
    empty.hidden = summary[key] !== 0;
  }

  for (const button of buttons) {
    const key = button.dataset.filter;
    button.querySelector("strong").textContent = summary[key];
    button.onclick = () => show(key);
  }
  for (const segment of deck.querySelectorAll("[data-status]")) {
    const count = summary[segment.dataset.status];
    segment.style.flexGrow = count;
    segment.hidden = count === 0;
  }
  if (list.id === "checks-list") {
    const previous = document.querySelector("#checks-unresolved");
    if (previous) previous.checked = false;
  }
  show(selections.get(list.id) || "all");
}

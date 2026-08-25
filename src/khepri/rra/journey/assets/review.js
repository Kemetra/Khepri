import { api, deleteContent, language, resume, routeFor } from "/beta/assets/common.js";

const table = document.querySelector("#mapping-table tbody");
const confirm = document.querySelector("#confirm-mapping");
const error = document.querySelector("#error-summary");
const findings = document.querySelector("#profile-findings");
const vocabulary = document.querySelector("#value-vocabulary");
const cell = (value) => { const item = document.createElement("td"); item.textContent = value ?? "—"; return item; };
// A governed code is never printed at a customer: the server owns both languages of
// its wording and hands them over as data attributes. An unknown code falls back to
// itself rather than to invented text, so a semantic added without wording is visible
// as a machine identifier instead of being silently renamed or rendered "undefined".
const wordFor = (kind, code) => (code == null ? null : vocabulary?.getAttribute(`data-${kind}-${code.replaceAll("_", "-")}`) ?? code);

const load = async () => {
  const state = await resume();
  if (!state || state.step !== "review") return;
  const profile = await api("/api/v1/beta/profile");
  for (const mapping of profile.mappings) {
    const row = document.createElement("tr");
    const candidate = mapping.candidates[0];
    row.append(cell(candidate?.safe_label), cell(wordFor("semantic", mapping.semantic)), cell(wordFor("state", mapping.state)), cell(candidate?.evidence?.join(" · ")));
    table.append(row);
  }
  if (!profile.admissible) {
    const codes = [...new Set([...profile.reasons, ...profile.findings])];
    const list = document.createElement("ul");
    for (const code of codes) {
      const item = document.createElement("li");
      item.textContent = findings.getAttribute(`data-${code.replaceAll("_", "-")}`) ?? findings.dataset.generic;
      list.append(item);
    }
    findings.append(document.createTextNode(findings.dataset.title), list);
    findings.hidden = false;
  }
  confirm.disabled = !(profile.admissible && profile.mappings.filter((item) => item.requirement === "required").every((item) => item.state === "mapped"));
};

confirm.addEventListener("click", async () => {
  confirm.disabled = true;
  try {
    await api("/api/v1/beta/facts", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    await api("/api/v1/beta/reports", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    location.assign(routeFor("processing"));
  } catch (failure) {
    error.textContent = language === "ar" ? "تعذر بدء التحليل." : "Analysis could not be started.";
    error.hidden = false; error.focus();
  }
});
document.querySelector("#restart").addEventListener("click", deleteContent);
load().catch(() => { error.textContent = language === "ar" ? "بيانات المراجعة غير متاحة." : "Review data is unavailable."; error.hidden = false; });

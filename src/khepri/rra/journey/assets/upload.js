import { api, deleteContent, language, resume, routeFor } from "/beta/assets/common.js";

const MAX_BYTES = 50 * 1024 * 1024;
const CONSENT_VERSION = "rra001.beta-consent.v1";

// `RRA-003` will not let admission infer what a column means, so every profile
// carries an explicit source contract. The journey declares the shape its own
// upload step already guarantees -- one currency, posted sales, a receipt
// number per line -- and nothing here is read off the file's headers.
//
// This is the journey's *default* declaration, not a collection surface. An
// operator whose extract differs cannot yet say so from the browser; that
// surface is the remaining half of this slice and is tracked with it.
const SOURCE_CONTRACT = {
  contract_id: "rra003.journey-default.v1",
  evidence: "beta journey default declaration",
  event_kind_column: null,
  sale_only: true,
  status_column: null,
  posted_only: true,
  currency_column: null,
  currency_code: "EGP",
  event_key_columns: [],
  unique_line_grain_attested: true,
  transaction_id_column: "invoice_no",
  transaction_key_components: [],
  transaction_id_unique_package_wide: true,
  revenue_vat_exclusive: true,
  revenue_is_net_of_returns: false,
  units_are_integral: true,
  cost_is_extended: true,
  discount_is_additive: true,
};

const profileBody = () => JSON.stringify({ requested_semantics: [], source_contract: SOURCE_CONTRACT });
const form = document.querySelector("#upload-form");
const consent = document.querySelector("#consent");
const input = document.querySelector("#sales-file");
const button = document.querySelector("#start-assessment");
const selected = document.querySelector("#selected-file");
const errorSummary = document.querySelector("#error-summary");
const dropZone = document.querySelector("#drop-zone");
const recovery = document.querySelector("#upload-recovery");
let file = null;
let uploaded = false;

const message = (text) => {
  errorSummary.textContent = text;
  errorSummary.hidden = false;
  errorSummary.focus();
};
const valid = (candidate) => {
  const extension = candidate.name.toLowerCase().split(".").pop();
  return ["csv", "xlsx"].includes(extension) && candidate.size > 0 && candidate.size <= MAX_BYTES;
};
const update = () => {
  input.disabled = !consent.checked;
  button.disabled = !(consent.checked && file);
};
const choose = (candidate) => {
  if (!valid(candidate)) {
    file = null;
    message(language === "ar" ? "اختر ملف CSV أو XLSX لا يتجاوز 50 ميجابايت." : "Choose a CSV or XLSX file no larger than 50 MB.");
  } else {
    file = candidate;
    selected.textContent = candidate.name;
    errorSummary.hidden = true;
  }
  update();
};

consent.addEventListener("change", update);
input.addEventListener("change", () => input.files?.[0] && choose(input.files[0]));
["dragenter", "dragover"].forEach((name) => dropZone.addEventListener(name, (event) => { event.preventDefault(); if (!input.disabled) dropZone.classList.add("is-dragging"); }));
["dragleave", "drop"].forEach((name) => dropZone.addEventListener(name, (event) => { event.preventDefault(); dropZone.classList.remove("is-dragging"); }));
dropZone.addEventListener("drop", (event) => { if (!input.disabled && event.dataTransfer?.files[0]) choose(event.dataTransfer.files[0]); });

const upload = () => new Promise((resolve, reject) => {
  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/v1/beta/uploads");
  xhr.withCredentials = true;
  xhr.upload.addEventListener("progress", (event) => {
    if (!event.lengthComputable) return;
    const percent = Math.round((event.loaded / event.total) * 100);
    const bar = document.querySelector("[role=progressbar]");
    document.querySelector("#upload-progress").hidden = false;
    bar.setAttribute("aria-valuenow", String(percent));
    bar.querySelector("span").style.inlineSize = `${percent}%`;
  });
  xhr.addEventListener("load", () => xhr.status === 201 ? resolve() : reject(new Error(String(xhr.status))));
  xhr.addEventListener("error", reject);
  xhr.send(file);
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  button.disabled = true;
  try {
    await api("/api/v1/beta/consent", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ consent_version: CONSENT_VERSION }) });
    await upload();
    uploaded = true;
    await api("/api/v1/beta/profile", { method: "POST", headers: { "Content-Type": "application/json" }, body: profileBody() });
    location.assign(routeFor("review"));
  } catch (error) {
    message(uploaded ? errorSummary.dataset.profileRejected : (language === "ar" ? "تعذر إكمال الرفع الآمن. حاول مرة أخرى." : "The secure upload could not be completed. Try again."));
    recovery.hidden = !uploaded;
    update();
  }
});

const bootstrap = async () => {
  const invitation = new URLSearchParams(location.hash.slice(1)).get("invite");
  if (location.hash) history.replaceState(null, "", location.pathname + location.search);
  try {
    if (invitation) await api("/api/v1/beta/sessions/redeem", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token: invitation }) });
    const state = await resume();
    if (state?.upload_present && !state.profile_present) {
      uploaded = true;
      await api("/api/v1/beta/profile", { method: "POST", headers: { "Content-Type": "application/json" }, body: profileBody() });
      location.replace(routeFor("review"));
    }
  } catch (error) {
    message(uploaded ? errorSummary.dataset.profileRejected : (error.status === 401 ? errorSummary.dataset.invitation : errorSummary.dataset.temporary));
    recovery.hidden = !uploaded;
  }
};
recovery.addEventListener("click", deleteContent);
update();
bootstrap();

import { api, deleteContent, language, resume, routeFor } from "/beta/assets/common.js";

const MAX_BYTES = 50 * 1024 * 1024;
const CONSENT_VERSION = "rra001.beta-consent.v1";
const form = document.querySelector("#upload-form");
const consent = document.querySelector("#consent");
const input = document.querySelector("#sales-file");
const button = document.querySelector("#start-assessment");
const selected = document.querySelector("#selected-file");
const errorSummary = document.querySelector("#error-summary");
const dropZone = document.querySelector("#drop-zone");
const recovery = document.querySelector("#upload-recovery");
const contractFields = document.querySelectorAll("[data-contract-field]");
let file = null;
let uploaded = false;

// Read out of the operator's own controls, never composed here. `RRA-003` refuses
// to establish event kind, status, currency, basis, or identity from the data, and
// a declaration this file invented would be indistinguishable at the server from
// one the operator chose -- which is the same inference wearing a client's clothes.
//
// A blank optional column is sent as null, because the server reads null as "not
// declared by column" while "" would name a column called "". The two required
// identifiers are sent as the empty string instead: they are typed `str`, so null
// is a *schema* violation and answers 422 -- the very failure this fixes -- while
// "" reaches `build_source_contract` and earns the 400 that states what is
// missing. `data-contract-required` marks which those are, so the distinction
// lives on the control it describes rather than as a list here.
const declaration = () => {
  const contract = {};
  for (const control of contractFields) {
    const name = control.dataset.contractField;
    const blank = control.dataset.contractRequired === undefined ? null : "";
    contract[name] = control.type === "checkbox" ? control.checked : (control.value.trim() || blank);
  }
  return contract;
};
const profileRequest = () => JSON.stringify({ requested_semantics: [], source_contract: declaration() });
// The stated reason when the server gives one, and the page's own wording when it
// does not. A governed refusal names what it refused, and flattening that into a
// generic message is what leaves an operator with nothing to act on.
const refusalText = (error) => error?.detail || errorSummary.dataset.profileRejected;

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
    await api("/api/v1/beta/profile", { method: "POST", headers: { "Content-Type": "application/json" }, body: profileRequest() });
    location.assign(routeFor("review"));
  } catch (error) {
    message(uploaded ? refusalText(error) : (language === "ar" ? "تعذر إكمال الرفع الآمن. حاول مرة أخرى." : "The secure upload could not be completed. Try again."));
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
      // The upload landed but its profile response was lost, so the file is here
      // and the profile is not. This posts the declaration as it stands on the
      // page: nothing is stored in the browser, so on a fresh load the form is
      // blank and the declaration is incomplete.
      //
      // That is handled, not ignored. A blank `contract_id` makes
      // `to_contract()` raise `ContractRefused`, and the route answers 400 with
      // a stated reason rather than the 422 a missing contract earned -- "400
      // rather than 422, and the distinction is the point". `refusalText` then
      // shows the operator that reason. Synthesizing a contract here to finish
      // the request unattended is the one thing `RRA-003` forbids, so the
      // refusal is the correct outcome and the operator declares and resubmits.
      await api("/api/v1/beta/profile", { method: "POST", headers: { "Content-Type": "application/json" }, body: profileRequest() });
      location.replace(routeFor("review"));
    }
  } catch (error) {
    message(uploaded ? refusalText(error) : (error.status === 401 ? errorSummary.dataset.invitation : errorSummary.dataset.temporary));
    recovery.hidden = !uploaded;
  }
};
recovery.addEventListener("click", deleteContent);
update();
bootstrap();

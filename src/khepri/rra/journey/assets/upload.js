import { api, language, resume, routeFor } from "/beta/assets/common.js";

const MAX_BYTES = 50 * 1024 * 1024;
const CONSENT_VERSION = "rra001.beta-consent.v1";
const form = document.querySelector("#upload-form");
const consent = document.querySelector("#consent");
const input = document.querySelector("#sales-file");
const button = document.querySelector("#start-assessment");
const selected = document.querySelector("#selected-file");
const errorSummary = document.querySelector("#error-summary");
const dropZone = document.querySelector("#drop-zone");
let file = null;

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
    await api("/api/v1/beta/profile", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ requested_semantics: [] }) });
    location.assign(routeFor("review"));
  } catch (error) {
    message(language === "ar" ? "تعذر إكمال الرفع الآمن. حاول مرة أخرى." : "The secure upload could not be completed. Try again.");
    update();
  }
});

const bootstrap = async () => {
  const invitation = new URLSearchParams(location.hash.slice(1)).get("invite");
  if (location.hash) history.replaceState(null, "", location.pathname + location.search);
  try {
    if (invitation) await api("/api/v1/beta/sessions/redeem", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token: invitation }) });
    await resume();
  } catch (error) {
    message(language === "ar" ? "الدعوة غير متاحة." : "This invitation is unavailable.");
  }
};
update();
bootstrap();

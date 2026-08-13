import { api, deleteContent, resume } from "/beta/assets/common.js";

let delay = 1000;
let timer = null;
const poll = async () => {
  timer = null;
  if (document.hidden) return;
  let state;
  try {
    state = await resume();
  } catch (error) {
    document.querySelector("#processing-status").textContent = document.querySelector("#processing-status").dataset.temporary;
    delay = Math.min(delay * 2, 10000);
    timer = window.setTimeout(poll, delay);
    return;
  }
  if (!state || state.step !== "processing") return;
  if (!state.job_id && state.package_present) {
    try {
      await api("/api/v1/beta/reports", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    } catch (error) {
      delay = Math.min(delay * 2, 10000);
      timer = window.setTimeout(poll, delay);
      return;
    }
  }
  if (state.job_state === "dead_lettered") {
    document.querySelector(".indeterminate").hidden = true;
    document.querySelector("#processing-status").textContent = document.querySelector("#processing-status").dataset.failed;
    document.querySelector("#processing-recovery").hidden = false;
    return;
  }
  document.querySelector("#processing-status").textContent = document.querySelector("#processing-status").dataset.preparing;
  delay = Math.min(delay * 2, 10000);
  timer = window.setTimeout(poll, delay);
};
document.addEventListener("visibilitychange", () => { if (!document.hidden && !timer) poll(); });
document.querySelector("#processing-recovery").addEventListener("click", deleteContent);
poll();

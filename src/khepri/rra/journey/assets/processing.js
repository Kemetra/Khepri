import { language, resume } from "/beta/assets/common.js";

let delay = 1000;
let timer = null;
const poll = async () => {
  timer = null;
  if (document.hidden) return;
  const state = await resume();
  if (!state || state.step !== "processing" || state.job_state === "dead_lettered") return;
  document.querySelector("#processing-status").textContent = language === "ar" ? "يتم إعداد التقرير الآمن." : "The secure report is being prepared.";
  delay = Math.min(delay * 2, 10000);
  timer = window.setTimeout(poll, delay);
};
document.addEventListener("visibilitychange", () => { if (!document.hidden && !timer) poll(); });
poll();

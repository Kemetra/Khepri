import { deleteContent, language, resume } from "/beta/assets/common.js";

const links = [
  ["English web report", "surfaces/web/en", "en"], ["التقرير العربي", "surfaces/web/ar", "ar"],
  ["English evidence", "surfaces/evidence/en", "en"], ["الأدلة الفنية", "surfaces/evidence/ar", "ar"],
  ["English PDF", "surfaces/pdf/en", "en"], ["PDF عربي", "surfaces/pdf/ar", "ar"],
  ["Bilingual Excel", "surfaces/excel", "en"],
];
const load = async () => {
  const state = await resume();
  if (!state || !state.bundle_complete) return;
  document.querySelector("#row-count").textContent = new Intl.NumberFormat(language).format(state.row_count);
  document.querySelector("#generated-at").textContent = new Intl.DateTimeFormat(language, { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", timeZoneName: "short" }).format(new Date(state.generated_at));
  const holder = document.querySelector("#report-links");
  for (const [label, path, direction] of links) {
    const link = document.createElement("a"); link.className = "report-card"; link.textContent = label; link.dir = direction === "ar" ? "rtl" : "ltr"; link.href = `/api/v1/beta/reports/${state.job_id}/${path}`; holder.append(link);
  }
  holder.hidden = false;
};
document.querySelector("#delete-content").addEventListener("click", deleteContent);
load();

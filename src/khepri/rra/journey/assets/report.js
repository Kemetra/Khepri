import { deleteContent, language, resume } from "/beta/assets/common.js";

// The timezone is part of the value, not decoration: the deadline it carries is
// when this session's content is deleted, and a reader near expiry has to be able
// to tell how long is actually left.
const moment = (value) => new Intl.DateTimeFormat(language, { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", timeZoneName: "short" }).format(new Date(value));

const load = async () => {
  const state = await resume();
  if (!state || !state.bundle_complete) return;
  document.querySelector("#row-count").textContent = new Intl.NumberFormat(language).format(state.row_count);
  document.querySelector("#generated-at").textContent = moment(state.generated_at);
  // The governed deletion deadline, not seven days from generation. A report
  // opened late in the session may have hours left, and the footer's general
  // promise cannot say so.
  document.querySelector("#expires-at").textContent = moment(state.content_expires_at);
  const holder = document.querySelector("#report-links");
  const links = [
    [holder.dataset.webEn, "surfaces/web/en", language], [holder.dataset.webAr, "surfaces/web/ar", language],
    [holder.dataset.evidenceEn, "surfaces/evidence/en", language], [holder.dataset.evidenceAr, "surfaces/evidence/ar", language],
    [holder.dataset.pdfEn, "surfaces/pdf/en", language], [holder.dataset.pdfAr, "surfaces/pdf/ar", language],
    [holder.dataset.excel, "surfaces/excel", language],
  ];
  for (const [label, path, direction] of links) {
    const link = document.createElement("a"); link.className = "report-card"; link.textContent = label; link.dir = direction === "ar" ? "rtl" : "ltr"; link.href = `/api/v1/beta/reports/${state.job_id}/${path}`; holder.append(link);
  }
  holder.hidden = false;
};
document.querySelector("#delete-content").addEventListener("click", deleteContent);
load().catch(() => {
  const error = document.querySelector("#error-summary");
  error.textContent = error.dataset.temporary;
  error.hidden = false;
});

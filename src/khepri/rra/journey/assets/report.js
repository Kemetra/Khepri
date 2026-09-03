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
  // Pages to open and files to download, each link naming its group, so a surface
  // added later cannot land ungrouped. The web report in this page's language leads
  // the pages: it opens with the analysis-quality summary, and is where to look
  // before downloading anything.
  const web = [
    [holder.dataset.webEn, "surfaces/web/en", language, "open"], [holder.dataset.webAr, "surfaces/web/ar", language, "open"],
  ];
  if (language === "ar") web.reverse();
  const links = [
    ...web,
    [holder.dataset.evidenceEn, "surfaces/evidence/en", language, "open"], [holder.dataset.evidenceAr, "surfaces/evidence/ar", language, "open"],
    [holder.dataset.pdfEn, "surfaces/pdf/en", language, "download"], [holder.dataset.pdfAr, "surfaces/pdf/ar", language, "download"],
    [holder.dataset.excel, "surfaces/excel", language, "download"],
  ];
  for (const [label, path, direction, group] of links) {
    const link = document.createElement("a"); link.className = "report-card"; link.textContent = label; link.dir = direction === "ar" ? "rtl" : "ltr"; link.href = `/api/v1/beta/reports/${state.job_id}/${path}`;
    holder.querySelector(`[data-group="${group}"]`).append(link);
  }
  holder.querySelector('[data-group="open"] .report-card').classList.add("report-card--primary");
  holder.hidden = false;
};
document.querySelector("#delete-content").addEventListener("click", deleteContent);
load().catch(() => {
  const error = document.querySelector("#error-summary");
  error.textContent = error.dataset.temporary;
  error.hidden = false;
});

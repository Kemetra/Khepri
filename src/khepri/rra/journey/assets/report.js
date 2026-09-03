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
  // The report and its evidence, then the other formats, each link naming its group
  // so a surface added later cannot land ungrouped. The web report in this page's
  // language leads: it begins with the analysis-quality summary and is where to look
  // first. Every surface is served as an attachment, so the groups name content, not
  // mechanism.
  const web = [
    [holder.dataset.webEn, "surfaces/web/en", language, "read"], [holder.dataset.webAr, "surfaces/web/ar", language, "read"],
  ];
  if (language === "ar") web.reverse();
  const links = [
    ...web,
    [holder.dataset.evidenceEn, "surfaces/evidence/en", language, "read"], [holder.dataset.evidenceAr, "surfaces/evidence/ar", language, "read"],
    [holder.dataset.pdfEn, "surfaces/pdf/en", language, "formats"], [holder.dataset.pdfAr, "surfaces/pdf/ar", language, "formats"],
    [holder.dataset.excel, "surfaces/excel", language, "formats"],
  ];
  for (const [label, path, direction, group] of links) {
    const link = document.createElement("a"); link.className = "report-card"; link.textContent = label; link.dir = direction === "ar" ? "rtl" : "ltr"; link.href = `/api/v1/beta/reports/${state.job_id}/${path}`;
    holder.querySelector(`[data-group="${group}"]`).append(link);
  }
  holder.querySelector('[data-group="read"] .report-card').classList.add("report-card--primary");
  holder.hidden = false;
};
document.querySelector("#delete-content").addEventListener("click", deleteContent);
load().catch(() => {
  const error = document.querySelector("#error-summary");
  error.textContent = error.dataset.temporary;
  error.hidden = false;
});

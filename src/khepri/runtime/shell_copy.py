"""Bilingual copy for the commercial shell (`R8-02`).

Separate from `khepri.rra.journey.copy` rather than an extension of it. The shell is `RCA`'s and
the journey is `RRA`'s, and `RCA-002` excludes any change to the beta journey's templates or
assets. Sharing one dictionary would make a shell key an `RRA` change.

**Parity is asserted at import, not left to a test.** `RCA-002` `FR-054` requires equivalent state,
actions, and error text in both languages. A key present in one language and missing in the other
raises `StrictUndefined` at render time -- in whichever language happens to be requested -- which
is a defect discovered by a visitor rather than by the build.

**No cause is named in the unavailable copy.** `FR-050` collapses five states into this surface and
`FR-052` forbids disclosing which one occurred, so the text says what the reader can do next and
nothing about what went wrong.
"""

from __future__ import annotations

_EN = {
    "product": "Khepri",
    "skip": "Skip to main content",
    "unavailable_title": "This page is unavailable",
    "unavailable_intro": (
        "We cannot show this page. Check the address, or return to your organization's home page."
    ),
    "no_membership_title": "You are not in an organization yet",
    "no_membership_intro": (
        "Your account is active, but it does not belong to an organization."
    ),
    "no_membership_action": "Ask an organization owner to invite you.",
    "switcher_title": "Choose an organization",
    "switcher_intro": "You belong to these organizations.",
    "team_title": "Team",
    "team_intro": "People in this organization.",
    "team_empty": "No one else is in this organization yet.",
    "member_disabled": "Account disabled",
    "role_owner": "Owner",
    "role_member": "Member",
    "invitations_title": "Pending invitations",
    "invitations_empty": "There are no pending invitations.",
    "invitation_revoke": "Withdraw",
    "invite_title": "Invite someone",
    "invite_intro": (
        "They receive a link that stays usable for seven days. Only owners can invite."
    ),
    "invite_email_label": "Email address",
    "invite_role_label": "Role in this organization",
    "invite_submit": "Create invitation",
    "invitation_issued_title": "Invitation created",
    "invitation_issued_intro": "Send this link to the person you invited.",
    "invitation_token_once": (
        "This is shown once. We cannot show it again, so copy it before you leave this page."
    ),
    "back_to_team": "Back to the team",
    "new_analysis": "Start a new analysis",
    # The persistent frame. `frame_home_label` is the brand's *purpose*, composed after the visible
    # wordmark rather than replacing it. An `aria-label` would have replaced it, and on the Arabic
    # shell that left an accessible name with no `KHEPRI` in it while `KHEPRI` was what the reader
    # could see -- so a speech-input reader saying what is on the control could not operate it
    # (WCAG 2.5.3, "Label in Name"). The wordmark is still a picture of a name, so the words are
    # still needed; they are added to it now instead of standing in for it.
    "frame_home_label": "home page",
    "frame_organization_label": "Change organization",
    # The control names the language it goes to, in that language, so a reader who cannot read the
    # current one can still find it. `lang` is set on the element for pronunciation.
    "frame_language": "العربية",
    "frame_language_code": "ar",
    # One wording for every collapsed refusal. `FR-050` forbids distinguishing the causes "by copy,
    # status code, page identity, or navigation state", and an exit is navigation state -- so this
    # string, its target, and its presence are identical on `unavailable` and on the journey's
    # `expired`, whichever cause brought the reader there.
    "recovery_exit": "Go to your organizations",
    # `W1-05`. The frame's destination landmark, named for what it is now that it holds more than
    # `Team`. The surface titles double as navigation labels: design language §3.5 settles the set
    # as Overview · Data · Analyses · Team, and `DatasetVersion` never appears on screen (§7.2).
    "frame_surfaces_label": "Sections",
    "overview_title": "Overview",
    "overview_intro": "What happened most recently, and what to do next.",
    "latest_work_title": "Latest work",
    "overview_no_work": "No analysis has run yet.",
    "overview_no_data": "No data has been submitted yet.",
    "processing_title": "Still running",
    "attention_title": "Needs attention",
    "attention_run_failed": "An analysis did not complete.",
    # `KHEPRI-DEC-033` §5: no claim that content expires on its own, because nothing yet makes it.
    "retention_notice": "Content is kept while this organization exists.",
    "data_title": "Data",
    "data_intro": "What was submitted, whether it was admitted, and which analyses used it.",
    "data_empty": "Nothing has been submitted to this organization yet.",
    "data_submitted": "Submitted",
    "data_admitted": "Admitted",
    "data_awaiting": "Awaiting its first analysis",
    "data_analysis_started": "Analysis started",
    "data_in_use": "Used in analysis",
    "data_uses_title": "Analyses that used this data",
    "data_no_uses": "No analysis has used this data yet.",
    "retention_kept": "Kept",
    # The operational states a run can hold (`FR-117`'s vocabulary). Trust state is a second axis
    # and is `RRA-012`'s; it is not fused into these words.
    "run_state_started": "Processing",
    "run_state_completed": "Completed",
    "run_state_failed": "Did not complete",
    # The Analyses spine (`FR-117`). The report words are distinct strings on purpose -- none is a
    # substring of another -- so a test asserting one absent is not fooled by another present.
    "analyses_title": "Analyses",
    "analyses_intro": "Every analysis run for this organization, newest first.",
    "analyses_empty": "No analysis has run for this organization yet.",
    "spine_started": "Started",
    "spine_data_submitted": "Data submitted",
    "spine_data_deleted": "Data deleted, submitted",
    "report_available": "Report available",
    "report_not_yet": "Report not ready yet",
    "report_unavailable": "Report not produced",
    "report_unreachable": "Report can no longer be opened",
    # A deleted run stays on the spine as a tombstone (`KHEPRI-DEC-033` §1), minimal (§7.3).
    "retention_deleted": "Deleted",
    "tombstone_deleted": "Deleted",
    "tombstone_note": "This analysis was deleted. Its entry stays so the history does not shorten.",
    # `W1-06`. Analysis detail, its Passport (`FR-119`), its artifacts (`FR-118`), and the audit
    # disclosure (§10). The quality group words are the report's own (`RRA-012` component chrome)
    # and are not restated here.
    "analysis_title": "Analysis",
    "analysis_intro": "What this analysis covered, what it answered, and its report.",
    "passport_title": "Analysis passport",
    "passport_period": "Period covered",
    "passport_timezone": "Retail day boundary",
    "passport_data": "Data",
    "passport_data_link": "Submitted",
    "passport_scope": "Coverage",
    "passport_scope_unstated": "Not stated",
    "passport_rows": "Rows",
    "passport_ran": "Completed",
    "passport_started": "Started",
    "passport_methodology": "Methodology versions",
    "passport_unavailable": "The provenance for this analysis is not available.",
    "artifacts_title": "Report",
    "artifact_web": "Open report",
    "artifact_evidence": "Open evidence",
    "artifact_pdf": "Download PDF",
    "artifact_excel": "Download Excel",
    "artifacts_not_yet": "The report is not ready yet.",
    "artifacts_none": "No report was produced for this analysis.",
    "artifacts_unreachable": "The report for this analysis can no longer be opened.",
    "audit_title": "Audit detail",
    "audit_run": "Analysis identifier",
    "audit_version": "Data identifier",
    "audit_package": "Package digest",
    "audit_manifest": "Coverage manifest digest",
    "audit_upload": "Upload digest",
    "audit_artifacts": "Artifact digest",
}

_AR = {
    "product": "خِبري",
    "skip": "تخطَّ إلى المحتوى الرئيسي",
    "unavailable_title": "هذه الصفحة غير متاحة",
    "unavailable_intro": (
        "لا يمكننا عرض هذه الصفحة. تحقق من العنوان، أو عد إلى الصفحة الرئيسية لمؤسستك."
    ),
    "no_membership_title": "لست ضمن أي مؤسسة بعد",
    "no_membership_intro": "حسابك نشط، لكنه لا ينتمي إلى أي مؤسسة.",
    "no_membership_action": "اطلب من مالك المؤسسة دعوتك.",
    "switcher_title": "اختر مؤسسة",
    "switcher_intro": "أنت عضو في هذه المؤسسات.",
    "team_title": "الفريق",
    "team_intro": "الأشخاص في هذه المؤسسة.",
    "team_empty": "لا يوجد أحد آخر في هذه المؤسسة بعد.",
    "member_disabled": "الحساب معطَّل",
    "role_owner": "مالك",
    "role_member": "عضو",
    "invitations_title": "الدعوات المعلَّقة",
    "invitations_empty": "لا توجد دعوات معلَّقة.",
    "invitation_revoke": "سحب",
    "invite_title": "ادعُ شخصًا",
    "invite_intro": (
        "سيصل إليه رابط يظل صالحًا للاستخدام مدة سبعة أيام. المالكون وحدهم يمكنهم الدعوة."
    ),
    "invite_email_label": "عنوان البريد الإلكتروني",
    "invite_role_label": "الدور في هذه المؤسسة",
    "invite_submit": "إنشاء الدعوة",
    "invitation_issued_title": "تم إنشاء الدعوة",
    "invitation_issued_intro": "أرسل هذا الرابط إلى الشخص الذي دعوته.",
    "invitation_token_once": (
        "يظهر هذا مرة واحدة. لا يمكننا عرضه مرة أخرى، فانسخه قبل مغادرة هذه الصفحة."
    ),
    "back_to_team": "العودة إلى الفريق",
    "new_analysis": "ابدأ تحليلًا جديدًا",
    "frame_home_label": "الصفحة الرئيسية",
    "frame_organization_label": "تغيير المؤسسة",
    "frame_language": "English",
    "frame_language_code": "en",
    "recovery_exit": "الانتقال إلى مؤسساتك",
    "frame_surfaces_label": "الأقسام",
    "overview_title": "نظرة عامة",
    "overview_intro": "ما حدث مؤخرًا، وما الخطوة التالية.",
    "latest_work_title": "آخر الأعمال",
    "overview_no_work": "لم يُجرَ أي تحليل بعد.",
    "overview_no_data": "لم تُرسَل أي بيانات بعد.",
    "processing_title": "ما زال يعمل",
    "attention_title": "يحتاج إلى انتباه",
    "attention_run_failed": "لم يكتمل أحد التحليلات.",
    "retention_notice": "يُحتفظ بالمحتوى ما دامت هذه المؤسسة قائمة.",
    "data_title": "البيانات",
    "data_intro": "ما أُرسل، وهل قُبل، وأي التحليلات استخدمته.",
    "data_empty": "لم يُرسَل شيء إلى هذه المؤسسة بعد.",
    "data_submitted": "أُرسل",
    "data_admitted": "مقبول",
    "data_awaiting": "بانتظار أول تحليل",
    "data_analysis_started": "بدأ تحليلها",
    "data_in_use": "مستخدم في تحليل",
    "data_uses_title": "التحليلات التي استخدمت هذه البيانات",
    "data_no_uses": "لم يستخدم أي تحليل هذه البيانات بعد.",
    "retention_kept": "محفوظ",
    "run_state_started": "قيد المعالجة",
    "run_state_completed": "مكتمل",
    "run_state_failed": "لم يكتمل",
    "analyses_title": "التحليلات",
    "analyses_intro": "كل تحليل أُجري لهذه المؤسسة، الأحدث أولًا.",
    "analyses_empty": "لم يُجرَ أي تحليل لهذه المؤسسة بعد.",
    "spine_started": "بدأ",
    "spine_data_submitted": "أُرسلت البيانات",
    "spine_data_deleted": "بيانات محذوفة، أُرسلت",
    "report_available": "التقرير متاح",
    "report_not_yet": "التقرير غير جاهز بعد",
    "report_unavailable": "لم يُنتَج تقرير",
    "report_unreachable": "لم يعد بالإمكان فتح التقرير",
    "retention_deleted": "محذوف",
    "tombstone_deleted": "محذوف",
    "tombstone_note": "حُذف هذا التحليل. يبقى مدخله كي لا يقصر التاريخ.",
    # `W1-06`.
    "analysis_title": "التحليل",
    "analysis_intro": "ما شمله هذا التحليل، وما أجاب عنه، وتقريره.",
    "passport_title": "بطاقة التحليل",
    "passport_period": "الفترة المشمولة",
    "passport_timezone": "حدود يوم البيع",
    "passport_data": "البيانات",
    "passport_data_link": "أُرسلت",
    "passport_scope": "النطاق",
    "passport_scope_unstated": "غير محدد",
    "passport_rows": "الصفوف",
    "passport_ran": "اكتمل",
    "passport_started": "بدأ",
    "passport_methodology": "إصدارات المنهجية",
    "passport_unavailable": "مصدر هذا التحليل غير متاح.",
    "artifacts_title": "التقرير",
    "artifact_web": "افتح التقرير",
    "artifact_evidence": "افتح الأدلة",
    "artifact_pdf": "نزّل PDF",
    "artifact_excel": "نزّل Excel",
    "artifacts_not_yet": "التقرير غير جاهز بعد.",
    "artifacts_none": "لم يُنتَج تقرير لهذا التحليل.",
    "artifacts_unreachable": "لم يعد بالإمكان فتح تقرير هذا التحليل.",
    "audit_title": "تفاصيل التدقيق",
    "audit_run": "معرّف التحليل",
    "audit_version": "معرّف البيانات",
    "audit_package": "بصمة الحزمة",
    "audit_manifest": "بصمة بيان النطاق",
    "audit_upload": "بصمة الملف",
    "audit_artifacts": "بصمة المخرج",
}

if set(_EN) != set(_AR):  # pragma: no cover -- structural guard, not a branch under test
    missing = set(_EN).symmetric_difference(_AR)
    raise RuntimeError(f"SHELL_COPY is not at language parity: {sorted(missing)}")

SHELL_COPY = {"en": _EN, "ar": _AR}

#: Text direction per language, so a template never infers it from the language code.
DIRECTIONS = {"en": "ltr", "ar": "rtl"}

__all__ = ["DIRECTIONS", "SHELL_COPY"]

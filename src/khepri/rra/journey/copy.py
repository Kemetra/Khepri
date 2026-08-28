"""Closed bilingual copy for the private-beta journey."""

from __future__ import annotations

_EN = {
    "product": "Khepri Retail Revenue Assessment",
    "skip": "Skip to main content",
    "private_beta": "Private beta",
    "upload_title": "Upload your sales data",
    "upload_intro": "Start with one CSV or single-sheet Excel workbook. Maximum 50 MB.",
    "consent": "I agree to the private-beta data processing terms.",
    "choose_file": "Choose a file",
    "drop_file": "Drop a CSV or XLSX file here, or choose one",
    "start": "Start secure assessment",
    "retention": "Your session and report are deleted after 7 days. You can delete them sooner.",
    "review_title": "This is what we read",
    "review_intro": "Confirm the detected, content-minimized retail structure before analysis.",
    "confirm": "Looks right — analyse",
    "restart": "Upload a different file",
    "processing_title": "Working through your data",
    "processing_intro": "You may close this tab. Your secure session will resume here.",
    "report_title": "Retail Revenue Assessment",
    "report_intro": "Your complete bilingual report bundle is ready.",
    "language": "العربية",
    "delete": "Delete session content",
    "expired_title": "This secure session is unavailable",
    "expired_intro": "Ask your Khepri advisor for a new private-beta invitation.",
    "uploaded_dataset": "Uploaded dataset",
    "step_upload": "Upload",
    "step_review": "Review",
    "step_processing": "Analysing",
    "step_report": "Report",
    "accepted": "Accepted",
    "size_limit": "Size limit",
    "you_receive": "You receive",
    "outputs": "Arabic and English — web, PDF, Excel",
    "language_navigation": "Language",
    "journey_progress": "Assessment progress",
    "processing_progress": "Report generation in progress",
    "stage_upload_review": "Upload and review",
    "stage_confirmed_facts": "Confirmed facts",
    "stage_report_generation": "Report generation",
    "stage_complete_publication": "Complete publication",
    "processing_preparing": "The secure report is being prepared.",
    "processing_failed": (
        "The report could not be completed. Delete this session and request a "
        "new invitation."
    ),
    "column": "Column",
    "retail_meaning": "Retail meaning",
    "status": "Status",
    "evidence": "Evidence",
    "semantic_transaction_date": "Transaction date",
    "semantic_revenue": "Revenue",
    "semantic_units": "Units",
    "semantic_transaction_id": "Transaction reference",
    "semantic_product": "Product",
    "semantic_category": "Category",
    "semantic_store": "Store or branch",
    "semantic_channel": "Sales channel",
    "semantic_cost": "Cost",
    "semantic_discount": "Discount amount",
    "semantic_returns": "Returns amount",
    "state_mapped": "Matched",
    "state_ambiguous": "Not determined",
    "state_conflicting": "Not usable",
    "state_unavailable": "Not found",
    "review_blocked_title": "Analysis cannot start yet:",
    "reason_generic": "The dataset cannot be analysed safely in its current form.",
    "reason_no_data_rows": "The uploaded sheet has no data rows.",
    "reason_no_time_field": "No usable transaction date column was found.",
    "reason_no_core_measure": "No usable revenue or units column was found.",
    "reason_irreconcilable_types": "A required field contains incompatible value types.",
    "reason_ambiguous_mapping": "A required retail meaning could not be determined safely.",
    "reason_missing_semantic": "A requested retail field is missing.",
    "finding_duplicate_labels": "Two or more columns have the same safe label.",
    "finding_all_columns_empty": "All uploaded columns are empty.",
    "dataset": "Dataset",
    "rows": "Rows",
    "generated": "Generated",
    "available_until": "Available until",
    "artifact_web_en": "English web report",
    "artifact_web_ar": "Arabic web report",
    "artifact_evidence_en": "English evidence",
    "artifact_evidence_ar": "Arabic evidence",
    "artifact_pdf_en": "English PDF",
    "artifact_pdf_ar": "Arabic PDF",
    "artifact_excel": "Bilingual Excel",
    "deletion_requested_title": "Deletion requested",
    "deletion_requested_intro": (
        "Your content is unavailable and secure deletion will continue automatically."
    ),
    "upload_progress": "Upload progress",
    "invitation_unavailable": "This invitation is unavailable.",
    "temporary_unavailable": "The secure session is temporarily unavailable. Try again.",
    "profile_rejected": (
        "The file was uploaded but could not be profiled. Delete this session and "
        "request a new invitation."
    ),
    "manifest_legend": "Tell us what period this file covers",
    "manifest_intro": (
        "Optional. Without it we still report what your file shows, but we "
        "decline period comparisons and growth, because a file cannot prove "
        "which days it was meant to include. Leave it blank to skip."
    ),
    "manifest_attested_by": "Who is confirming this",
    "manifest_attested_by_hint": (
        "Your name and role, so the record shows who confirmed the period "
        "this file covers."
    ),
    "manifest_timezone": "Timezone your trading day is counted in",
    "manifest_timezone_hint": "For example Africa/Cairo.",
    "manifest_covered_start": "First day this file is meant to cover",
    "manifest_covered_end": "Last day this file is meant to cover",
    "manifest_aggregate_scope": "Name of the store or group this file covers",
    "manifest_covered_days": "Every day in that period, separated by commas",
    "manifest_covered_days_hint": (
        "Include each day from the first to the last, including any day that "
        "traded nothing."
    ),
    "manifest_event_kinds": "Kinds of row the file includes, separated by commas",
    "manifest_event_kinds_hint": "For example sale.",
    "manifest_statuses": "Statuses the file includes, separated by commas",
    "manifest_statuses_hint": "For example posted.",
    "manifest_closed_days": "Days you were closed, separated by commas",
    "manifest_closed_days_hint": (
        "Days that traded nothing because you were shut. These still count as "
        "covered — zero is the right answer for them."
    ),
    "manifest_extraction_gap_days": (
        "Days the file may be missing rows, separated by commas"
    ),
    "manifest_extraction_gap_days_hint": (
        "Days where the export may have dropped rows. We decline period "
        "comparisons and growth over any range that includes one, because we "
        "cannot tell how much is missing."
    ),
    "manifest_partial_terminal_boundary": (
        "A till was still open when this file was taken"
    ),
    "manifest_partial_terminal_boundary_hint": (
        "Tick this only if the export ran mid-shift. It sets aside period "
        "comparisons and growth for the whole file, not just the last day."
    ),
    "file_invalid": "Choose a CSV or XLSX file no larger than 50 MB.",
    "upload_failed": "The secure upload could not be completed. Try again.",
    "review_unavailable": "Review data is unavailable.",
    "analysis_unavailable": "Analysis could not be started.",
    "refusal_title": "This file was not accepted:",
    "refusal_stated": (
        "The assessment was refused on governed grounds. The stated reason is "
        "shown above."
    ),
    "contract_legend": "Tell us what your file means",
    "contract_intro": (
        "These cannot be read from your column names, so we never guess them. "
        "Your answers are recorded with the assessment."
    ),
    "contract_id": "Reference for this declaration",
    "contract_evidence": "Who declared this, and on what authority",
    "contract_currency_code": "Currency code for every amount (for example EGP)",
    "contract_currency_hint": "Three letters, shown as capitals (EGP, USD, SAR).",
    "contract_sale_only": "Every row is a sale — returns and refunds are excluded",
    "contract_posted_only": (
        "Every row is posted — void and cancelled events are excluded"
    ),
    "contract_unique_line_grain_attested": "Each row is one order line",
    "contract_transaction_id_column": "Column holding the transaction reference",
    "contract_transaction_id_unique_package_wide": (
        "That reference is unique across the whole file"
    ),
    "contract_revenue_vat_exclusive": "Revenue amounts exclude VAT",
    "contract_revenue_is_net_of_returns": "Revenue is already net of returns",
    "contract_units_are_integral": "Units are whole numbers",
    "contract_cost_is_extended": "Cost is the line total, not a unit cost",
    "contract_discount_is_additive": "Discounts can be added across rows",
}

_AR = {
    "product": "تقييم كِبري لإيرادات التجزئة",
    "skip": "انتقل إلى المحتوى الرئيسي",
    "private_beta": "نسخة تجريبية خاصة",
    "upload_title": "ارفع بيانات مبيعاتك",
    "upload_intro": "ابدأ بملف CSV واحد أو مصنف Excel بورقة واحدة، بحد أقصى 50 ميجابايت.",
    "consent": "أوافق على شروط معالجة البيانات للنسخة التجريبية الخاصة.",
    "choose_file": "اختر ملفاً",
    "drop_file": "اسحب ملف CSV أو XLSX هنا، أو اختر ملفاً",
    "start": "ابدأ التقييم الآمن",
    "retention": "تُحذف الجلسة والتقرير بعد 7 أيام، ويمكنك حذفهما قبل ذلك.",
    "review_title": "هذا ما قرأناه",
    "review_intro": "راجع بنية بيانات التجزئة المكتشفة قبل بدء التحليل.",
    "confirm": "البيانات صحيحة — ابدأ التحليل",
    "restart": "ارفع ملفاً مختلفاً",
    "processing_title": "نعالج بياناتك الآن",
    "processing_intro": "يمكنك إغلاق الصفحة والعودة إلى جلستك الآمنة لاحقاً.",
    "report_title": "تقييم إيرادات التجزئة",
    "report_intro": "حزمة تقريرك الكاملة باللغتين جاهزة.",
    "language": "English",
    "delete": "احذف محتوى الجلسة",
    "expired_title": "هذه الجلسة الآمنة غير متاحة",
    "expired_intro": "اطلب دعوة جديدة للنسخة التجريبية من مستشار كِبري.",
    "uploaded_dataset": "مجموعة البيانات المرفوعة",
    "step_upload": "الرفع",
    "step_review": "المراجعة",
    "step_processing": "التحليل",
    "step_report": "التقرير",
    "accepted": "الملفات المقبولة",
    "size_limit": "الحد الأقصى",
    "you_receive": "ما ستحصل عليه",
    "outputs": "العربية والإنجليزية — ويب وPDF وExcel",
    "language_navigation": "اللغة",
    "journey_progress": "تقدم التقييم",
    "processing_progress": "جاري إعداد التقرير",
    "stage_upload_review": "الرفع والمراجعة",
    "stage_confirmed_facts": "الحقائق المؤكدة",
    "stage_report_generation": "إنشاء التقرير",
    "stage_complete_publication": "اكتمال النشر",
    "processing_preparing": "يتم إعداد التقرير الآمن.",
    "processing_failed": "تعذر إكمال التقرير. احذف هذه الجلسة واطلب دعوة جديدة.",
    "column": "العمود",
    "retail_meaning": "المعنى التجاري",
    "status": "الحالة",
    "evidence": "الدليل",
    "semantic_transaction_date": "تاريخ المعاملة",
    "semantic_revenue": "الإيرادات",
    "semantic_units": "الكمية",
    "semantic_transaction_id": "رقم المعاملة",
    "semantic_product": "المنتج",
    "semantic_category": "الفئة",
    "semantic_store": "المتجر أو الفرع",
    "semantic_channel": "قناة البيع",
    "semantic_cost": "التكلفة",
    "semantic_discount": "قيمة الخصم",
    "semantic_returns": "قيمة المرتجعات",
    "state_mapped": "مطابق",
    "state_ambiguous": "غير محدد",
    "state_conflicting": "غير قابل للاستخدام",
    "state_unavailable": "غير موجود",
    "review_blocked_title": "لا يمكن بدء التحليل بعد:",
    "reason_generic": "لا يمكن تحليل مجموعة البيانات بأمان في صورتها الحالية.",
    "reason_no_data_rows": "لا تحتوي الورقة المرفوعة على صفوف بيانات.",
    "reason_no_time_field": "لم نعثر على عمود صالح لتاريخ المعاملة.",
    "reason_no_core_measure": "لم نعثر على عمود صالح للإيرادات أو الوحدات.",
    "reason_irreconcilable_types": "يحتوي حقل مطلوب على أنواع قيم غير متوافقة.",
    "reason_ambiguous_mapping": "تعذر تحديد معنى تجاري مطلوب بأمان.",
    "reason_missing_semantic": "حقل تجاري مطلوب غير موجود.",
    "finding_duplicate_labels": "يوجد عمودان أو أكثر بالتسمية الآمنة نفسها.",
    "finding_all_columns_empty": "كل الأعمدة المرفوعة فارغة.",
    "dataset": "مجموعة البيانات",
    "rows": "الصفوف",
    "generated": "تاريخ الإنشاء",
    "available_until": "متاح حتى",
    "artifact_web_en": "تقرير الويب بالإنجليزية",
    "artifact_web_ar": "تقرير الويب بالعربية",
    "artifact_evidence_en": "الأدلة بالإنجليزية",
    "artifact_evidence_ar": "الأدلة بالعربية",
    "artifact_pdf_en": "PDF بالإنجليزية",
    "artifact_pdf_ar": "PDF بالعربية",
    "artifact_excel": "Excel ثنائي اللغة",
    "deletion_requested_title": "تم طلب الحذف",
    "deletion_requested_intro": "لم يعد محتواك متاحاً، وستستمر عملية الحذف الآمن تلقائياً.",
    "upload_progress": "تقدم رفع الملف",
    "invitation_unavailable": "هذه الدعوة غير متاحة.",
    "temporary_unavailable": "الجلسة الآمنة غير متاحة مؤقتاً. حاول مرة أخرى.",
    "profile_rejected": (
        "تم رفع الملف لكن تعذر تحليله الأولي. احذف هذه الجلسة واطلب دعوة جديدة."
    ),
    "manifest_legend": "أخبرنا بالفترة التي يغطيها هذا الملف",
    "manifest_intro": (
        "اختياري. بدونه نعرض ما يظهره ملفك، لكننا نمتنع عن مقارنات الفترات "
        "والنمو، لأن الملف لا يثبت بذاته الأيام التي كان يُفترض أن يشملها. "
        "اتركه فارغاً لتخطّيه."
    ),
    "manifest_attested_by": "من يؤكّد ذلك",
    "manifest_attested_by_hint": (
        "اسمك وصفتك الوظيفية، ليوضّح السجل من أكّد الفترة "
        "التي يغطّيها هذا الملف."
    ),
    "manifest_timezone": "المنطقة الزمنية التي يُحسب بها يوم العمل",
    "manifest_timezone_hint": "مثال: Africa/Cairo.",
    "manifest_covered_start": "أول يوم يغطيه هذا الملف",
    "manifest_covered_end": "آخر يوم يغطيه هذا الملف",
    "manifest_aggregate_scope": "اسم الفرع أو المجموعة التي يغطيها الملف",
    "manifest_covered_days": "كل يوم في تلك الفترة، مفصولة بفواصل",
    "manifest_covered_days_hint": (
        "أدرج كل يوم من الأول إلى الأخير، بما في ذلك أي يوم لم تحدث فيه مبيعات."
    ),
    "manifest_event_kinds": "أنواع الصفوف التي يشملها الملف، مفصولة بفواصل",
    "manifest_event_kinds_hint": "مثال: sale.",
    "manifest_statuses": "الحالات التي يشملها الملف، مفصولة بفواصل",
    "manifest_statuses_hint": "مثال: posted.",
    "manifest_closed_days": "أيام الإغلاق، مفصولة بفواصل",
    "manifest_closed_days_hint": (
        "أيام لم تحدث فيها مبيعات لأنك كنت مغلقاً. تظل هذه الأيام مشمولة "
        "بالتغطية، فالصفر هو الإجابة الصحيحة عنها."
    ),
    "manifest_extraction_gap_days": (
        "أيام قد تنقص من الملف صفوفها، مفصولة بفواصل"
    ),
    "manifest_extraction_gap_days_hint": (
        "أيام ربما أسقط التصدير صفوفاً منها. نمتنع عن مقارنات الفترات والنمو "
        "لأي مدى يشمل أحدها، لأننا لا نعرف حجم الناقص."
    ),
    "manifest_partial_terminal_boundary": (
        "كانت إحدى نقاط البيع مفتوحة وقت أخذ هذا الملف"
    ),
    "manifest_partial_terminal_boundary_hint": (
        "علّم هنا فقط إذا جرى التصدير في منتصف وردية. هذا يوقف مقارنات الفترات "
        "والنمو للملف كله، لا لليوم الأخير وحده."
    ),
    "file_invalid": "اختر ملف CSV أو XLSX لا يتجاوز 50 ميجابايت.",
    "upload_failed": "تعذر إكمال الرفع الآمن. حاول مرة أخرى.",
    "review_unavailable": "بيانات المراجعة غير متاحة.",
    "analysis_unavailable": "تعذر بدء التحليل.",
    "refusal_title": "لم يُقبل هذا الملف:",
    "refusal_stated": "تم رفض التقييم لأسباب حاكمة، والسبب المعلن مذكور أعلاه.",
    "contract_legend": "أخبرنا بمعنى بيانات ملفك",
    "contract_intro": (
        "لا يمكن استنتاج هذه المعاني من أسماء الأعمدة، ولذلك لا نخمنها أبداً. "
        "تُسجَّل إجاباتك مع التقييم."
    ),
    "contract_id": "مرجع هذا الإقرار",
    "contract_evidence": "من أقرَّ بهذا، وبأي صفة",
    "contract_currency_code": "رمز العملة لكل المبالغ (مثال: EGP)",
    "contract_currency_hint": "ثلاثة أحرف لاتينية تُكتب بحروف كبيرة (EGP أو USD أو SAR).",
    "contract_sale_only": "كل صف عملية بيع — المرتجعات والمبالغ المستردة مستبعدة",
    "contract_posted_only": "كل صف مُرحَّل — العمليات الملغاة والباطلة مستبعدة",
    "contract_unique_line_grain_attested": "كل صف يمثل بنداً واحداً من الطلب",
    "contract_transaction_id_column": "العمود الذي يحمل مرجع المعاملة",
    "contract_transaction_id_unique_package_wide": "هذا المرجع فريد في الملف بأكمله",
    "contract_revenue_vat_exclusive": "مبالغ الإيرادات لا تشمل ضريبة القيمة المضافة",
    "contract_revenue_is_net_of_returns": "الإيرادات صافية من المرتجعات بالفعل",
    "contract_units_are_integral": "الوحدات أعداد صحيحة",
    "contract_cost_is_extended": "التكلفة هي إجمالي البند، وليست تكلفة الوحدة",
    "contract_discount_is_additive": "يمكن جمع الخصومات على مستوى الصفوف",
}

if _EN.keys() != _AR.keys():
    raise RuntimeError("Journey translations must cover the same vocabulary.")

JOURNEY_COPY = {"en": _EN, "ar": _AR}

__all__ = ["JOURNEY_COPY"]

"""Bilingual copy for the public product landing (`LAND1-01`, RCA-004).

Marketing prose lives here; governed product vocabulary does not. `FR-085` forbids a second
manually maintained truth for metrics, reasons, caveats, or their meanings, so every string in
this module is either marketing narration or a label with no governed counterpart. The specimen's
metric names and its refusal text are read from `khepri.rra.rendering.wording` at render time —
see `landing_api.specimen`.

Parity is asserted at import in the shape `legal_copy` established: a key present in one language
and absent from the other raises before a visitor can meet the gap.
"""

from __future__ import annotations

#: Marketing narration, English.
_EN: dict[str, str] = {
    "product": "Khepri",
    "tagline": "Retail decisions you can prove.",
    "skip": "Skip to content",
    "language": "العربية",
    "language_code": "ar",
    "language_navigation": "Language",
    "legal_navigation": "Legal",
    "claim_lede": (
        "Khepri turns the retail export you already have into analysis that carries its own "
        "evidence — and names what it cannot support instead of estimating it."
    ),
    "claim_prove": "prove",
    "specimen_file": "q3-sales-export.csv",
    "specimen_admitted": "Admitted",
    "specimen_population_term": "Population",
    "specimen_population_value": "18 stores · 1 quarter",
    "specimen_caption": "Illustrative export. Not customer data.",
    "specimen_withheld_term": "Change against the prior quarter",
    "register_ii": "Register II · The passage",
    "register_v": "Register III · What an answer is worth",
    "passage_1_term": "Operational export",
    "passage_1_detail": "The file the retailer already produces, imperfect as it is.",
    "passage_1_state": "41,905 rows · 22 columns",
    "passage_2_term": "Semantic admission",
    "passage_2_detail": (
        "Meaning, population and coverage are established and shown back to you before any "
        "figure is calculated."
    ),
    "passage_2_state": "18 stores · 1 quarter admitted",
    "passage_3_term": "Deterministic facts",
    "passage_3_detail": (
        "Versioned retail calculations. The same admissible inputs give the same result."
    ),
    "passage_4_term": "Evidence, caveats, refusals",
    "passage_4_detail": (
        "Each figure reconciles with the evidence behind it. What cannot be supported is named, "
        "and stays named."
    ),
    "passage_5_term": "A result you can defend",
    "passage_5_detail": (
        "The same facts in Arabic and English, carrying their caveats and refusals with them."
    ),
    "passage_figure": "Refusal is a capability.",
    "passage_figure_em": (
        "We would rather refuse an unsupported answer than manufacture confidence."
    ),
    "contrast_theirs_label": "Typical analytics",
    "contrast_theirs": "“Here is your answer.”",
    "contrast_ours_label": "Khepri",
    "contrast_ours_before": "“Here is the answer we can ",
    "contrast_ours_after": " — and here is what we cannot.”",
    "verdict_proven_name": "Proven",
    "verdict_proven_claim": "Revenue reconciles across all 18 stores.",
    "verdict_proven_detail": (
        "Population and coverage were established first; the figure matches the rows behind it."
    ),
    "verdict_caveated_name": "Caveated",
    "verdict_caveated_claim": "Monthly figures are reported, and qualified.",
    "verdict_caveated_detail": (
        "Some rows carried no date. The figure is still reported, and the qualification travels "
        "with it wherever it is read — again in the product's own wording:"
    ),
    "verdict_withheld_name": "Withheld",
    "verdict_withheld_claim": "Comparison with an earlier period is not reported here.",
    "verdict_withheld_detail": (
        "Khepri states the reason in the place the comparison would have appeared. This is the "
        "product's own wording, not a marketing paraphrase:"
    ),
    "verdicts_note": (
        "The three results above are illustrative, not customer data. Their state names and the "
        "refusal wording are the product's governed vocabulary."
    ),
    "pillars_heading": "Why Khepri",
    "pillar_1_name": "Provable figures",
    "pillar_1_body": (
        "Every important figure reconciles with the evidence behind it, reachable from the claim "
        "it supports."
    ),
    "pillar_2_name": "Explicit uncertainty",
    "pillar_2_body": (
        "Caveats and unavailable conclusions stay visible, in the place the answer would have "
        "appeared."
    ),
    "pillar_3_name": "Bilingual parity",
    "pillar_3_body": (
        "Arabic and English receive equivalent facts, caveats and refusals. Neither is a "
        "translation of the other."
    ),
    "pillar_4_name": "Reproducible analysis",
    "pillar_4_body": (
        "The same admissible inputs produce the same governed result, under a stated calculation "
        "version."
    ),
    "scripts_heading": "One result, two first-class languages",
    "scripts_note": (
        "Figures shown are illustrative, not customer data. Each panel names the metric from the "
        "same governed catalog, in its own script."
    ),
    # ---- Deliverables. The four surfaces PRODUCT.md records; no product is invented here. ----
    "deliverables_heading": "One admission, four deliverables",
    "deliverables_lede": (
        "The same governed facts feed every surface. None of them recalculates; they select and "
        "present what was already admitted."
    ),
    "deliverable_1_name": "The interactive review",
    "deliverable_1_body": (
        "Read the analysis on screen, with each caveat and refusal in the place its answer would "
        "have appeared."
    ),
    "deliverable_2_name": "The final report",
    "deliverable_2_body": (
        "An executive deliverable built to be read on screen and on paper, carrying the same "
        "figures and the same refusals."
    ),
    "deliverable_3_name": "The evidence layer",
    "deliverable_3_body": (
        "Reached from the claim it supports, not filed in a separate archive. Evidence is "
        "contextual by design."
    ),
    "deliverable_4_name": "The Excel artifact",
    "deliverable_4_body": (
        "Structured output for the work that continues downstream, from the same admitted facts."
    ),
    # ---- The refusal gallery. Every message is read from the governed catalog at render time. ----
    "refusals_heading": "What Khepri refuses, and why",
    "refusals_lede": (
        "These are not error messages. Each is a governed result: the reason is named, the rest "
        "of the review is unaffected, and the file change that would make the answer available "
        "is stated. This is the product's own wording, read from the same catalog the report "
        "uses."
    ),
    "refusals_note": (
        "Six of the governed refusals, read from the product catalog rather than written here. "
        "Each names its own remedy; none is a generic failure."
    ),
    # ---- Questions. Answered from what the product actually is. ----
    "questions_heading": "Questions",
    "question_1": "What does Khepri need from me?",
    "answer_1": (
        "The sales export your point-of-sale system already produces. There is no integration "
        "to build and no schema to match first \u2014 Khepri establishes what your columns mean, "
        "shows that reading back to you, and only then calculates."
    ),
    "question_2": "What happens when my file cannot answer a question?",
    "answer_2": (
        "The question is refused by name, in the place the answer would have appeared, with the "
        "reason and the file change that would make it available. A refusal is a governed "
        "result, not a failure, and it never uses error styling."
    ),
    "question_3": "Can I check a figure against the rows behind it?",
    "answer_3": (
        "Yes. Evidence is reached from the claim it supports rather than from a separate "
        "archive, so a figure and its proof are never more than one step apart."
    ),
    "question_4": "Do Arabic and English readers get the same thing?",
    "answer_4": (
        "Yes, and this is enforced rather than intended. Arabic and English carry equivalent "
        "facts, caveats, refusals and evidence; a missing string fails the build rather than "
        "reaching a reader. Neither language is a translation of the other."
    ),
    "question_5": "Will the same file give the same answer twice?",
    "answer_5": (
        "Yes. Facts are deterministic and versioned, under a stated calculation version. "
        "Templates, dashboards and AI may select and present those facts; they may not "
        "recalculate them."
    ),
    "question_6": "How do I get access?",
    "answer_6": (
        "Khepri is in private beta with a small number of retail operators. Access is arranged "
        "directly with them, and there is no public sign-up."
    ),
    "close_headline": "Bring your retail data. Get decisions you can defend.",
    "close_body": (
        "Khepri is in private beta with a small number of retail operators. Access is arranged "
        "directly, and there is no public sign-up."
    ),
}

#: Marketing narration, Arabic. Composed for Arabic, not translated word for word.
_AR: dict[str, str] = {
    "product": "خِبري",
    "tagline": "قرارات تجزئة يمكنك إثباتها.",
    "skip": "تخطَّ إلى المحتوى",
    "language": "English",
    "language_code": "en",
    "language_navigation": "اللغة",
    "legal_navigation": "معلومات قانونية",
    "claim_lede": (
        "يحوّل خِبري ملف التجزئة الذي لديك بالفعل إلى تحليل يحمل أدلته معه — ويسمّي ما لا "
        "يستطيع إثباته بدل أن يقدّره."
    ),
    "claim_prove": "إثباتها",
    "specimen_file": "q3-sales-export.csv",
    "specimen_admitted": "مقبول",
    "specimen_population_term": "النطاق",
    "specimen_population_value": "١٨ متجرًا · ربع سنة",
    "specimen_caption": "ملف توضيحي. ليس بيانات عميل.",
    "specimen_withheld_term": "التغيّر مقارنةً بالربع السابق",
    "register_ii": "السجل الثاني · المسار",
    "register_v": "السجل الثالث · ما قيمة الإجابة",
    "passage_1_term": "ملف تشغيلي",
    "passage_1_detail": "الملف الذي ينتجه المتجر أصلًا، بما فيه من نقص.",
    "passage_1_state": "٤١٬٩٠٥ صفًا · ٢٢ عمودًا",
    "passage_2_term": "قبول دلالي",
    "passage_2_detail": (
        "يُحدَّد المعنى والنطاق والتغطية وتُعرض عليك قبل حساب أي رقم."
    ),
    "passage_2_state": "١٨ متجرًا · ربع سنة مقبول",
    "passage_3_term": "حقائق حتمية",
    "passage_3_detail": (
        "حسابات تجزئة موثّقة الإصدار. المدخلات المقبولة نفسها تعطي النتيجة نفسها."
    ),
    "passage_4_term": "أدلة وتحفّظات وامتناع",
    "passage_4_detail": (
        "كل رقم يطابق الدليل الذي خلفه. وما لا يمكن إثباته يُسمّى، ويبقى مسمًّى."
    ),
    "passage_5_term": "نتيجة يمكنك الدفاع عنها",
    "passage_5_detail": (
        "الحقائق نفسها بالعربية والإنجليزية، وتحمل معها تحفّظاتها وامتناعها."
    ),
    "passage_figure": "الامتناع قدرة.",
    "passage_figure_em": "نفضّل الامتناع عن إجابة غير مثبتة على أن نصطنع ثقة بها.",
    "contrast_theirs_label": "التحليلات المعتادة",
    "contrast_theirs": "«هذه إجابتك.»",
    "contrast_ours_label": "خِبري",
    "contrast_ours_before": "«هذه الإجابة التي نستطيع ",
    "contrast_ours_after": " — وهذا ما لا نستطيعه.»",
    "verdict_proven_name": "مثبت",
    "verdict_proven_claim": "الإيرادات مطابَقة عبر المتاجر الـ١٨ جميعها.",
    "verdict_proven_detail": (
        "حُدِّد النطاق والتغطية أولًا، والرقم يطابق الصفوف التي خلفه."
    ),
    "verdict_caveated_name": "متحفَّظ عليه",
    "verdict_caveated_claim": "الأرقام الشهرية مُصدَرة، ومتحفَّظ عليها.",
    "verdict_caveated_detail": (
        "بعض الصفوف لم تحمل تاريخًا. والرقم مُصدَر رغم ذلك، والتحفّظ يرافقه أينما قُرئ — وهذا "
        "أيضًا نص المنتج نفسه:"
    ),
    "verdict_withheld_name": "ممتنع",
    "verdict_withheld_claim": "المقارنة بفترة سابقة غير مُصدَرة هنا.",
    "verdict_withheld_detail": (
        "يذكر خِبري السبب في الموضع الذي كانت المقارنة ستظهر فيه. وهذا نص المنتج نفسه، لا صياغة "
        "تسويقية:"
    ),
    "verdicts_note": (
        "النتائج الثلاث أعلاه توضيحية، وليست بيانات عميل. وأسماء حالاتها ونص الامتناع هي مفردات "
        "المنتج المعتمدة."
    ),
    "pillars_heading": "لماذا خِبري",
    "pillar_1_name": "أرقام قابلة للإثبات",
    "pillar_1_body": (
        "كل رقم مهم يطابق الدليل الذي خلفه، ويمكن الوصول إليه من الادعاء الذي يسنده."
    ),
    "pillar_2_name": "عدم يقين معلن",
    "pillar_2_body": (
        "تبقى التحفّظات والنتائج غير المتاحة ظاهرة، في الموضع الذي كانت الإجابة ستظهر فيه."
    ),
    "pillar_3_name": "تكافؤ اللغتين",
    "pillar_3_body": (
        "تتلقى العربية والإنجليزية الحقائق والتحفّظات والامتناع ذاتها. وليست إحداهما ترجمة "
        "للأخرى."
    ),
    "pillar_4_name": "تحليل قابل للتكرار",
    "pillar_4_body": (
        "المدخلات المقبولة نفسها تنتج النتيجة المعتمدة نفسها، وفق إصدار حساب معلن."
    ),
    "scripts_heading": "نتيجة واحدة، لغتان أصيلتان",
    "scripts_note": (
        "الأرقام المعروضة توضيحية، وليست بيانات عميل. وتسمّي كل لوحة المقياس من الفهرس المعتمد "
        "نفسه، بحروفها هي."
    ),
    # ---- المخرجات الأربعة ----
    "deliverables_heading": "قبول واحد، وأربعة مخرجات",
    "deliverables_lede": (
        "الحقائق المحكومة نفسها تغذّي كل سطح. ولا يعيد أيٌ منها الحساب؛ إنما ينتقي ويعرض ما "
        "سبق قبوله."
    ),
    "deliverable_1_name": "المراجعة التفاعلية",
    "deliverable_1_body": (
        "اقرأ التحليل على الشاشة، مع كل تحفّظ وامتناع في الموضع الذي كانت إجابته ستظهر فيه."
    ),
    "deliverable_2_name": "التقرير النهائي",
    "deliverable_2_body": (
        "مخرَج تنفيذي مُعدّ للقراءة على الشاشة وعلى الورق، يحمل الأرقام نفسها والامتناعات نفسها."
    ),
    "deliverable_3_name": "طبقة الأدلة",
    "deliverable_3_body": (
        "يُوصل إليها من الادعاء الذي تسنده، لا من أرشيف منفصل. فالأدلة سياقية بحكم التصميم."
    ),
    "deliverable_4_name": "ملف الإكسل",
    "deliverable_4_body": (
        "مخرَج مُهيكل للعمل الذي يستمر لاحقاً، من الحقائق المقبولة نفسها."
    ),
    # ---- معرض الامتناعات ----
    "refusals_heading": "ما يمتنع عنه خِبري، ولماذا",
    "refusals_lede": (
        "هذه ليست رسائل خطأ. كل واحدة نتيجة محكومة: يُسمّى السبب، وتبقى بقية التقرير غير "
        "متأثرة، ويُذكر التغيير في الملف الذي يجعل الإجابة متاحة. وهذا نص المنتج نفسه، مقروءاً "
        "من الفهرس ذاته الذي يستخدمه التقرير."
    ),
    "refusals_note": (
        "ستة من الامتناعات المحكومة، مقروءة من فهرس المنتج لا مكتوبة هنا. "
        "كل واحد يذكر علاجه؛ ولا واحد منها عطل عام."
    ),
    # ---- أسئلة ----
    "questions_heading": "أسئلة",
    "question_1": "ماذا يحتاج خِبري مني؟",
    "answer_1": (
        "ملف المبيعات الذي ينتجه نظام نقاط البيع لديك أصلاً. لا يوجد ربط تقني تبنيه ولا مخطط "
        "تطابقه أولاً — يحدّد خِبري معنى أعمدتك، ويعرض عليك هذه القراءة، ثم يحسب بعد ذلك."
    ),
    "question_2": "ماذا يحدث حين لا يستطيع ملفي الإجابة عن سؤال؟",
    "answer_2": (
        "يُمتنع عن السؤال بالاسم، في الموضع الذي كانت الإجابة ستظهر فيه، مع السبب والتغيير في "
        "الملف الذي يجعلها متاحة. فالامتناع نتيجة محكومة لا عطل، ولا يستخدم تنسيق الأخطاء أبداً."
    ),
    "question_3": "هل يمكنني التحقق من رقم مقابل الصفوف التي خلفه؟",
    "answer_3": (
        "نعم. يُوصل إلى الأدلة من الادعاء الذي تسنده لا من أرشيف منفصل، فلا يبعد الرقم عن "
        "دليله أكثر من خطوة واحدة."
    ),
    "question_4": "هل يحصل قارئ العربية وقارئ الإنجليزية على الشيء نفسه؟",
    "answer_4": (
        "نعم، وهذا مفروض لا منويّ. تحمل العربية والإنجليزية حقائق وتحفّظات وامتناعات وأدلة "
        "متكافئة؛ والنص الناقص يُفشل البناء بدل أن يصل إلى قارئ. وليست إحداهما ترجمة للأخرى."
    ),
    "question_5": "هل يعطي الملف نفسه الإجابة نفسها مرتين؟",
    "answer_5": (
        "نعم. الحقائق حتمية ومُصدّرة بإصدار، تحت إصدار حساب معلن. وللقوالب ولوحات المعلومات "
        "والذكاء الاصطناعي أن تنتقي هذه الحقائق وتعرضها؛ وليس لها أن تعيد حسابها."
    ),
    "question_6": "كيف أحصل على الوصول؟",
    "answer_6": (
        "خِبري في نسخة تجريبية خاصة مع عدد محدود من مشغّلي التجزئة. ويُرتّب الوصول معهم "
        "مباشرةً، ولا يوجد تسجيل عام."
    ),
    "close_headline": "أحضِر بيانات تجزئتك. واحصل على قرارات تستطيع الدفاع عنها.",
    "close_body": (
        "خِبري في نسخة تجريبية خاصة مع عدد محدود من مشغّلي التجزئة. ويُرتَّب الوصول مباشرةً، ولا "
        "يوجد تسجيل عام."
    ),
}

if set(_EN) != set(_AR):  # pragma: no cover -- import-time parity guard
    missing = set(_EN).symmetric_difference(_AR)
    raise RuntimeError(f"LANDING_COPY is not at language parity: {sorted(missing)}")

_EMPTY_EN = sorted(key for key, value in _EN.items() if not value.strip())
_EMPTY_AR = sorted(key for key, value in _AR.items() if not value.strip())
if _EMPTY_EN or _EMPTY_AR:  # pragma: no cover -- import-time completeness guard
    raise RuntimeError(f"LANDING_COPY has empty values: {sorted({*_EMPTY_EN, *_EMPTY_AR})}")

#: Every marketing string, by language.
LANDING_COPY = {"en": _EN, "ar": _AR}

#: The reading direction each language is rendered in, server-computed and never inferred.
LANDING_DIRECTIONS = {"en": "ltr", "ar": "rtl"}

if set(LANDING_COPY) != set(LANDING_DIRECTIONS):  # pragma: no cover -- import-time guard
    raise RuntimeError("LANDING_COPY and LANDING_DIRECTIONS cover different languages.")

__all__ = ["LANDING_COPY", "LANDING_DIRECTIONS"]

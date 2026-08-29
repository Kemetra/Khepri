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
        "Figures shown are illustrative, not customer data. Both panels carry the same facts, the "
        "same caveats and the same refusals."
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
        "الأرقام المعروضة توضيحية، وليست بيانات عميل. وتحمل اللوحتان الحقائق والتحفّظات "
        "والامتناع ذاتها."
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

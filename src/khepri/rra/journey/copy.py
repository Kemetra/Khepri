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
}

if _EN.keys() != _AR.keys():
    raise RuntimeError("Journey translations must cover the same vocabulary.")

JOURNEY_COPY = {"en": _EN, "ar": _AR}

__all__ = ["JOURNEY_COPY"]

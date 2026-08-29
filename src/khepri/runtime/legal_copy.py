"""Bilingual public legal copy (`LEGAL1-01` through `LEGAL1-05`, RCA-003)."""

# ruff: noqa: E501

from __future__ import annotations

_EN = {
    "product": "Khepri",
    "skip": "Skip to main content",
    "language": "العربية",
    "language_code": "ar",
    "language_navigation": "Language",
    "legal_navigation": "Legal information",
    "unpublished_title": "This page is not currently published.",
    "unpublished_intro": (
        "This legal information is not currently available for public publication."
    ),
}

_AR = {
    "product": "خِبري",
    "skip": "تخطَّ إلى المحتوى الرئيسي",
    "language": "English",
    "language_code": "en",
    "language_navigation": "اللغة",
    "legal_navigation": "معلومات قانونية",
    "unpublished_title": "هذه الصفحة غير منشورة حاليًا.",
    "unpublished_intro": "هذه المعلومات القانونية غير متاحة حاليًا للنشر العام.",
}

if set(_EN) != set(_AR):  # pragma: no cover -- import-time parity guard
    missing = set(_EN).symmetric_difference(_AR)
    raise RuntimeError(f"LEGAL_COPY is not at language parity: {sorted(missing)}")

LEGAL_COPY = {"en": _EN, "ar": _AR}

LEGAL_PAGE_TITLES = {
    "en": {
        "privacy-policy": "Privacy Policy",
        "data-protection": "Data Protection",
        "terms-and-conditions": "Terms and Conditions",
        "contact-us": "Contact Us",
        "about-us": "About Us",
        "refund-and-void": "Refund & Void",
    },
    "ar": {
        "privacy-policy": "سياسة الخصوصية",
        "data-protection": "حماية البيانات",
        "terms-and-conditions": "الشروط والأحكام",
        "contact-us": "اتصل بنا",
        "about-us": "من نحن",
        "refund-and-void": "حالة الاسترداد والإلغاء",
    },
}

if set(LEGAL_PAGE_TITLES["en"]) != set(LEGAL_PAGE_TITLES["ar"]):  # pragma: no cover
    missing = set(LEGAL_PAGE_TITLES["en"]).symmetric_difference(LEGAL_PAGE_TITLES["ar"])
    raise RuntimeError(f"LEGAL_PAGE_TITLES is not at language parity: {sorted(missing)}")

DIRECTIONS = {"en": "ltr", "ar": "rtl"}

LEGAL_DOCUMENTS = {
    "privacy-policy": {
        "en": (
            "Khepri is a governed retail decision platform. This Privacy Policy remains unavailable until an approved version includes the verified operator identity, privacy contact, and effective date.",
            "Khepri processes service-administration information, customer-uploaded operational data, and the technical information needed to provide the service.",
            "Processing is limited to providing requested service functions, protecting the service, and meeting obligations under the applicable agreement and law.",
            "Depending on the context, Khepri may act as a controller for service-administration information and as a processor or service provider for customer-uploaded operational data. Customer-uploaded operational data remains customer-controlled.",
            "Service providers or subprocessors may process information under appropriate instructions and the applicable agreement. A public version will identify their role only when that disclosure is verified.",
            "A public version will state the applicable international-transfer position when it has been verified; this draft does not state an environment location.",
            "Retention is addressed through the applicable agreement and active data-use authority; this draft states no retention period.",
            "The public security summary will describe only safeguards confirmed for the environment being described.",
            "Where a privacy right or request may apply, the approved public policy will provide the verified privacy contact route. It does not promise product controls for deletion or export.",
        ),
        "ar": (
            "خِبري منصة محكومة لاتخاذ القرارات في قطاع التجزئة. تظل سياسة الخصوصية هذه غير متاحة إلى أن تتضمن النسخة المعتمدة هوية المشغل المؤكدة ووسيلة اتصال الخصوصية وتاريخ السريان.",
            "تعالج خِبري معلومات إدارة الخدمة والبيانات التشغيلية التي يحمّلها العملاء والمعلومات التقنية اللازمة لتقديم الخدمة.",
            "يقتصر هذا التعامل على تقديم وظائف الخدمة المطلوبة وحماية الخدمة والوفاء بالالتزامات بموجب الاتفاق والقانون المنطبقين.",
            "بحسب السياق، قد تعمل خِبري كمتحكم في معلومات إدارة الخدمة وكمعالج أو مقدم خدمة للبيانات التشغيلية التي يحمّلها العملاء. وتظل تلك البيانات تحت سيطرة العميل.",
            "قد يعالج مقدمو الخدمة أو المعالجون الفرعيون المعلومات وفق تعليمات مناسبة والاتفاق المنطبق. ولا تحدد النسخة العامة دورهم إلا بعد التحقق من هذا الإفصاح.",
            "ستوضح النسخة العامة موقف نقل البيانات الدولي المنطبق بعد التحقق منه؛ ولا يذكر هذا المسود موقع استضافة أو إقامة للبيانات.",
            "تتناول ترتيبات الاحتفاظ البيانات الاتفاق المنطبق وسلطة استخدام البيانات السارية؛ ولا يذكر هذا المسود مدة للاحتفاظ.",
            "يصف الملخص الأمني العام الضمانات المؤكدة فقط للبيئة التي يصفها.",
            "عندما ينطبق حق أو طلب متعلق بالخصوصية، توفر السياسة العامة المعتمدة وسيلة اتصال الخصوصية المؤكدة. ولا تعد بوظائف حذف أو تصدير ذاتية.",
        ),
    },
    "data-protection": {
        "en": (
            "This Data Protection page remains unavailable until an approved version includes the verified operator identity, privacy contact, and effective date.",
            "Khepri's public browser surfaces use restrictive response security headers and load presentation assets from the same origin.",
            "The public statement describes safeguards only when they are confirmed for the environment being described. It does not state an environment location, recovery commitment, or performance commitment.",
            "Customer-uploaded operational data is processed to provide the service and remains customer-controlled under the applicable agreement and active data-use authority.",
            "Where a service provider processes information for Khepri, the approved public statement describes only its verified role and the applicable contractual safeguards.",
        ),
        "ar": (
            "تظل صفحة حماية البيانات غير متاحة إلى أن تتضمن النسخة المعتمدة هوية المشغل المؤكدة ووسيلة اتصال الخصوصية وتاريخ السريان.",
            "تستخدم واجهات خِبري العامة في المتصفح ترويسات استجابة مقيدة وتحمل أصول العرض من المصدر نفسه.",
            "يصف البيان العام الضمانات المؤكدة فقط للبيئة التي يصفها. ولا يذكر منطقة استضافة أو موقف إقامة بيانات أو التزامًا بالتعافي أو التزامًا بمستوى الخدمة.",
            "تُعالج البيانات التشغيلية التي يحمّلها العملاء لتقديم الخدمة وتظل تحت سيطرة العميل بموجب الاتفاق المنطبق وسلطة استخدام البيانات السارية.",
            "عندما يعالج مقدم خدمة معلومات لصالح خِبري، يصف البيان العام المعتمد دوره المتحقق والضمانات التعاقدية المنطبقة فقط.",
        ),
    },
    "terms-and-conditions": {
        "en": (
            "These Terms and Conditions remain unavailable until an approved version identifies the verified contracting operator, support contact, governing law, dispute process, and effective date.",
            "Authorized customers are responsible for their accounts, authorized users, and lawful use of customer-uploaded operational data.",
            "The service may be used only for lawful, authorized business purposes and must not be used to interfere with the service or another party's rights.",
            "Customer-uploaded operational data remains customer-controlled, subject to the applicable agreement and active data-use authority.",
            "Analytical outputs are decision-support material and do not replace a customer's own business, professional, legal, or regulatory judgment.",
            "Where the applicable agreement identifies the service as beta, its beta status and applicable limitations govern the relationship.",
            "Khepri and its licensors retain rights in the service, while customers retain rights in their customer-controlled operational data, subject to the applicable agreement.",
            "The approved Terms will state the applicable suspension and termination principles, liability approach, contracting relationship, governing law, dispute process, and verified contact route.",
        ),
        "ar": (
            "تظل هذه الشروط والأحكام غير متاحة إلى أن تحدد النسخة المعتمدة المشغل المتعاقد المؤكد ووسيلة اتصال الدعم والقانون الحاكم وإجراءات النزاع وتاريخ السريان.",
            "يتحمل العملاء المصرح لهم مسؤولية حساباتهم ومستخدميهم المصرح لهم والاستخدام المشروع للبيانات التشغيلية التي يحمّلونها.",
            "لا يجوز استخدام الخدمة إلا لأغراض أعمال مشروعة ومصرح بها، ولا يجوز استخدامها للتدخل في الخدمة أو في حقوق أي طرف آخر.",
            "تظل البيانات التشغيلية التي يحمّلها العملاء تحت سيطرة العميل، وفق الاتفاق المنطبق وسلطة استخدام البيانات السارية.",
            "تمثل المخرجات التحليلية مواد لدعم القرار ولا تحل محل حكم العميل التجاري أو المهني أو القانوني أو التنظيمي الخاص به.",
            "عندما يصف الاتفاق المنطبق الخدمة بأنها تجريبية، تحكم حالتها التجريبية والقيود المنطبقة العلاقة.",
            "تحتفظ خِبري ومانحو تراخيصها بالحقوق في الخدمة، بينما يحتفظ العملاء بالحقوق في بياناتهم التشغيلية الخاضعة لسيطرتهم، وفق الاتفاق المنطبق.",
            "توضح الشروط المعتمدة مبادئ الإيقاف والإنهاء المنطبقة ونهج المسؤولية والعلاقة التعاقدية والقانون الحاكم وإجراءات النزاع ووسيلة الاتصال المؤكدة.",
        ),
    },
    "contact-us": {
        "en": (
            "Contact Us remains unavailable until an approved version identifies the verified operator, support contact route, and effective date.",
            "No public address, telephone number, or role mailbox is stated before it has been verified for publication.",
        ),
        "ar": (
            "تظل صفحة اتصل بنا غير متاحة إلى أن تحدد النسخة المعتمدة المشغل المؤكد ووسيلة اتصال الدعم وتاريخ السريان.",
            "لا يذكر عنوان أو رقم هاتف أو صندوق بريد مخصص للجمهور قبل التحقق من صلاحيته للنشر.",
        ),
    },
    "about-us": {
        "en": (
            "Khepri is a governed retail decision platform.",
            "It helps authorized teams work with their operational data to produce structured decision material within their approved context.",
            "Its public and product surfaces are delivered under approved specifications and do not make unverified claims about customers, scale, certifications, or service commitments.",
        ),
        "ar": (
            "خِبري منصة محكومة لاتخاذ القرارات في قطاع التجزئة.",
            "تساعد الفرق المصرح لها على العمل مع بياناتها التشغيلية لإنتاج مواد قرار منظمة ضمن سياقها المعتمد.",
            "تقدم واجهاتها العامة وواجهات المنتج وفق مواصفات معتمدة ولا تقدم ادعاءات غير متحقق منها بشأن العملاء أو النطاق أو الشهادات أو التزامات الخدمة.",
        ),
    },
    "refund-and-void": {
        "en": (
            "No general public self-service refund policy currently applies.",
            "Private commercial fees are governed by the applicable agreement and law.",
            "Detailed refund or void mechanics require future billing authority and are not published on this page.",
        ),
        "ar": (
            "لا تسري حاليًا سياسة عامة للاسترداد الذاتي للجمهور.",
            "تخضع الرسوم التجارية الخاصة للاتفاق والقانون المنطبقين.",
            "تتطلب تفاصيل آليات الاسترداد أو الإلغاء سلطة فوترة مستقبلية ولا تنشر في هذه الصفحة.",
        ),
    },
}

__all__ = ["DIRECTIONS", "LEGAL_COPY", "LEGAL_DOCUMENTS", "LEGAL_PAGE_TITLES"]

import * as React from "react";
import { LogConsole } from "@khepri/ds";

export const LiveRunLog = () => (
  <div style={{ maxWidth: 520 }}>
    <LogConsole
      lines={[
        { time: "10:59:12", message: "جاري تهيئة نموذج جودة الهواء...", level: "info" },
        { time: "10:58:41", message: "تم الانتهاء من التحقق من صحة البيانات لمجموعة \"مؤشرات جودة الهواء\"" },
        { time: "10:58:02", message: "بدء تنفيذ نموذج جودة الهواء (Air Quality Model)" },
        { time: "10:57:18", message: "تم استيعاب 1.2 مليون سجل من مجموعة بيانات \"محطات الرصد\"" },
        { time: "10:56:33", message: "تنبيه: قيم مفقودة في حقل PM2_5 (8,421 سجل)", level: "warning" },
        { time: "10:54:17", message: "فشل الاتصال بمصدر خارجي، ستتم إعادة المحاولة", level: "error" },
        { time: "10:32:10", message: "بدأ تنفيذ التحليل بواسطة سارة أحمد" },
      ]}
    />
  </div>
);

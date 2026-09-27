import * as React from "react";
import { FileRow, ConfidenceBadge } from "@khepri/ds";

export const UploadedDatasets = () => (
  <div style={{ maxWidth: 380 }}>
    <FileRow name="بيانات جودة الهواء 2020-2024" kind="csv" size="245 MB" date="2025/04/20" />
    <FileRow name="مؤشرات الطاقة المتجددة" kind="xlsx" size="128 MB" date="2025/04/18" />
    <FileRow name="البيانات السكانية والاقتصادية" kind="csv" size="310 MB" date="2025/04/15" />
    <FileRow name="السياسات البيئية الإقليمية" kind="xlsx" size="96 MB" date="2025/04/12" />
  </div>
);

export const EvidenceAttachments = () => (
  <div style={{ maxWidth: 460 }}>
    <FileRow name="تقرير وزارة الكهرباء والطاقة المتجددة" kind="pdf" size="4.2 MB" date="2024/03/15" trailing={<ConfidenceBadge value={92} />} />
    <FileRow name="بيانات القدرة المركبة حسب المصدر" kind="xlsx" size="1.8 MB" date="2024/02/10" trailing={<ConfidenceBadge value={74} />} />
  </div>
);

import * as React from "react";
import { PrimaryCell, FileTypeIcon, Avatar } from "@khepri/ds";

export const TitleAndEnglish = () => <PrimaryCell title="أثر سياسات الطاقة المتجددة" subtitle="Renewable Energy Policy Impact" />;

export const WithLeading = () => (
  <div className="k-stack">
    <PrimaryCell leading={<FileTypeIcon kind="xlsx" />} title="مؤشرات_السكان_المناطق.xlsx" subtitle="128 MB" />
    <PrimaryCell leading={<Avatar name="سارة أحمد" size={32} />} title="سارة أحمد" subtitle="مدير التحليلات" />
  </div>
);

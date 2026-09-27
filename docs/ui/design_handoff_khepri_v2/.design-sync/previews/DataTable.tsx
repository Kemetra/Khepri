import * as React from "react";
import { DataTable, PrimaryCell, StatusPill, IconButton, FileTypeIcon, Tag } from "@khepri/ds";

const analyses = [
  { name: "أثر سياسات الطاقة المتجددة", en: "Renewable Energy Policy Impact", status: "complete", date: "2025/04/21", time: "10:32 ص" },
  { name: "تحليل جودة الهواء في المدن الكبرى", en: "Urban Air Quality Analysis", status: "complete", date: "2025/04/20", time: "03:15 م" },
  { name: "مقارنة السياسات الإقليمية للمياه", en: "Regional Water Policy Comparison", status: "running", date: "2025/04/19", time: "11:20 ص" },
  { name: "فرص الاقتصاد الأخضر", en: "Green Economy Opportunities", status: "review", date: "2025/04/17", time: "02:18 م" },
] as const;

export const RecentAnalyses = () => (
  <div style={{ maxWidth: 640 }}>
    <DataTable
      rows={analyses as unknown as Array<Record<string, string>>}
      columns={[
        { key: "name", header: "الاسم", render: (r) => <PrimaryCell title={r.name} subtitle={r.en} /> },
        { key: "status", header: "الحالة", render: (r) => <StatusPill status={r.status as "complete"} size="sm" /> },
        { key: "date", header: "تاريخ التنفيذ", render: (r) => <PrimaryCell title={r.date} subtitle={r.time} /> },
        { key: "menu", header: "", width: 40, render: () => <IconButton icon="more" label="خيارات" size="sm" /> },
      ]}
    />
  </div>
);

const files = [
  { name: "استهلاك_الطاقة_2024_2020", kind: "csv", size: "24.5 MB", source: "وزارة الكهرباء والطاقة", status: "complete", tags: ["طاقة", "استهلاك"] },
  { name: "مؤشرات_السكان_المناطق.xlsx", kind: "xlsx", size: "128 MB", source: "الجهاز المركزي للتعبئة والإحصاء", status: "complete", tags: ["سكان", "مناطق"] },
  { name: "تقرير_السياسات_البيئية.pdf", kind: "pdf", size: "6.3 MB", source: "رفع يدوي", status: "running", tags: ["سياسات"] },
] as const;

export const UploadedFiles = () => (
  <div style={{ maxWidth: 720 }}>
    <DataTable
      rows={files as unknown as Array<Record<string, unknown>>}
      columns={[
        {
          key: "name", header: "اسم الملف",
          render: (r) => (
            <PrimaryCell
              leading={<FileTypeIcon kind={r.kind as "csv"} />}
              title={r.name as string}
              subtitle={<span className="k-row" style={{ gap: 4, marginTop: 4 }}>{(r.tags as string[]).map((t) => <Tag key={t}>{t}</Tag>)}</span>}
            />
          ),
        },
        { key: "size", header: "الحجم", numeric: true },
        { key: "kind", header: "النوع", render: (r) => <FileTypeIcon kind={r.kind as "csv"} variant="chip" /> },
        { key: "source", header: "المصدر" },
        { key: "status", header: "الحالة", render: (r) => <StatusPill status={r.status as "complete"} label={r.status === "running" ? "قيد المعالجة" : undefined} size="sm" /> },
      ]}
    />
  </div>
);

export const DensePreview = () => (
  <div style={{ maxWidth: 560 }}>
    <DataTable
      dense
      striped
      rows={[
        { id: "C-001", date: "2025/04/01", region: "القاهرة", pm25: 12.4, pm10: 28.1 },
        { id: "C-002", date: "2025/04/01", region: "الجيزة", pm25: 18.7, pm10: 35.2 },
        { id: "C-003", date: "2025/04/02", region: "القاهرة", pm25: 20.1, pm10: 42.0 },
        { id: "C-004", date: "2025/04/02", region: "القليوبية", pm25: 15.6, pm10: 31.9 },
      ]}
      columns={[
        { key: "id", header: "معرف المحطة" },
        { key: "date", header: "التاريخ", numeric: true },
        { key: "region", header: "المنطقة الجغرافية" },
        { key: "pm25", header: "تركيز PM2_5", numeric: true },
        { key: "pm10", header: "تركيز PM10", numeric: true },
      ]}
    />
  </div>
);

export const Empty = () => (
  <div style={{ maxWidth: 480 }}>
    <DataTable rows={[]} columns={[{ key: "a", header: "الاسم" }, { key: "b", header: "الحالة" }]} empty="لا توجد تحليلات بعد" />
  </div>
);

import * as React from "react";
import { CategoryTile } from "@khepri/ds";

export const LibraryFilters = () => (
  <div className="k-grid-3" style={{ maxWidth: 640 }}>
    <CategoryTile active icon="grid" label="الكل" count="24 تحليل" />
    <CategoryTile icon="trend-up" tone="blue" label="تحليل السوق" count="6 تحليلات" />
    <CategoryTile icon="coins" tone="amber" label="التسعير والتعرفة" count="5 تحليلات" />
    <CategoryTile icon="cog" tone="green" label="الاتجاهات التشغيلية" count="7 تحليلات" />
    <CategoryTile icon="scenario" tone="red" label="مقارنة السيناريوهات" count="4 تحليلات" />
    <CategoryTile icon="file" tone="blue" label="السياسات والأثر" count="2 تحليل" />
  </div>
);

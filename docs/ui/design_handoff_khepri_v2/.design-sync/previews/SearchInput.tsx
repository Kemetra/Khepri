import * as React from "react";
import { SearchInput } from "@khepri/ds";

export const LibrarySearch = () => (
  <div style={{ maxWidth: 320 }}>
    <SearchInput placeholder="البحث في مكتبة التحليلات..." />
  </div>
);

export const WithValue = () => (
  <div style={{ maxWidth: 320 }}>
    <SearchInput placeholder="ابحث في الأدلة والمصادر..." defaultValue="الطاقة المتجددة" />
  </div>
);

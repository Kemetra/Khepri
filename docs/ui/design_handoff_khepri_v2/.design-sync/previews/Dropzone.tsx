import * as React from "react";
import { Dropzone } from "@khepri/ds";

export const Default = () => (
  <div style={{ maxWidth: 640 }}>
    <Dropzone />
  </div>
);

export const SpreadsheetsOnly = () => (
  <div style={{ maxWidth: 420 }}>
    <Dropzone
      formats={[{ kind: "csv", limit: "حتى 500 ميجابايت" }, { kind: "xlsx", limit: "حتى 500 ميجابايت" }]}
      note="يفضل أن تكون البيانات منظمة في ورقة واحدة"
    />
  </div>
);

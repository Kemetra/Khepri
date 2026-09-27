import * as React from "react";
import { IconButton } from "@khepri/ds";

export const Plain = () => (
  <div className="k-row">
    <IconButton icon="more" label="خيارات" />
    <IconButton icon="x" label="إغلاق" />
    <IconButton icon="edit" label="تعديل" />
    <IconButton icon="bell" label="الإشعارات" />
    <IconButton icon="help" label="المساعدة" />
  </div>
);

export const Outlined = () => (
  <div className="k-row">
    <IconButton icon="more" label="خيارات" variant="outlined" />
    <IconButton icon="print" label="طباعة" variant="outlined" />
    <IconButton icon="share" label="مشاركة" variant="outlined" />
    <IconButton icon="more" label="خيارات" variant="outlined" size="sm" />
  </div>
);

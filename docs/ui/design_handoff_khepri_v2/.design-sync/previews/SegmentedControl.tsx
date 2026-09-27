import * as React from "react";
import { SegmentedControl } from "@khepri/ds";

export const ViewSwitch = () => (
  <SegmentedControl
    value="cards"
    options={[{ value: "cards", label: "بطاقات", icon: "grid" }, { value: "table", label: "جدولي", icon: "list" }]}
  />
);

export const Periods = () => (
  <SegmentedControl
    value="12m"
    options={[{ value: "30d", label: "30 يوماً" }, { value: "6m", label: "6 أشهر" }, { value: "12m", label: "12 شهراً" }]}
  />
);

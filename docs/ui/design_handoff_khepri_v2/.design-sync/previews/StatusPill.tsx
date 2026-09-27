import * as React from "react";
import { StatusPill } from "@khepri/ds";

export const WorkflowStates = () => (
  <div className="k-row">
    <StatusPill status="complete" />
    <StatusPill status="running" />
    <StatusPill status="review" />
    <StatusPill status="stopped" />
    <StatusPill status="draft" />
  </div>
);

export const QueueAndPublish = () => (
  <div className="k-row">
    <StatusPill status="queued" />
    <StatusPill status="waiting" />
    <StatusPill status="warning" />
    <StatusPill status="published" />
    <StatusPill status="compatible" />
  </div>
);

export const SmallAndCustom = () => (
  <div className="k-row">
    <StatusPill status="complete" size="sm" />
    <StatusPill status="running" label="قيد المعالجة" size="sm" />
    <StatusPill tone="red" label="حرجة" size="sm" />
    <StatusPill tone="amber" label="متوسطة" size="sm" />
    <StatusPill tone="blue" label="طفيفة" size="sm" />
  </div>
);

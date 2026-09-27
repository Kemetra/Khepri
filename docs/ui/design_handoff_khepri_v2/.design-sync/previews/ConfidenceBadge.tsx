import * as React from "react";
import { ConfidenceBadge } from "@khepri/ds";

export const Levels = () => (
  <div className="k-row">
    <ConfidenceBadge value={92} />
    <ConfidenceBadge value={75} />
    <ConfidenceBadge value={52} />
  </div>
);

export const ForcedLevel = () => <ConfidenceBadge value={68} level="medium" />;

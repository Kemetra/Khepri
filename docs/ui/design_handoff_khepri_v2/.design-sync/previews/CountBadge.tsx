import * as React from "react";
import { CountBadge } from "@khepri/ds";

export const Soft = () => (
  <div className="k-row">
    <CountBadge value={4} />
    <CountBadge value={12} tone="gold" />
    <CountBadge value={7} tone="blue" />
    <CountBadge value={3} tone="green" />
  </div>
);

export const SolidRanks = () => (
  <div className="k-row">
    <CountBadge value={1} tone="green" variant="solid" />
    <CountBadge value={2} tone="blue" variant="solid" />
    <CountBadge value={3} tone="amber" variant="solid" />
    <CountBadge value={4} tone="purple" variant="solid" />
  </div>
);

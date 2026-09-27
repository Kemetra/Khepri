import * as React from "react";
import { IconBadge } from "@khepri/ds";

export const Tones = () => (
  <div className="k-row">
    <IconBadge icon="file" tone="sky" />
    <IconBadge icon="lightbulb" tone="amber" />
    <IconBadge icon="database" tone="blue" />
    <IconBadge icon="check-circle" tone="green" />
    <IconBadge icon="alert" tone="red" />
    <IconBadge icon="hash" tone="purple" />
    <IconBadge icon="coins" tone="gold" />
  </div>
);

export const Sizes = () => (
  <div className="k-row">
    <IconBadge icon="leaf" tone="green" size="sm" />
    <IconBadge icon="leaf" tone="green" size="md" />
    <IconBadge icon="leaf" tone="green" size="lg" />
  </div>
);

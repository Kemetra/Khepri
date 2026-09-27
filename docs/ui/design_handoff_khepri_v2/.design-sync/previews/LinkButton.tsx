import * as React from "react";
import { LinkButton } from "@khepri/ds";

export const CardLinks = () => (
  <div className="k-row" style={{ gap: 24 }}>
    <LinkButton>عرض الكل</LinkButton>
    <LinkButton>عرض التفاصيل</LinkButton>
    <LinkButton>عرض جميع المهام</LinkButton>
  </div>
);

export const GoldAndPlain = () => (
  <div className="k-row" style={{ gap: 24 }}>
    <LinkButton tone="gold">عرض المصدر</LinkButton>
    <LinkButton chevron={false}>عرض الكل</LinkButton>
  </div>
);

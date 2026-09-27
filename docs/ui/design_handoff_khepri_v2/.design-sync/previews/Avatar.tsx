import * as React from "react";
import { Avatar } from "@khepri/ds";

export const Initials = () => (
  <div className="k-row">
    <Avatar name="سارة أحمد" size={40} />
    <Avatar name="محمد علي" size={40} />
    <Avatar name="د. نادية حسن" size={40} />
    <Avatar name="أحمد خالد" size={40} />
  </div>
);

export const Sizes = () => (
  <div className="k-row">
    <Avatar name="سارة أحمد" size={24} />
    <Avatar name="سارة أحمد" size={32} />
    <Avatar name="سارة أحمد" size={48} />
  </div>
);

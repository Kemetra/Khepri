import * as React from "react";
import { AvatarGroup } from "@khepri/ds";

const team = [
  { name: "سارة أحمد" }, { name: "محمد علي" }, { name: "د. نادية حسن" }, { name: "أحمد خالد" }, { name: "ليلى محمود" },
];

export const Collaborators = () => <AvatarGroup people={team} size={36} />;

export const AllShown = () => <AvatarGroup people={team.slice(0, 3)} max={3} />;

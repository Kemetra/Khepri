import * as React from "react";

export interface AvatarProps {
  /** Person's name; used for alt text and the initials fallback. */
  name: string;
  /** Photo URL. When absent, initials on a sand circle are shown. */
  src?: string;
  /** Diameter in px. Default 32. */
  size?: number;
}

function initials(name: string): string {
  const parts = name.replace(/^د\.\s*/, "").trim().split(/\s+/);
  return parts.slice(0, 2).map((p) => p.charAt(0)).join(" ");
}

/** Round user avatar - photo, or initials on a sand circle. */
export function Avatar({ name, src, size = 32 }: AvatarProps) {
  const style = { width: size, height: size, fontSize: Math.round(size * 0.36) };
  return src ? (
    <img className="k-avatar" src={src} alt={name} style={style} />
  ) : (
    <span className="k-avatar k-avatar--initials" style={style} role="img" aria-label={name}>
      {initials(name)}
    </span>
  );
}

export interface AvatarGroupProps {
  people: Array<{ name: string; src?: string }>;
  /** How many avatars to show before collapsing into "+N". Default 3. */
  max?: number;
  size?: number;
}

/** Overlapping avatar stack with a "+N" overflow chip (report collaborators). */
export function AvatarGroup({ people, max = 3, size = 32 }: AvatarGroupProps) {
  const shown = people.slice(0, max);
  const rest = people.length - shown.length;
  return (
    <span className="k-avatar-group">
      {shown.map((p) => (
        <Avatar key={p.name} name={p.name} src={p.src} size={size} />
      ))}
      {rest > 0 ? (
        <span className="k-avatar k-avatar--more" style={{ width: size, height: size, fontSize: Math.round(size * 0.36) }}>
          +{rest}
        </span>
      ) : null}
    </span>
  );
}

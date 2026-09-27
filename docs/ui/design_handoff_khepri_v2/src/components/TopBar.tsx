import * as React from "react";
import { Icon } from "./Icon";
import { Avatar } from "./Avatar";

export interface TopBarUser {
  name: string;
  role?: string;
  /** Avatar image URL; initials are shown when absent. */
  avatarUrl?: string;
}

export interface TopBarWorkspace {
  /** Arabic workspace name, e.g. "البيئة والسياسات العامة". */
  name: string;
  /** Secondary (usually English) line. */
  subtitle?: string;
}

export interface TopBarProps {
  /** Placeholder for the global search field. */
  searchPlaceholder?: string;
  onSearch?: (query: string) => void;
  /** Current workspace shown in the switcher. */
  workspace?: TopBarWorkspace;
  onWorkspaceClick?: () => void;
  /** Signed-in user shown at the inline-end edge. */
  user?: TopBarUser;
  /** Show the unread dot on the bell. */
  hasNotifications?: boolean;
  /** Extra controls placed before the icon buttons. */
  actions?: React.ReactNode;
}

/**
 * Application top bar: global search (inline-start), workspace switcher, and the
 * help / notifications / user cluster (inline-end).
 */
export function TopBar({
  searchPlaceholder = "البحث في البيانات، التحليلات، الأدلة...", onSearch, workspace, onWorkspaceClick,
  user, hasNotifications, actions,
}: TopBarProps) {
  return (
    <div className="k-topbar">
      <label className="k-topbar__search">
        <Icon name="search" size={18} />
        <input
          type="search"
          placeholder={searchPlaceholder}
          onChange={(e) => onSearch?.(e.target.value)}
          aria-label="بحث"
        />
      </label>
      {workspace ? (
        <button type="button" className="k-topbar__workspace" onClick={onWorkspaceClick}>
          <span className="k-topbar__ws-icon"><Icon name="building" size={18} /></span>
          <span className="k-topbar__ws-text">
            <strong>{workspace.name}</strong>
            {workspace.subtitle ? <small>{workspace.subtitle}</small> : null}
          </span>
          <Icon name="chevron-down" size={16} />
        </button>
      ) : null}
      <div className="k-topbar__end">
        {actions}
        <button type="button" className="k-topbar__icon" aria-label="المساعدة"><Icon name="help" /></button>
        <button type="button" className="k-topbar__icon" aria-label="الإشعارات">
          <Icon name="bell" />
          {hasNotifications ? <span className="k-topbar__dot" /> : null}
        </button>
        {user ? (
          <span className="k-topbar__user">
            <Avatar name={user.name} src={user.avatarUrl} size={36} />
            <span className="k-topbar__user-text">
              <strong>{user.name}</strong>
              {user.role ? <small>{user.role}</small> : null}
            </span>
          </span>
        ) : null}
      </div>
    </div>
  );
}

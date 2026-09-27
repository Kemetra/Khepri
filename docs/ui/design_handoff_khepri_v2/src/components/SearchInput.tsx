import * as React from "react";
import { Icon } from "./Icon";

export interface SearchInputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "type" | "size"> {
  /** Default "ابحث...". */
  placeholder?: string;
}

/** Grey rounded search box with a magnifier - page-level filters ("البحث في مكتبة التحليلات..."). */
export function SearchInput({ placeholder = "ابحث...", ...rest }: SearchInputProps) {
  return (
    <label className="k-search">
      <Icon name="search" size={18} />
      <input type="search" placeholder={placeholder} aria-label={placeholder} {...rest} />
    </label>
  );
}

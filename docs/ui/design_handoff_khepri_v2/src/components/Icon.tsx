import * as React from "react";
import {
  AlertTriangle, ArrowDown, ArrowLeft, ArrowUp, BarChart3, Bell, Bot, Building2, Calendar, Check,
  CheckCircle2, ChevronDown, ChevronLeft, ChevronRight, CircleStop, Clock, Cog, Coins, Database,
  Download, ExternalLink, Eye, FileArchive, FileBarChart2, FileSpreadsheet, FileText, Filter, Folder,
  Gauge, GitFork, Globe, GraduationCap, GripVertical, Hash, HelpCircle, History, Home, Image, Info,
  Layers, LayoutGrid, Leaf, Lightbulb, LineChart, Link, List, Loader2, Map, MoreHorizontal, Newspaper,
  Paperclip, Pencil, PieChart, Pin, Play, Plus, Printer, Quote, RotateCw, Save, Search, Settings,
  Share2, ShieldCheck, Sparkles, Star, Table, Target, TrendingDown, TrendingUp, Upload, UploadCloud,
  UserPlus, Users, X, Zap,
} from "lucide-react";

const ICONS = {
  alert: AlertTriangle, "arrow-down": ArrowDown, "arrow-left": ArrowLeft, "arrow-up": ArrowUp,
  analyses: BarChart3, bell: Bell, bot: Bot, building: Building2, calendar: Calendar, check: Check,
  "check-circle": CheckCircle2, "chevron-down": ChevronDown, "chevron-left": ChevronLeft,
  "chevron-right": ChevronRight, stop: CircleStop, clock: Clock, cog: Cog, coins: Coins,
  database: Database, download: Download, external: ExternalLink, eye: Eye, "file-zip": FileArchive,
  report: FileBarChart2, "file-sheet": FileSpreadsheet, file: FileText, filter: Filter, folder: Folder,
  gauge: Gauge, scenario: GitFork, globe: Globe, academic: GraduationCap, grip: GripVertical,
  hash: Hash, help: HelpCircle, history: History, home: Home, image: Image, info: Info,
  layers: Layers, grid: LayoutGrid, leaf: Leaf, lightbulb: Lightbulb, "line-chart": LineChart,
  link: Link, list: List, loader: Loader2, map: Map, more: MoreHorizontal, news: Newspaper,
  attach: Paperclip, edit: Pencil, "pie-chart": PieChart, pin: Pin, play: Play, plus: Plus,
  print: Printer, quote: Quote, retry: RotateCw, save: Save, search: Search, settings: Settings,
  share: Share2, shield: ShieldCheck, sparkles: Sparkles, star: Star, table: Table, target: Target,
  "trend-down": TrendingDown, "trend-up": TrendingUp, upload: Upload, "upload-cloud": UploadCloud,
  "user-plus": UserPlus, users: Users, x: X, zap: Zap,
} as const;

/** Every icon name accepted by `Icon` and by the `icon` prop of Khepri components. */
export type IconName = keyof typeof ICONS;

/** All available icon names, for pickers and docs. */
export const iconNames = Object.keys(ICONS) as IconName[];

export interface IconProps {
  /** Icon to draw (Khepri's curated line-icon set). */
  name: IconName;
  /** Pixel size (width and height). Default 18. */
  size?: number;
  /** Stroke width. Default 1.75, matching the mockups' thin line icons. */
  strokeWidth?: number;
  className?: string;
  /** Accessible label; when omitted the icon is decorative (aria-hidden). */
  label?: string;
}

/**
 * Khepri line icon. Pass a curated `name` (e.g. "database", "analyses", "lightbulb").
 * Icons inherit `currentColor`, so colour them with the parent's text colour.
 */
export function Icon({ name, size = 18, strokeWidth = 1.75, className, label }: IconProps) {
  const Glyph = ICONS[name];
  return (
    <Glyph
      size={size}
      strokeWidth={strokeWidth}
      className={className}
      aria-hidden={label ? undefined : true}
      aria-label={label}
      role={label ? "img" : undefined}
    />
  );
}

/** Renders an icon name or passes through a custom node. Internal helper. */
export function renderIcon(icon: IconName | React.ReactNode | undefined, size = 18) {
  if (icon == null || icon === false) return null;
  if (typeof icon === "string") return <Icon name={icon as IconName} size={size} />;
  return icon;
}

import { cn } from "@/lib/utils";
import type { ItemStatus, TransferStatus, TransferPriority } from "@/types";

// ─── StatCard ────────────────────────────────────────────────
interface StatCardProps {
  label: string;
  value: string | number;
  sub?: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
}
export function StatCard({ label, value, sub, icon, className }: StatCardProps) {
  return (
    <div className={cn("bg-white border border-border rounded-xl p-4", className)}>
      <div className="flex items-center gap-2 text-[11px] font-medium text-muted-foreground uppercase tracking-wide mb-2">
        {icon}
        {label}
      </div>
      <div className="text-2xl font-semibold font-mono text-foreground leading-none">
        {value}
      </div>
      {sub && <div className="text-[11px] text-muted-foreground mt-2">{sub}</div>}
    </div>
  );
}

// ─── Badge variants ──────────────────────────────────────────
type BadgeVariant = "blue" | "green" | "amber" | "red" | "purple" | "gray";

const badgeStyles: Record<BadgeVariant, string> = {
  blue: "bg-blue-50 text-blue-700 border-blue-200",
  green: "bg-green-50 text-green-700 border-green-200",
  amber: "bg-amber-50 text-amber-700 border-amber-200",
  red: "bg-red-50 text-red-700 border-red-200",
  purple: "bg-purple-50 text-purple-700 border-purple-200",
  gray: "bg-gray-100 text-gray-600 border-gray-200",
};

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  className?: string;
}
export function Badge({ children, variant = "blue", className }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium border",
        badgeStyles[variant],
        className
      )}
    >
      {children}
    </span>
  );
}

// ─── Status Badge helpers ─────────────────────────────────────
export function ItemStatusBadge({ status }: { status: ItemStatus }) {
  const map: Record<ItemStatus, { label: string; variant: BadgeVariant }> = {
    ok: { label: "Pietiekams", variant: "green" },
    low: { label: "Zems", variant: "amber" },
    critical: { label: "Kritisks", variant: "red" },
  };
  const { label, variant } = map[status];
  return <Badge variant={variant}>{label}</Badge>;
}

export function TransferStatusBadge({ status }: { status: TransferStatus }) {
  const map: Record<TransferStatus, { label: string; variant: BadgeVariant }> = {
    pending: { label: "Gaida", variant: "amber" },
    "in-transit": { label: "Ceļā", variant: "blue" },
    done: { label: "Pabeigts", variant: "green" },
    cancelled: { label: "Atcelts", variant: "gray" },
  };
  const { label, variant } = map[status];
  return <Badge variant={variant}>{label}</Badge>;
}

export function PriorityBadge({ priority }: { priority: TransferPriority }) {
  const map: Record<TransferPriority, { label: string; variant: BadgeVariant }> = {
    normal: { label: "Parasta", variant: "gray" },
    high: { label: "Augsta", variant: "amber" },
    urgent: { label: "Steidzama", variant: "red" },
  };
  const { label, variant } = map[priority];
  return <Badge variant={variant}>{label}</Badge>;
}

// ─── Card ────────────────────────────────────────────────────
interface CardProps {
  children: React.ReactNode;
  className?: string;
}
export function Card({ children, className }: CardProps) {
  return (
    <div className={cn("bg-white border border-border rounded-xl overflow-hidden", className)}>
      {children}
    </div>
  );
}

export function CardHeader({ children, className }: CardProps) {
  return (
    <div className={cn("px-4 py-3 border-b border-border flex items-center gap-3", className)}>
      {children}
    </div>
  );
}

export function CardTitle({ children, className }: CardProps) {
  return (
    <h3 className={cn("text-[13px] font-semibold text-foreground flex-1", className)}>
      {children}
    </h3>
  );
}

// ─── Button ──────────────────────────────────────────────────
type ButtonVariant = "default" | "primary" | "danger" | "ghost";
type ButtonSize = "sm" | "md";

const buttonStyles: Record<ButtonVariant, string> = {
  default: "border border-border bg-white text-foreground hover:bg-secondary",
  primary: "border border-blue-600 bg-blue-600 text-white hover:bg-blue-700",
  danger: "border border-red-200 bg-red-50 text-red-700 hover:bg-red-100",
  ghost: "border-transparent bg-transparent text-muted-foreground hover:bg-secondary hover:text-foreground",
};

const sizeStyles: Record<ButtonSize, string> = {
  sm: "px-2.5 py-1 text-[11px] gap-1.5",
  md: "px-3.5 py-1.5 text-[12px] gap-2",
};

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  children: React.ReactNode;
}
export function Button({
  variant = "default",
  size = "md",
  isLoading,
  children,
  className,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      {...props}
      disabled={disabled || isLoading}
      className={cn(
        "inline-flex items-center justify-center rounded-md font-medium transition-colors border",
        buttonStyles[variant],
        sizeStyles[size],
        (disabled || isLoading) && "opacity-50 cursor-not-allowed",
        className
      )}
    >
      {isLoading ? (
        <span className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
      ) : null}
      {children}
    </button>
  );
}

// ─── StockBar ────────────────────────────────────────────────
export function StockBar({ stock, minStock }: { stock: number; minStock: number }) {
  const pct = Math.min(100, Math.round((stock / Math.max(minStock * 3, 50)) * 100));
  const color =
    stock <= Math.floor(minStock * 0.3)
      ? "bg-red-500"
      : stock < minStock
      ? "bg-amber-500"
      : "bg-green-500";
  return (
    <div className="w-20 h-1.5 bg-border rounded-full overflow-hidden">
      <div className={cn("h-full rounded-full transition-all", color)} style={{ width: `${pct}%` }} />
    </div>
  );
}

// ─── Empty State ─────────────────────────────────────────────
export function EmptyState({ message = "Datu nav" }: { message?: string }) {
  return (
    <div className="py-16 flex flex-col items-center gap-2 text-muted-foreground">
      <span className="text-4xl">📭</span>
      <p className="text-sm">{message}</p>
    </div>
  );
}

// ─── Loading Spinner ─────────────────────────────────────────
export function LoadingSpinner({ className }: { className?: string }) {
  return (
    <div className={cn("flex justify-center items-center py-12", className)}>
      <div className="w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

// ─── Section Header ──────────────────────────────────────────
export function SectionHeader({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-4 mb-6">
      <div className="flex-1">
        <h2 className="text-lg font-semibold text-foreground">{title}</h2>
        {subtitle && <p className="text-[13px] text-muted-foreground mt-0.5">{subtitle}</p>}
      </div>
      {children && <div className="flex items-center gap-2">{children}</div>}
    </div>
  );
}

// ─── Alert ───────────────────────────────────────────────────
type AlertVariant2 = "info" | "warning" | "error" | "success";
const alertStyles: Record<AlertVariant2, string> = {
  info: "bg-blue-50 border-blue-200 text-blue-800",
  warning: "bg-amber-50 border-amber-200 text-amber-800",
  error: "bg-red-50 border-red-200 text-red-800",
  success: "bg-green-50 border-green-200 text-green-800",
};
export function Alert({
  variant = "info",
  children,
}: {
  variant?: AlertVariant2;
  children: React.ReactNode;
}) {
  return (
    <div className={cn("flex gap-3 px-4 py-3 rounded-lg border text-[13px] mb-2 last:mb-0", alertStyles[variant])}>
      {children}
    </div>
  );
}

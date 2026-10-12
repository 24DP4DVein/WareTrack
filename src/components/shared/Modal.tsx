"use client";

import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "./ui";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  size?: "sm" | "md" | "lg";
}

const sizeMap = {
  sm: "max-w-sm",
  md: "max-w-lg",
  lg: "max-w-2xl",
};

export default function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  size = "md",
}: ModalProps) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        className={cn(
          "bg-white rounded-xl shadow-2xl w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150",
          sizeMap[size]
        )}
      >
        {/* Header */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-border">
          <div className="flex-1">
            <h2 className="text-[15px] font-semibold text-foreground">{title}</h2>
            {description && (
              <p className="text-[12px] text-muted-foreground mt-0.5">{description}</p>
            )}
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 rounded-md flex items-center justify-center text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors"
          >
            <X size={15} />
          </button>
        </div>

        {/* Body */}
        <div className="p-5 max-h-[70vh] overflow-y-auto">{children}</div>

        {/* Footer */}
        {footer && (
          <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-border bg-secondary/30">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Form helpers ─────────────────────────────────────────────
export function FormField({
  label,
  error,
  required,
  children,
  className,
}: {
  label: string;
  error?: string;
  required?: boolean;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label className="text-[12px] font-medium text-muted-foreground">
        {label}
        {required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      {children}
      {error && <p className="text-[11px] text-red-600">{error}</p>}
    </div>
  );
}

export const inputClass =
  "w-full border border-border rounded-md px-3 py-2 text-[13px] text-foreground bg-white outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition placeholder:text-muted-foreground";

export const selectClass =
  "w-full border border-border rounded-md px-3 py-2 text-[13px] text-foreground bg-white outline-none focus:border-blue-500 transition";

export const textareaClass =
  "w-full border border-border rounded-md px-3 py-2 text-[13px] text-foreground bg-white outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition resize-y min-h-[80px] placeholder:text-muted-foreground";

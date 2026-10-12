"use client";

import { useAppStore } from "@/store/useAppStore";
import { cn } from "@/lib/utils";
import { CheckCircle2, AlertTriangle, XCircle, Info, X } from "lucide-react";

const icons = {
  success: <CheckCircle2 size={15} className="text-green-500 flex-shrink-0" />,
  warning: <AlertTriangle size={15} className="text-amber-500 flex-shrink-0" />,
  error: <XCircle size={15} className="text-red-500 flex-shrink-0" />,
  info: <Info size={15} className="text-blue-500 flex-shrink-0" />,
};

export default function ToastContainer() {
  const toasts = useAppStore((s) => s.toasts);
  const removeToast = useAppStore((s) => s.removeToast);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-6 right-6 z-[9999] flex flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={cn(
            "flex items-center gap-3 bg-[#1a1916] text-white px-4 py-3 rounded-xl shadow-xl text-[13px] min-w-[260px] max-w-[360px] animate-in slide-in-from-right-4 fade-in duration-200"
          )}
        >
          {icons[t.type]}
          <span className="flex-1">{t.message}</span>
          <button
            onClick={() => removeToast(t.id)}
            className="text-white/40 hover:text-white/80 transition-colors"
          >
            <X size={13} />
          </button>
        </div>
      ))}
    </div>
  );
}

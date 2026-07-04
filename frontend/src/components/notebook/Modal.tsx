import React, { useEffect } from "react";
import { X } from "lucide-react";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: React.ReactNode;
  children: React.ReactNode;
  /** Ancho máximo de la caja (clase Tailwind). */
  maxWidth?: string;
}

/**
 * Modal — diálogo con estética cuaderno: overlay difuminado + caja de papel con
 * borde a lápiz y sombra dura. Cierra con Esc, click en el fondo o el botón ×.
 */
export default function Modal({ open, onClose, title, children, maxWidth = "max-w-lg" }: ModalProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 bg-stone-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className={`bg-[#faf6ee] rounded-xl p-6 w-full ${maxWidth} border-2 border-[#1e1814] shadow-[8px_8px_0px_#1e1814] relative max-h-[88vh] overflow-y-auto`}
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          className="absolute top-3 right-3 p-1.5 rounded-lg text-stone-500 hover:text-stone-900 hover:bg-stone-200/60 cursor-pointer transition-colors"
          aria-label="Cerrar"
        >
          <X className="w-5 h-5" />
        </button>
        {title && (
          <h3 className="text-2xl font-hand font-bold text-stone-900 leading-tight mb-3 pr-8">{title}</h3>
        )}
        {children}
      </div>
    </div>
  );
}

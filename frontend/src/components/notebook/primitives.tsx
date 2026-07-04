import React from "react";

/**
 * primitives — piezas básicas del tema "cuaderno científico".
 * Botones a lápiz, tarjetas de papel, etiquetas, encabezados manuscritos, divisores
 * garabateados, cargador químico y estado vacío. Reutilizadas por todas las páginas.
 */

// ── Botón a lápiz ──────────────────────────────────────────────────────────────
type BtnProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "solid" | "outline";
  icon?: React.ReactNode;
};
export function PencilButton({ variant = "outline", icon, children, className = "", ...rest }: BtnProps) {
  const base =
    "inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl font-hand font-bold text-base border-2 transition-all cursor-pointer active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed";
  const skin =
    variant === "solid"
      ? "bg-[#2d2621] text-[#faf6ee] border-[#1e1814] shadow-[2.5px_2.5px_0px_#1e1814] hover:bg-[#3d332d]"
      : "bg-white text-[#3a332a] border-[#3f3429] shadow-[1.5px_2px_0px_#27211b] hover:bg-stone-50";
  return (
    <button className={`${base} ${skin} ${className}`} {...rest}>
      {icon}
      {children}
    </button>
  );
}

// ── Tarjeta de papel ───────────────────────────────────────────────────────────
export function NotebookCard({
  children,
  className = "",
  selected = false,
  onClick,
}: {
  children: React.ReactNode;
  className?: string;
  selected?: boolean;
  onClick?: () => void;
}) {
  const sel = selected
    ? "border-[#1e1915] shadow-[4px_4.5px_0px_#1e1915] bg-[#faf6ee]"
    : "border-stone-800/20 hover:border-stone-800/40 shadow-[2px_2.5px_0px_rgba(30,25,21,0.08)] hover:shadow-[3px_3.5px_0px_rgba(30,25,21,0.14)] bg-[#faf6ee]/80 hover:bg-[#faf6ee]";
  return (
    <div
      onClick={onClick}
      className={`rounded-xl p-5 border-2 transition-all duration-150 ${onClick ? "cursor-pointer" : ""} ${sel} ${className}`}
    >
      {children}
    </div>
  );
}

// ── Etiqueta / badge ───────────────────────────────────────────────────────────
type TagTone = "blue" | "green" | "amber" | "orange" | "red" | "neutral";
const TAG_TONES: Record<TagTone, string> = {
  blue: "bg-blue-100 text-sky-800 border-sky-400/30",
  green: "bg-emerald-100 text-emerald-800 border-emerald-400/30",
  amber: "bg-amber-100 text-amber-900 border-amber-400/30",
  orange: "bg-orange-100 text-orange-800 border-orange-400/30",
  red: "bg-red-100 text-red-800 border-red-400/30",
  neutral: "bg-stone-100 text-stone-700 border-stone-400/30",
};
export function Tag({ tone = "neutral", children }: { tone?: TagTone; children: React.ReactNode }) {
  return (
    <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md border font-mono ${TAG_TONES[tone]}`}>
      {children}
    </span>
  );
}

/** Mapea un grupo/estado de fármaco a un tono de etiqueta. */
export function groupTone(group: string): TagTone {
  const g = group.toLowerCase();
  if (g === "approved") return "green";
  if (g === "withdrawn") return "amber";
  if (g.includes("investiga") || g.includes("experimental")) return "orange";
  return "neutral";
}

// ── Encabezado de sección (subrayado mono) ──────────────────────────────────────
export function SectionHeader({ children, tone = "#7c2d12" }: { children: React.ReactNode; tone?: string }) {
  return (
    <h4
      className="text-sm font-bold font-mono tracking-wider pb-0.5 inline-block mb-2"
      style={{ color: tone, borderBottom: `1px solid ${tone}33` }}
    >
      {children}
    </h4>
  );
}

// ── Título manuscrito ───────────────────────────────────────────────────────────
export function HandTitle({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <h1 className={`font-hand font-bold tracking-tight text-[#1a140f] ${className}`}>{children}</h1>;
}

// ── Divisor garabateado ─────────────────────────────────────────────────────────
export function Scribble({ width = 60 }: { width?: number }) {
  return (
    <div className="flex justify-center my-4 opacity-40">
      <svg width={width} height="10" viewBox="0 0 100 20" fill="none">
        <path d="M 10 10 Q 30 0, 50 10 T 90 10" stroke="#000" strokeWidth="1.5" strokeLinecap="round" filter="url(#handdrawn-sketch)" />
      </svg>
    </div>
  );
}

// ── Cargador químico (hexágono girando) ─────────────────────────────────────────
export function Loader({ label }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-10 text-center select-none">
      <svg className="w-14 h-14 text-[#dd6b20] animate-spin-slow mb-3" viewBox="0 0 50 50" filter="url(#handdrawn-sketch)">
        <polygon points="25,5 45,15 45,35 25,45 5,35 5,15" stroke="currentColor" strokeWidth="2.5" fill="none" />
        <line x1="25" y1="5" x2="25" y2="45" stroke="currentColor" strokeWidth="1.2" />
        <line x1="45" y1="15" x2="5" y2="35" stroke="currentColor" strokeWidth="1.2" />
        <line x1="5" y1="15" x2="45" y2="35" stroke="currentColor" strokeWidth="1.2" />
        <circle cx="25" cy="25" r="4.5" fill="currentColor" />
      </svg>
      {label && <p className="text-sm font-hand text-stone-600">{label}</p>}
    </div>
  );
}

// ── Campo de entrada cuaderno ──────────────────────────────────────────────────
type InputProps = React.InputHTMLAttributes<HTMLInputElement> & { label?: string };
export function NotebookInput({ label, className = "", ...rest }: InputProps) {
  return (
    <div className="flex flex-col gap-1">
      {label && <label className="text-xs font-mono font-bold text-stone-600 tracking-wide">{label}</label>}
      <input
        className={`px-3 py-2 rounded-lg border-2 border-stone-800/20 bg-[#faf6ee] font-hand text-[#1a140f] text-sm placeholder:text-stone-500 focus:outline-none focus:border-[#3f3429] focus:shadow-[1.5px_2px_0px_#27211b] transition-all ${className}`}
        {...rest}
      />
    </div>
  );
}

// ── Barra de pestañas ───────────────────────────────────────────────────────────
export function TabBar<T extends string>({
  tabs,
  active,
  onChange,
}: {
  tabs: { id: T; label: React.ReactNode }[];
  active: T;
  onChange: (id: T) => void;
}) {
  return (
    <div className="flex gap-1 border-b-2 border-stone-200 mb-4">
      {tabs.map(({ id, label }) => (
        <button
          key={id}
          onClick={() => onChange(id)}
          className={`px-4 py-2 text-sm font-hand font-bold transition-all border-b-2 -mb-[2px] ${
            active === id
              ? "border-[#1e1915] text-[#1a140f]"
              : "border-transparent text-stone-500 hover:text-stone-700"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

// ── Estado vacío ────────────────────────────────────────────────────────────────
export function EmptyState({ title, hint, icon }: { title: string; hint?: string; icon?: React.ReactNode }) {
  return (
    <div className="flex-1 bg-amber-500/5 rounded-2xl border-2 border-dashed border-stone-300 p-10 flex flex-col items-center justify-center text-center select-none">
      {icon}
      <h4 className="text-xl font-bold font-hand text-stone-700 mt-2">{title}</h4>
      {hint && <p className="text-xs text-stone-500 font-hand max-w-sm mt-1">{hint}</p>}
    </div>
  );
}

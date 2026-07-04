import React, { useState } from 'react';

export interface Section {
  id: string;
  icon: string;
  title: string;
  content: React.ReactNode;
}

// ── Bloques de contenido reutilizables (tema cuaderno) ────────────────────────

export function H2({ children }: { children: React.ReactNode }) {
  return <h2 className="text-[#1a140f] text-xl font-hand font-bold mb-3 pb-2 border-b-2 border-stone-800/15">{children}</h2>;
}

export function H3({ children }: { children: React.ReactNode }) {
  return <h3 className="text-amber-800 text-base font-bold mt-5 mb-2">{children}</h3>;
}

export function P({ children }: { children: React.ReactNode }) {
  return <p className="text-stone-600 text-[0.9rem] leading-relaxed mb-2.5">{children}</p>;
}

export function Code({ children }: { children: React.ReactNode }) {
  return <code className="bg-stone-100 border border-stone-300 text-sky-800 px-1.5 py-px rounded font-mono text-[0.82rem]">{children}</code>;
}

export function CodeBlock({ children, lang = '' }: { children: string; lang?: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => { navigator.clipboard.writeText(children.trim()); setCopied(true); setTimeout(() => setCopied(false), 1500); };
  return (
    <div className="relative my-2.5">
      <pre className="bg-[#2b2620] border-2 border-stone-800/30 rounded-lg px-4 py-3.5 overflow-x-auto text-[0.8rem] font-mono text-stone-100 leading-relaxed m-0">
        {lang && <span className="text-stone-500 block mb-1.5 text-[0.7rem]">{lang}</span>}
        {children.trim()}
      </pre>
      <button onClick={copy} className={`absolute top-2 right-2 px-2 py-0.5 rounded-md text-[0.7rem] cursor-pointer border ${copied ? 'bg-emerald-700 border-emerald-500 text-emerald-100' : 'bg-stone-700 border-stone-600 text-stone-300'}`}>
        {copied ? '✓ Copiado' : 'Copiar'}
      </button>
    </div>
  );
}

export function Note({ children, type = 'info' }: { children: React.ReactNode; type?: 'info' | 'warning' | 'tip' }) {
  const styles = {
    info: 'bg-sky-50 border-sky-300 text-sky-800',
    warning: 'bg-amber-50 border-amber-300 text-amber-800',
    tip: 'bg-emerald-50 border-emerald-300 text-emerald-800',
  };
  const icon = { info: 'ℹ', warning: '⚠', tip: '✦' }[type];
  return (
    <div className={`border rounded-lg px-3.5 py-2.5 my-2.5 flex gap-2.5 items-start ${styles[type]}`}>
      <span className="font-bold shrink-0">{icon}</span>
      <span className="text-stone-700 text-[0.85rem] leading-relaxed">{children}</span>
    </div>
  );
}

export function Table({ headers, rows }: { headers: string[]; rows: (string | React.ReactNode)[][] }) {
  return (
    <div className="overflow-x-auto my-2.5 rounded-lg border-2 border-stone-800/15">
      <table className="w-full border-collapse text-[0.85rem]">
        <thead>
          <tr>{headers.map((h) => <th key={h} className="bg-[#efe7d6] text-stone-600 px-3 py-2 text-left font-bold font-mono text-xs">{h}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-t border-stone-800/10">
              {row.map((cell, j) => <td key={j} className="px-3 py-2 text-stone-600 align-top">{cell}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-3.5 mb-3.5">
      <div className="shrink-0 w-7 h-7 bg-[#2d2621] text-[#faf6ee] rounded-full flex items-center justify-center font-bold text-[0.85rem] font-hand">{n}</div>
      <div>
        <div className="text-stone-800 font-bold text-[0.9rem] mb-1 font-hand">{title}</div>
        <div className="text-stone-600 text-[0.85rem] leading-relaxed">{children}</div>
      </div>
    </div>
  );
}

export function UIBtn({ children, color = '#0369a1' }: { children: React.ReactNode; color?: string }) {
  return (
    <span className="inline-block bg-stone-100 rounded px-2 py-px text-[0.78rem] font-mono whitespace-nowrap border" style={{ color, borderColor: `${color}44` }}>
      {children}
    </span>
  );
}

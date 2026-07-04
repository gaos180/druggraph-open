import React from "react";

interface NotebookLayoutProps {
  children: React.ReactNode;
  /** Contenido fijo arriba del papel (p. ej. la barra de navegación). */
  navbar?: React.ReactNode;
  /** Ancho máximo del papel. Por defecto amplio para pantallas de datos. */
  maxWidth?: string;
}

/**
 * NotebookLayout — envoltorio de página con estética de cuaderno científico:
 * fondo papel, hoja central con encuadernación espiral, líneas y márgenes rojos.
 * Adaptado de `NotebookBackground` del frontend de ejemplo.
 */
export default function NotebookLayout({ children, navbar, maxWidth = "max-w-[1400px]" }: NotebookLayoutProps) {
  const rings = Array.from({ length: 24 });

  return (
    <div className="min-h-screen bg-[#eadecd] relative overflow-hidden font-sans text-[#2b251d] py-2 md:py-5 px-1 sm:px-4 md:px-6 selection:bg-amber-100 selection:text-amber-900">
      {/* Manchas de carboncillo decorativas */}
      <div className="absolute top-0 right-0 w-96 h-96 opacity-[0.18] pointer-events-none blur-2xl bg-gradient-to-bl from-zinc-600 via-[#1a1816]/30 to-transparent" />
      <div className="absolute -bottom-12 -left-12 w-80 h-80 opacity-[0.12] pointer-events-none blur-xl bg-gradient-to-tr from-stone-900 to-transparent" />

      <div className={`w-full ${maxWidth} mx-auto bg-[#faf6ee] rounded-xl shadow-[0_22px_50px_rgba(0,0,0,0.18)] min-h-[94vh] flex relative border-r-4 border-b-8 border-stone-800/20`}>
        {/* Encuadernación espiral izquierda */}
        <div className="w-9 sm:w-12 shrink-0 bg-[#e4dac6] border-r border-[#d4cbb8] relative flex flex-col items-center py-6 select-none z-10 shadow-inner">
          <div className="absolute top-0 right-1 w-px h-full bg-stone-500/10" />
          <div className="absolute top-0 right-2 w-px h-full bg-stone-500/20" />
          <div className="flex flex-col justify-between h-full absolute inset-y-8 left-1 sm:left-2">
            {rings.map((_, idx) => (
              <div key={idx} className="relative w-8 h-8 flex items-center justify-center -my-1">
                <div className="absolute left-[3px] w-2.5 h-4 bg-stone-800/40 rounded-full border border-stone-900/10 shadow-inner" />
                <svg className="w-12 h-6 overflow-visible -ml-3" filter="url(#handdrawn-sketch)">
                  <path d="M 6 12 Q -4 12 -4 4 Q -4 -4 8 -4 L 28 0 A 2 2 0 0 1 28 4 L 8 4 Q 0 4 0 12 L 6 12"
                    fill="none" stroke="#42403d" strokeWidth="2.5" strokeLinecap="round" />
                  <path d="M -2 4 Q -2 -1 8 -1" fill="none" stroke="#8c8882" strokeWidth="1" strokeLinecap="round" />
                </svg>
              </div>
            ))}
          </div>
        </div>

        {/* Hoja: líneas, márgenes y contenido */}
        <div className="flex-1 flex flex-col relative pl-5 pr-8 sm:pl-6 sm:pr-10 md:pl-8 md:pr-14 py-7 md:py-9 overflow-hidden z-0">
          <div className="absolute top-0 left-0 w-full h-full opacity-[0.03] bg-[linear-gradient(#000_1px,transparent_1px)] [background-size:100%_24px] pointer-events-none" />
          <div className="absolute left-1 md:left-2 top-0 bottom-0 w-px bg-red-400/20 pointer-events-none" />
          <div className="absolute left-[4px] md:left-[9px] top-0 bottom-0 w-px bg-red-400/10 pointer-events-none" />

          <div className="relative z-10 w-full flex flex-col flex-1">
            {navbar}
            <div className="flex-1 flex flex-col">{children}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

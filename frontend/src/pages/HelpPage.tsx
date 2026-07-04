import React, { useState } from 'react';
import { usePageTitle } from '../hooks/usePageTitle';
import { NotebookLayout, NotebookNavbar, PencilButton } from '../components/notebook';
import { SECTIONS } from './help/sections';

export default function HelpPage() {
  usePageTitle('Ayuda');
  const [activeId, setActiveId] = useState('start');

  const active = SECTIONS.find((s) => s.id === activeId)!;
  const activeIdx = SECTIONS.findIndex((s) => s.id === activeId);

  return (
    <NotebookLayout navbar={<NotebookNavbar />}>
      <div className="flex gap-5 items-start">
        {/* Sidebar de secciones */}
        <aside className="w-[220px] shrink-0 hidden md:block sticky top-2 self-start">
          <p className="text-stone-500 text-[0.7rem] font-bold uppercase tracking-wider px-2 mb-2 font-mono">Secciones</p>
          <div className="flex flex-col gap-1">
            {SECTIONS.map((s) => (
              <button key={s.id} onClick={() => setActiveId(s.id)}
                className={`w-full text-left flex items-center gap-2.5 px-3 py-2 rounded-xl text-[0.85rem] font-hand border-2 transition-all cursor-pointer ${
                  activeId === s.id ? 'bg-[#2d2621] text-[#faf6ee] border-[#1e1814]' : 'bg-transparent text-stone-600 border-transparent hover:bg-stone-500/10'
                }`}>
                <span>{s.icon}</span><span>{s.title}</span>
              </button>
            ))}
          </div>
        </aside>

        {/* Contenido */}
        <main className="flex-1 min-w-0 max-w-3xl">
          {active.content}
          <div className="flex justify-between mt-10 pt-5 border-t-2 border-stone-800/10">
            {activeIdx > 0
              ? <PencilButton onClick={() => setActiveId(SECTIONS[activeIdx - 1].id)}>← {SECTIONS[activeIdx - 1].title}</PencilButton>
              : <div />}
            {activeIdx < SECTIONS.length - 1
              ? <PencilButton onClick={() => setActiveId(SECTIONS[activeIdx + 1].id)}>{SECTIONS[activeIdx + 1].title} →</PencilButton>
              : <div />}
          </div>
        </main>
      </div>
    </NotebookLayout>
  );
}

/**
 * NetworkAnalysisPage — análisis GDS: centralidad, comunidades (Louvain) y
 * predicción de enlaces fármaco→diana. Requiere el plugin GDS en Neo4j.
 */
import React, { useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import { Share2, BarChart3, Boxes, Sparkles } from 'lucide-react';
import { usePageTitle } from '../hooks/usePageTitle';
import { NotebookLayout, NotebookNavbar, HandTitle } from '../components/notebook';
import { CentralityPanel, CommunitiesPanel, PredictionPanel } from './network/panels';

type Tab = 'centrality' | 'communities' | 'prediction';

export default function NetworkAnalysisPage() {
  usePageTitle('Análisis de Red');
  const [tab, setTab] = useState<Tab>('centrality');

  const tabs: { key: Tab; label: string; Icon: LucideIcon }[] = [
    { key: 'centrality', label: 'Centralidad', Icon: BarChart3 },
    { key: 'communities', label: 'Comunidades', Icon: Boxes },
    { key: 'prediction', label: 'Predicción de Enlaces', Icon: Sparkles },
  ];

  return (
    <NotebookLayout navbar={<NotebookNavbar />}>
      <div className="mb-5">
        <HandTitle className="text-3xl flex items-center gap-2"><Share2 className="w-7 h-7 text-amber-800" /> Análisis de Red</HandTitle>
        <p className="text-sm text-stone-500 font-hand mt-1">Métricas de grafo sobre la red fármaco-diana, calculadas con Neo4j Graph Data Science.</p>
      </div>

      <div className="flex gap-2 border-b border-stone-800/10 pb-3 overflow-x-auto scrollbar-none">
        {tabs.map(({ key, label, Icon }) => (
          <button key={key} onClick={() => setTab(key)}
            className={`px-4 py-2.5 rounded-xl font-hand text-base font-bold flex items-center gap-2 border-2 cursor-pointer transition-all shrink-0 whitespace-nowrap ${
              tab === key ? 'bg-[#2d2621] text-[#faf6ee] border-[#1e1814] shadow-[2px_2px_0px_#1e1814]' : 'bg-white text-stone-700 border-stone-300 hover:bg-stone-50'
            }`}>
            <Icon className="w-5 h-5" /> {label}
          </button>
        ))}
      </div>

      <div className="mt-5">
        {tab === 'centrality' && <CentralityPanel />}
        {tab === 'communities' && <CommunitiesPanel />}
        {tab === 'prediction' && <PredictionPanel />}
      </div>
    </NotebookLayout>
  );
}

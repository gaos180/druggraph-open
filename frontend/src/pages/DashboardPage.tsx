import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Share2, Pill, FlaskConical, Microscope, Crosshair, Wrench, HelpCircle, Settings, ArrowRight, GitCompare } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { statsApi, StatsResult } from '../api/stats';
import { usePageTitle } from '../hooks/usePageTitle';
import { NotebookLayout, NotebookNavbar, NotebookCard, HandTitle, SectionHeader, Loader, Tag } from '../components/notebook';

// ── Barra horizontal proporcional ────────────────────────────────────────────
function HBar({ label, count, max, color }: { label: string; count: number; max: number; color: string }) {
  const pct = max > 0 ? Math.round((count / max) * 100) : 0;
  return (
    <div className="mb-2">
      <div className="flex justify-between text-[11px] text-stone-600 mb-0.5">
        <span className="capitalize font-hand">{label}</span>
        <span className="font-mono tabular-nums">{count.toLocaleString()}</span>
      </div>
      <div className="bg-stone-300/50 rounded-full h-2 overflow-hidden">
        <div className="h-2 rounded-full transition-all duration-500" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}

function BigStat({ label, value, sub, color }: { label: string; value: number | string; sub?: string; color: string }) {
  return (
    <div className="bg-[#faf6ee] border-2 border-stone-800/15 rounded-xl px-4 py-3 flex-1 min-w-[130px] shadow-[2px_2.5px_0px_rgba(30,25,21,0.06)]">
      <div className="text-2xl font-bold font-hand tabular-nums" style={{ color }}>
        {typeof value === 'number' ? value.toLocaleString() : value}
      </div>
      <div className="text-xs text-stone-600 mt-0.5">{label}</div>
      {sub && <div className="text-[11px] text-stone-500 mt-0.5">{sub}</div>}
    </div>
  );
}

function StatsSection() {
  const [stats, setStats] = useState<StatsResult | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    statsApi.getStats().then(r => setStats(r.data)).catch(() => {}).finally(() => setLoading(false));
  }, []);

  if (loading) return <Loader label="Cargando estadísticas…" />;
  if (!stats) return null;

  const { mongo, neo4j } = stats;
  const maxGroup = Math.max(...mongo.by_group.map(g => g.count), 1);
  const maxRel = Math.max(...neo4j.rel_types.map(r => r.count), 1);
  const GROUP_COLORS: Record<string, string> = {
    approved: '#15803d', investigational: '#b45309', experimental: '#7c3aed',
    withdrawn: '#b91c1c', nutraceutical: '#0e7490', illicit: '#c2410c', vet_approved: '#57534e',
  };
  const panel = "bg-[#faf6ee] border-2 border-stone-800/15 rounded-xl p-4 shadow-[2px_2.5px_0px_rgba(30,25,21,0.06)]";

  return (
    <div className="mb-8">
      <SectionHeader tone="#7c2d12">ESTADÍSTICAS DE LA BASE DE DATOS</SectionHeader>
      <div className="flex gap-4 flex-wrap mb-5 mt-3">
        <BigStat label="Fármacos en MongoDB" value={mongo.total_drugs} color="#2563eb" sub="documentos DrugBank" />
        <BigStat label="Nodos :Drug en Neo4j" value={neo4j.drugs} color="#15803d" sub="grafo de interacciones" />
        <BigStat label="Proteínas diana" value={neo4j.targets} color="#7c3aed" sub="nodos :Target" />
        <BigStat label="Categorías" value={neo4j.categories} color="#c2410c" sub="nodos :Category" />
        <BigStat label="Registros DDI" value={mongo.total_ddi_mentions} color="#be185d" sub="interacciones fármaco-fármaco" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className={panel}>
          <div className="text-[11px] text-stone-500 mb-2.5 font-bold font-mono">MongoDB — DISTRIBUCIÓN POR GRUPO</div>
          {mongo.by_group.map(g => (
            <HBar key={g.label} label={g.label} count={g.count} max={maxGroup} color={GROUP_COLORS[g.label] || '#57534e'} />
          ))}
        </div>
        <div className={panel}>
          <div className="text-[11px] text-stone-500 mb-2.5 font-bold font-mono">Neo4j — RELACIÓN DRUG→TARGET</div>
          {neo4j.rel_types.slice(0, 8).map(r => (
            <HBar key={r.label} label={r.label} count={r.count} max={maxRel} color="#2563eb" />
          ))}
        </div>
        <div className={panel}>
          <div className="text-[11px] text-stone-500 mb-2.5 font-bold font-mono">Neo4j — TOP FÁRMACOS POR DIANAS</div>
          {neo4j.top_drugs.map((d, i) => (
            <div key={d.id} className="flex items-center gap-2 mb-2">
              <span className="text-stone-500 text-[11px] w-3.5 text-right font-mono">{i + 1}</span>
              <div className="flex-1 min-w-0">
                <div className="text-stone-800 text-xs font-medium truncate">{d.name}</div>
                <div className="text-stone-500 text-[11px] font-mono">{d.id}</div>
              </div>
              <Tag tone="blue">{d.targets} dianas</Tag>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const CARDS = [
  { Icon: Share2, title: 'Análisis de Red', to: '/network', color: '#4f46e5', desc: 'Centralidad, comunidades Louvain y predicción de enlaces fármaco-diana con Neo4j GDS y Cytoscape.' },
  { Icon: Pill, title: 'Base de Datos de Fármacos', to: '/drugs', color: '#2563eb', desc: 'Busca y filtra fármacos por nombre, SMILES, tipo, estado de aprobación y dianas.' },
  { Icon: FlaskConical, title: 'Laboratorio Virtual', to: '/sandbox', color: '#9333ea', desc: 'Ingresa un SMILES y compara tu compuesto contra la red: similitud estructural y de comportamiento.' },
  { Icon: Microscope, title: 'Búsqueda por Secuencia', to: '/blast', color: '#0891b2', desc: 'Pega una secuencia de aminoácidos y encuentra proteínas homólogas y los fármacos que las afectan.' },
  { Icon: Crosshair, title: 'Navegador de Dianas', to: '/targets', color: '#0f766e', desc: 'Explora proteínas objetivo, genes, localizaciones celulares y fármacos asociados.' },
  { Icon: GitCompare, title: 'Comparador de Dianas', to: '/targets/compare', color: '#0e7490', desc: 'Compara el perfil farmacológico de múltiples dianas: fármacos comunes, Jaccard y grafo interactivo.' },
  { Icon: Wrench, title: 'Herramientas Analíticas', to: '/tools', color: '#7c3aed', desc: 'DEG Analysis, Reposicionamiento, Toxicidad y verificador de interacciones DDI.' },
  { Icon: HelpCircle, title: 'Documentación y Ayuda', to: '/help', color: '#0369a1', desc: 'Guías de uso paso a paso, referencia de la API REST y descripción de las funcionalidades.' },
];

export default function DashboardPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  usePageTitle('Dashboard');

  const cards = user?.is_admin
    ? [...CARDS, { Icon: Settings, title: 'Panel de Administración', to: '/admin', color: '#7c3aed', desc: 'Gestiona cuentas: crea, edita roles, restablece contraseñas y elimina cuentas.' }]
    : CARDS;

  return (
    <NotebookLayout navbar={<NotebookNavbar />}>
      <div className="mb-10 py-4 border-b border-stone-800/10">
        <HandTitle className="text-3xl md:text-4xl">Red de Interacción de Fármacos</HandTitle>
        <p className="text-base text-stone-500 font-hand italic mt-2">
          Visualiza y explora relaciones farmacológicas a través de objetivos moleculares.
        </p>
      </div>

      <StatsSection />

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {cards.map(({ Icon, title, to, color, desc }) => (
          <NotebookCard key={to} onClick={() => navigate(to)} className="flex flex-col min-h-[170px]">
            <div className="flex items-start justify-between gap-3 mb-3">
              <div className="p-2.5 rounded-xl border-2 border-stone-800/15" style={{ background: `${color}14` }}>
                <Icon className="w-7 h-7" style={{ color }} />
              </div>
              <ArrowRight className="w-5 h-5 text-stone-500" />
            </div>
            <h3 className="text-lg font-bold font-hand text-stone-900 leading-tight">{title}</h3>
            <p className="text-[13px] text-stone-500 leading-snug font-hand mt-2 flex-1">{desc}</p>
          </NotebookCard>
        ))}
      </div>
    </NotebookLayout>
  );
}

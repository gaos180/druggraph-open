import React from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { BarChart3, Repeat, AlertTriangle, Pill, Wrench, Map as MapIcon, FlaskConical, Beaker, Share2, Biohazard, Stethoscope, Atom, Target, Microscope, PawPrint } from 'lucide-react';
import { usePageTitle } from '../../hooks/usePageTitle';
import { NotebookLayout, NotebookNavbar, HandTitle, NotebookCard } from '../../components/notebook';

const TOOLS = [
  { path: '/tools/lab', label: 'Laboratorio molecular', Icon: Microscope, description: 'Panel integral: analiza una molécula con todas las herramientas de una vez (propiedades, similitud, pharmacóforo, ADMET, dianas, repurposing) + toxicidad y docking como extras.' },
  { path: '/tools/deg', label: 'Análisis DEG', Icon: BarChart3, description: 'Cruza genes diferencialmente expresados con targets del fármaco y calcula enriquecimiento GO.' },
  { path: '/tools/repurposing', label: 'Reposicionamiento', Icon: Repeat, description: 'Encuentra fármacos con perfiles de target similares para proponer nuevas indicaciones.' },
  { path: '/tools/toxicity', label: 'Toxicidad', Icon: AlertTriangle, description: 'Evalúa anti-targets (hERG, CYPs), off-targets predichos y cluster estructural.' },
  { path: '/tools/ddi', label: 'DDI Checker', Icon: Pill, description: 'Verifica interacciones fármaco-fármaco registradas en Neo4j (pares o perfil completo).' },
  { path: '/tools/chemical-space', label: 'Espacio químico', Icon: MapIcon, description: 'Mapa UMAP+HDBSCAN de los embeddings ChemBERTa del catálogo; ubica moléculas nuevas.' },
  { path: '/tools/denovo', label: 'Diseño de novo', Icon: FlaskConical, description: 'Genera moléculas nuevas (CReM / SyntheMol / REINVENT4) y las filtra por drug-likeness.' },
  { path: '/tools/admet', label: 'Predicción ADMET', Icon: Beaker, description: 'Modelos supervisados propios (Tox21/BBBP/ESOL) que predicen ADMET/toxicidad desde el SMILES.' },
  { path: '/tools/dti-gnn', label: 'Predicción DTI (GNN)', Icon: Share2, description: 'GNN entrenada (GraphSAGE + Link Prediction) que predice dianas no documentadas con AUCPR.' },
  { path: '/tools/chemprop-tox', label: 'Toxicidad GNN', Icon: Biohazard, description: 'GNN Chemprop (D-MPNN) que aprende la representación molecular y predice los 12 ensayos de toxicidad Tox21.' },
  { path: '/tools/disease-gnn', label: 'Repurposing (GNN)', Icon: Stethoscope, description: 'GNN de enlaces sobre el knowledge graph (Drug↔Target↔Disease) que propone reposicionamientos fármaco→enfermedad.' },
  { path: '/tools/pharmacophore', label: 'Pharmacóforos 3D', Icon: Atom, description: 'Modelo pharmacofórico ligand-based (RDKit): rasgos 3D y geometría, o consenso multi-ligando. Base del Tier 5 estructural.' },
  { path: '/tools/docking', label: 'Docking (Vina)', Icon: Target, description: 'Cribado estructural: acopla un ligando al sitio activo 3D de una diana y estima la afinidad (AutoDock Vina).' },
  { path: '/tools/homology', label: 'Homología cross-especies', Icon: PawPrint, description: 'Uso veterinario: compara los ortólogos de las dianas del fármaco en las especies que elijas y ve si se conservan (≥70% ⇒ probable que funcione).' },
];

export default function ToolsPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const isHub = location.pathname === '/tools';
  usePageTitle('Herramientas');

  return (
    <NotebookLayout navbar={<NotebookNavbar />}>
      <div className="flex gap-5 items-start">
        {/* Sidebar */}
        <aside className="w-[210px] shrink-0 hidden md:block">
          <div className="text-[11px] font-bold font-mono text-stone-500 tracking-wider mb-2 px-2">HERRAMIENTAS</div>
          <div className="flex flex-col gap-2">
            {TOOLS.map(({ path, label, Icon }) => {
              const active = location.pathname === path;
              return (
                <button key={path} onClick={() => navigate(path)}
                  className={`flex items-center gap-2 px-4 py-2.5 rounded-xl font-hand text-base border-2 transition-all cursor-pointer text-left ${
                    active ? 'bg-[#2d2621] text-[#faf6ee] border-[#1e1814] shadow-[2px_2px_0px_#1e1814]' : 'bg-transparent text-stone-700 border-transparent hover:bg-stone-500/10'
                  }`}>
                  <Icon className="w-5 h-5 shrink-0" /> {label}
                </button>
              );
            })}
          </div>
        </aside>

        {/* Contenido */}
        <main className="flex-1 min-w-0">
          {isHub ? (
            <>
              <HandTitle className="text-3xl flex items-center gap-2"><Wrench className="w-7 h-7 text-amber-800" /> Herramientas Analíticas</HandTitle>
              <p className="text-sm text-stone-500 font-hand mt-1 mb-6">
                Análisis avanzados que combinan expresión génica, redes moleculares y enriquecimiento funcional.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {TOOLS.map(({ path, label, Icon, description }) => (
                  <NotebookCard key={path} onClick={() => navigate(path)} className="min-h-[150px]">
                    <div className="p-2 rounded-xl border-2 border-stone-800/15 bg-amber-500/10 w-fit mb-3"><Icon className="w-6 h-6 text-amber-800" /></div>
                    <div className="text-stone-900 font-bold font-hand text-lg mb-1">{label}</div>
                    <div className="text-stone-500 text-[12px] leading-snug font-hand">{description}</div>
                  </NotebookCard>
                ))}
              </div>
            </>
          ) : <Outlet />}
        </main>
      </div>
    </NotebookLayout>
  );
}

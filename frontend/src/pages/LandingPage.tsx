import React, { useState, useEffect } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { BookOpen, Network, Dna, FlaskConical, Search, GitCompare, Play } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { statsApi, PublicStats } from '../api/stats';

const FEATURES = [
  { icon: <Network className="w-6 h-6" />, title: 'Grafo molecular', desc: 'Explora relaciones fármaco–diana–categoría en Neo4j.' },
  { icon: <FlaskConical className="w-6 h-6" />, title: 'Laboratorio virtual', desc: 'Analiza compuestos nuevos por similitud estructural y propagación de efecto.' },
  { icon: <Dna className="w-6 h-6" />, title: 'Dianas terapéuticas', desc: 'Navega el catálogo de proteínas diana con datos UniProt y vías KEGG.' },
  { icon: <Search className="w-6 h-6" />, title: 'BLAST de secuencias', desc: 'Busca homólogos de proteínas contra el índice de dianas de DrugBank.' },
  { icon: <GitCompare className="w-6 h-6" />, title: 'Comparador de dianas', desc: 'Visualiza fármacos compartidos entre múltiples dianas en un grafo interactivo.' },
  { icon: <BookOpen className="w-6 h-6" />, title: 'Herramientas analíticas', desc: 'DEG estimado, reposicionamiento y predicción de toxicidad por perfil de dianas.' },
];

const DEMO_EMAIL = 'demo@druggraph.dev';
const DEMO_PASS  = 'demo1234';

export default function LandingPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState<PublicStats | null>(null);
  const [demoLoading, setDemoLoading] = useState(false);
  const [demoError, setDemoError] = useState('');

  useEffect(() => {
    statsApi.getPublicStats()
      .then(r => setStats(r.data))
      .catch(() => {});
  }, []);

  if (user) return <Navigate to="/dashboard" replace />;

  const handleDemo = async () => {
    setDemoLoading(true);
    setDemoError('');
    try {
      await login(DEMO_EMAIL, DEMO_PASS);
      navigate('/dashboard');
    } catch {
      setDemoError('No se pudo conectar al backend. ¿Está corriendo?');
      setDemoLoading(false);
    }
  };

  return (
    <div
      className="min-h-screen font-hand"
      style={{ background: '#faf6ee', backgroundImage: 'repeating-linear-gradient(transparent, transparent 27px, #d6ccbb55 27px, #d6ccbb55 28px)' }}
    >
      {/* Navbar mínima */}
      <header className="flex items-center justify-between px-8 py-4 border-b-2 border-stone-200">
        <div className="flex items-center gap-2">
          <svg width="28" height="28" viewBox="0 0 50 50" className="text-[#dd6b20]">
            <polygon points="25,5 45,15 45,35 25,45 5,35 5,15" stroke="currentColor" strokeWidth="2.5" fill="none" />
            <line x1="25" y1="5" x2="25" y2="45" stroke="currentColor" strokeWidth="1.2" />
            <line x1="45" y1="15" x2="5" y2="35" stroke="currentColor" strokeWidth="1.2" />
            <line x1="5" y1="15" x2="45" y2="35" stroke="currentColor" strokeWidth="1.2" />
          </svg>
          <span className="text-xl font-bold text-[#1a140f] tracking-tight">DrugGraph</span>
        </div>
        <div className="flex gap-3">
          <Link
            to="/login"
            className="px-4 py-2 rounded-xl border-2 border-stone-800/30 text-[#3a332a] text-sm font-bold hover:bg-stone-100 transition-all"
          >
            Iniciar sesión
          </Link>
          <Link
            to="/register"
            className="px-4 py-2 rounded-xl border-2 border-[#1e1814] bg-[#2d2621] text-[#faf6ee] text-sm font-bold shadow-[2px_2.5px_0px_#1e1814] hover:bg-[#3d332d] transition-all"
          >
            Registrarse
          </Link>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-3xl mx-auto px-8 pt-20 pb-10 text-center">
        <div className="inline-block mb-4 px-3 py-1 rounded-full bg-orange-100 border border-orange-300 text-orange-800 text-xs font-mono font-bold tracking-wider uppercase">
          Plataforma de análisis farmacológico
        </div>
        <h1 className="text-5xl font-bold text-[#1a140f] leading-tight mb-4">
          Análisis farmacológico<br />
          <span className="text-[#dd6b20]">en un solo lugar</span>
        </h1>
        <p className="text-lg text-stone-600 max-w-xl mx-auto mb-10 leading-relaxed">
          Los investigadores combinan DrugBank, STRING y KEGG por separado —
          DrugGraph unifica el grafo fármaco–diana, reposicionamiento, propagación de efectos
          y similitud estructural en una sola plataforma integrada.
        </p>

        {/* CTAs */}
        <div className="flex gap-4 justify-center flex-wrap">
          <Link
            to="/register"
            className="inline-flex items-center gap-2 px-7 py-3.5 rounded-xl border-2 border-[#1e1814] bg-[#2d2621] text-[#faf6ee] font-bold text-base shadow-[3px_3.5px_0px_#1e1814] hover:bg-[#3d332d] active:scale-95 transition-all"
          >
            Comenzar gratis
          </Link>
          <Link
            to="/login"
            className="inline-flex items-center gap-2 px-7 py-3.5 rounded-xl border-2 border-stone-800/30 text-[#3a332a] font-bold text-base shadow-[2px_2.5px_0px_rgba(30,25,21,0.1)] hover:bg-stone-100 active:scale-95 transition-all"
          >
            Ya tengo cuenta
          </Link>
        </div>

        {/* Demo access */}
        <div className="mt-5 flex flex-col items-center gap-2">
          <button
            onClick={handleDemo}
            disabled={demoLoading}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl border-2 border-[#dd6b20]/40 text-[#dd6b20] font-bold text-sm bg-orange-50 hover:bg-orange-100 active:scale-95 transition-all disabled:opacity-60"
          >
            <Play className="w-4 h-4" />
            {demoLoading ? 'Entrando al demo…' : 'Ver demo sin registro →'}
          </button>
          {demoError && <p className="text-red-700 text-xs font-mono">{demoError}</p>}
        </div>
      </section>

      {/* Stats en vivo */}
      {stats && (
        <section className="max-w-2xl mx-auto px-8 pb-14">
          <div className="flex justify-center gap-0 border-2 border-stone-800/10 rounded-2xl overflow-hidden bg-white/50 divide-x-2 divide-stone-800/10">
            {[
              { value: stats.total_drugs.toLocaleString() + '+', label: 'fármacos', sub: 'DrugBank' },
              { value: stats.total_targets.toLocaleString() + '+', label: 'proteínas diana', sub: 'Neo4j' },
              { value: '3', label: 'bases de datos', sub: 'unificadas' },
            ].map(({ value, label, sub }) => (
              <div key={label} className="flex-1 text-center py-5 px-4">
                <div className="text-2xl font-bold text-[#1a140f] font-mono tabular-nums">{value}</div>
                <div className="text-sm text-stone-700 font-hand mt-0.5">{label}</div>
                <div className="text-[11px] text-stone-500 font-mono">{sub}</div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Features */}
      <section className="max-w-4xl mx-auto px-8 pb-20">
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-5">
          {FEATURES.map(({ icon, title, desc }) => (
            <div
              key={title}
              className="bg-white/60 border-2 border-stone-200 rounded-2xl p-5 shadow-[2px_2.5px_0px_rgba(30,25,21,0.06)] hover:border-stone-300 hover:shadow-[3px_3.5px_0px_rgba(30,25,21,0.1)] transition-all"
            >
              <div className="text-[#dd6b20] mb-3">{icon}</div>
              <h3 className="font-bold text-[#1a140f] text-base mb-1">{title}</h3>
              <p className="text-stone-500 text-sm leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t-2 border-stone-200 py-6 text-center text-stone-500 text-xs font-mono">
        DrugGraph · {new Date().getFullYear()} · Datos de DrugBank, STRING, KEGG y UniProt
      </footer>
    </div>
  );
}

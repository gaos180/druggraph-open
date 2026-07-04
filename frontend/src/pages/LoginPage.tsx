import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { BookOpen, LogIn, Play, ArrowLeft } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { usePageTitle } from '../hooks/usePageTitle';
import { PencilButton, Scribble } from '../components/notebook';

const DEMO_EMAIL = 'demo@druggraph.dev';
const DEMO_PASS  = 'demo1234';

export default function LoginPage() {
  const { login, user } = useAuth();
  const navigate = useNavigate();
  usePageTitle('Iniciar sesión');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);

  useEffect(() => { if (user) navigate('/dashboard'); }, [user, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(email, password);
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.response?.data?.error || 'Error de conexión. ¿Está corriendo el backend?');
    } finally {
      setLoading(false);
    }
  };

  const handleDemo = async () => {
    setDemoLoading(true);
    setError('');
    try {
      await login(DEMO_EMAIL, DEMO_PASS);
      navigate('/dashboard');
    } catch {
      setError('No se pudo conectar al backend. ¿Está corriendo?');
      setDemoLoading(false);
    }
  };

  const inputCls =
    'w-full bg-[#faf6ee] px-3 py-2 border-2 border-[#3f3429] rounded-xl font-hand text-base focus:outline-none focus:ring-1 focus:ring-stone-600';

  return (
    <div className="min-h-screen bg-[#eadecd] flex items-center justify-center p-4 font-hand text-[#2b251d]">
      {/* Líneas de cuaderno de fondo */}
      <div className="fixed inset-0 opacity-[0.04] bg-[linear-gradient(#000_1px,transparent_1px)] [background-size:100%_26px] pointer-events-none" />

      <div className="absolute top-4 left-4">
        <Link to="/" className="inline-flex items-center gap-1.5 text-stone-500 hover:text-stone-800 text-sm font-hand transition-colors">
          <ArrowLeft className="w-4 h-4" /> Inicio
        </Link>
      </div>

      <div className="relative w-full max-w-md bg-[#faf6ee] rounded-2xl p-8 border-2 border-[#1e1814] shadow-[6px_7px_0px_#1e1814]">
        {/* Garabato de esquina */}
        <div className="absolute -top-3 -right-3 w-16 h-16 pointer-events-none opacity-20">
          <svg width="100%" height="100%" viewBox="0 0 50 50">
            <path d="M 0 0 C 20 20, 30 15, 50 50 M 10 0 C 15 15, 20 20, 50 30" stroke="#000" strokeWidth="2" fill="none" />
          </svg>
        </div>

        <div className="flex items-center gap-2 justify-center mb-1">
          <BookOpen className="w-7 h-7 text-amber-800 rotate-6" />
          <span className="font-hand font-bold text-2xl text-[#1a140f]">DrugGraph</span>
        </div>
        <h1 className="font-hand font-bold text-3xl text-center text-stone-900 leading-tight">Bienvenido</h1>
        <p className="text-xs text-stone-500 font-hand italic text-center mt-0.5">
          Cuaderno de redes de interacción de fármacos
        </p>
        <Scribble />

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label htmlFor="email" className="block text-[11px] font-mono text-stone-500 mb-1">EMAIL</label>
            <input id="email" type="email" autoComplete="email" placeholder="tu@institucion.edu"
              value={email} onChange={(e) => setEmail(e.target.value)} required className={inputCls} />
          </div>
          <div>
            <label htmlFor="password" className="block text-[11px] font-mono text-stone-500 mb-1">CONTRASEÑA</label>
            <input id="password" type="password" autoComplete="current-password" placeholder="••••••••"
              value={password} onChange={(e) => setPassword(e.target.value)} required className={inputCls} />
          </div>
          {error && (
            <p className="text-[12px] font-mono text-red-700 border border-red-500/30 bg-red-50 p-2 rounded-lg leading-tight">
              {error}
            </p>
          )}
          <PencilButton type="submit" variant="solid" disabled={loading} icon={<LogIn className="w-4 h-4" />} className="w-full justify-center">
            {loading ? 'Entrando…' : 'Iniciar sesión'}
          </PencilButton>
        </form>

        <p className="text-center text-xs text-stone-500 font-hand mt-5">
          ¿No tienes cuenta?{' '}
          <Link to="/register" className="text-amber-800 font-bold underline">Crea una aquí</Link>
        </p>

        {/* Acceso demo */}
        <div className="mt-5 border-t-2 border-stone-800/10 pt-4">
          <p className="text-center text-[11px] text-stone-500 font-mono mb-2.5">ACCESO DE DEMOSTRACIÓN</p>
          <button
            type="button"
            onClick={handleDemo}
            disabled={demoLoading || loading}
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl border-2 border-[#dd6b20]/40 text-[#dd6b20] font-bold text-sm bg-orange-50 hover:bg-orange-100 active:scale-95 transition-all disabled:opacity-60 cursor-pointer"
          >
            <Play className="w-4 h-4" />
            {demoLoading ? 'Entrando…' : 'Probar sin cuenta (demo)'}
          </button>
        </div>
      </div>
    </div>
  );
}

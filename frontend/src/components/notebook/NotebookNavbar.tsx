import React, { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Pill, Crosshair, FlaskConical, Microscope, Share2, Wrench, HelpCircle, LogOut, BookOpen, Menu, X } from "lucide-react";
import { useAuth } from "../../context/AuthContext";

const NAV_LINKS = [
  { to: "/drugs", label: "Fármacos", Icon: Pill },
  { to: "/targets", label: "Dianas", Icon: Crosshair },
  { to: "/sandbox", label: "Sandbox", Icon: FlaskConical },
  { to: "/blast", label: "BLAST", Icon: Microscope },
  { to: "/network", label: "Red", Icon: Share2 },
  { to: "/tools", label: "Herramientas", Icon: Wrench },
];

export default function NotebookNavbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleLogout = async () => {
    await logout();
    window.location.href = '/';
  };

  const handleNav = (to: string) => {
    navigate(to);
    setMobileOpen(false);
  };

  return (
    <header className="mb-6 select-none">
      {/* Barra principal */}
      <div className="flex items-center gap-2 border-b-2 border-stone-800/10 pb-4">
        {/* Marca */}
        <button
          onClick={() => handleNav("/dashboard")}
          className="flex items-center gap-2 mr-2 cursor-pointer font-hand font-bold text-xl text-[#1a140f] shrink-0"
        >
          <BookOpen className="w-6 h-6 text-amber-800 rotate-6" />
          DrugGraph
        </button>

        {/* Nav links — visible solo en desktop (md+) */}
        <div className="hidden md:flex items-center gap-1 flex-wrap">
          {NAV_LINKS.map(({ to, label, Icon }) => {
            const active = location.pathname === to || location.pathname.startsWith(to + "/");
            return (
              <button
                key={to}
                onClick={() => handleNav(to)}
                className={`px-3 py-2.5 xl:px-4 rounded-xl font-hand text-sm xl:text-base flex items-center gap-1.5 xl:gap-2 border-2 transition-all cursor-pointer whitespace-nowrap ${
                  active
                    ? "bg-[#2d2621] text-[#faf6ee] border-[#1e1814] shadow-[2px_2px_0px_#1e1814]"
                    : "bg-transparent text-stone-700 border-transparent hover:bg-stone-500/10"
                }`}
              >
                <Icon className="w-4 h-4 xl:w-5 xl:h-5" />
                <span>{label}</span>
              </button>
            );
          })}
        </div>

        <div className="flex-1" />

        {/* Botones de utilidad */}
        {user?.is_admin && (
          <button
            onClick={() => handleNav("/admin")}
            className="text-xs font-bold font-mono text-purple-800 bg-purple-100 border border-purple-400/40 px-2.5 py-1.5 rounded-md cursor-pointer hidden sm:block"
          >
            ADMIN
          </button>
        )}
        <button
          onClick={() => handleNav("/profile")}
          title="Mi perfil"
          className="p-2 rounded-xl font-hand text-stone-700 hover:bg-stone-500/10 cursor-pointer flex items-center gap-1.5"
        >
          <span>👤</span>
          <span className="hidden sm:inline text-sm">{user?.name?.split(" ")[0] ?? "Perfil"}</span>
        </button>
        <button
          onClick={() => handleNav("/help")}
          title="Ayuda"
          className="p-2 rounded-xl text-stone-500 hover:bg-stone-500/10 cursor-pointer"
        >
          <HelpCircle className="w-5 h-5" />
        </button>
        <button
          onClick={handleLogout}
          title="Salir"
          className="p-2 rounded-xl text-stone-500 hover:text-red-700 hover:bg-red-500/10 cursor-pointer"
        >
          <LogOut className="w-5 h-5" />
        </button>

        {/* Hamburguesa — solo móvil */}
        <button
          onClick={() => setMobileOpen((o) => !o)}
          title={mobileOpen ? "Cerrar menú" : "Abrir menú"}
          className="md:hidden p-2 rounded-xl text-stone-600 hover:bg-stone-500/10 cursor-pointer"
        >
          {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Menú móvil desplegable */}
      {mobileOpen && (
        <div className="md:hidden flex flex-col gap-1 pt-3 pb-4 border-b border-stone-800/10">
          {user?.is_admin && (
            <button
              onClick={() => handleNav("/admin")}
              className="text-xs font-bold font-mono text-purple-800 bg-purple-100 border border-purple-400/40 px-3 py-2 rounded-md cursor-pointer self-start mb-1"
            >
              ADMIN
            </button>
          )}
          {NAV_LINKS.map(({ to, label, Icon }) => {
            const active = location.pathname === to || location.pathname.startsWith(to + "/");
            return (
              <button
                key={to}
                onClick={() => handleNav(to)}
                className={`px-4 py-2.5 rounded-xl font-hand text-base flex items-center gap-2.5 border-2 transition-all cursor-pointer ${
                  active
                    ? "bg-[#2d2621] text-[#faf6ee] border-[#1e1814] shadow-[2px_2px_0px_#1e1814]"
                    : "bg-transparent text-stone-700 border-transparent hover:bg-stone-500/10"
                }`}
              >
                <Icon className="w-5 h-5" />
                {label}
              </button>
            );
          })}
        </div>
      )}
    </header>
  );
}

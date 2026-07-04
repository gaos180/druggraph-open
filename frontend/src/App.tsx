import React, { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import DrugsPage from './features/drugs/DrugsPage';
import DrugDetailPage from './features/drugs/DrugDetailPage';
import SandboxPage from './features/sandbox/SandboxPage';
import BlastSearchPage from './pages/BlastSearchPage';
import NetworkAnalysisPage from './pages/NetworkAnalysisPage';
import HelpPage from './pages/HelpPage';
import AdminPage from './pages/AdminPage';
import ProfilePage from './pages/ProfilePage';
import TargetsPage from './features/targets/TargetsPage';
import TargetDetailPage from './features/targets/TargetDetailPage';
import ToolsPage from './features/tools/ToolsPage';
import DegAnalysisTool from './features/tools/DegAnalysisTool';
import RepurposingTool from './features/tools/RepurposingTool';
import ToxicityTool from './features/tools/ToxicityTool';
import DdiCheckerPage from './features/tools/DdiCheckerPage';
import ChemicalSpaceMap from './features/tools/ChemicalSpaceMap';
import DeNovoTool from './features/tools/DeNovoTool';
import AdmetTool from './features/tools/AdmetTool';
import DtiGnnTool from './features/tools/DtiGnnTool';
import LandingPage from './pages/LandingPage';
import TargetComparePage from './features/targets/TargetComparePage';
import { NotebookSvgDefs } from './components/notebook';
import { ErrorBoundary } from './components/ErrorBoundary';
import './styles/globals.css';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  return user ? <>{children}</> : <Navigate to="/login" />;
}

function JwtExpiryWarning() {
  const { tokenExpiry, logout } = useAuth();
  const navigate = useNavigate();
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (!tokenExpiry) return;

    const check = () => {
      const diff = tokenExpiry - Math.floor(Date.now() / 1000);
      if (diff <= 0) {
        logout();
        navigate('/login');
        return;
      }
      setSecondsLeft(diff);
    };

    check();
    const interval = setInterval(check, 30_000);
    return () => clearInterval(interval);
  }, [tokenExpiry, logout, navigate]);

  if (!secondsLeft || secondsLeft > 300 || dismissed) return null;

  const minutes = Math.ceil(secondsLeft / 60);
  return (
    <div style={{
      position: 'fixed', bottom: '20px', right: '20px',
      background: '#431407', border: '1px solid #fb923c',
      color: '#fed7aa', padding: '12px 18px', borderRadius: '10px',
      zIndex: 9999, fontSize: '0.85rem', maxWidth: '280px',
      boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'flex-start', gap: '10px',
    }}>
      <span style={{ fontSize: '1.2rem' }}>⏰</span>
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 600, marginBottom: '4px' }}>Sesión por expirar</div>
        <div style={{ fontSize: '0.8rem', opacity: 0.85 }}>
          Tu sesión expirará en {minutes} minuto{minutes !== 1 ? 's' : ''}.
          Guarda tu trabajo.
        </div>
      </div>
      <button
        onClick={() => setDismissed(true)}
        style={{
          background: 'transparent', border: 'none', color: '#fb923c',
          cursor: 'pointer', fontSize: '1rem', padding: '0',
        }}
      >✕</button>
    </div>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <BrowserRouter>
          <NotebookSvgDefs />
          <JwtExpiryWarning />
          <Routes>
          <Route path="/" element={<LandingPage />} />

          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          <Route path="/dashboard" element={
            <ProtectedRoute><DashboardPage /></ProtectedRoute>
          } />

          <Route path="/drugs" element={
            <ProtectedRoute><DrugsPage /></ProtectedRoute>
          } />

          <Route path="/drugs/:id" element={
            <ProtectedRoute><DrugDetailPage /></ProtectedRoute>
          } />

          <Route path="/targets" element={
            <ProtectedRoute><TargetsPage /></ProtectedRoute>
          } />

          <Route path="/targets/compare" element={
            <ProtectedRoute><TargetComparePage /></ProtectedRoute>
          } />

          <Route path="/targets/:id" element={
            <ProtectedRoute><TargetDetailPage /></ProtectedRoute>
          } />

          <Route path="/sandbox" element={
            <ProtectedRoute><SandboxPage /></ProtectedRoute>
          } />

          <Route path="/blast" element={
            <ProtectedRoute><BlastSearchPage /></ProtectedRoute>
          } />

          <Route path="/network" element={
            <ProtectedRoute><NetworkAnalysisPage /></ProtectedRoute>
          } />

          <Route path="/help" element={
            <ProtectedRoute><HelpPage /></ProtectedRoute>
          } />

          <Route path="/admin" element={
            <ProtectedRoute><AdminPage /></ProtectedRoute>
          } />

          <Route path="/profile" element={
            <ProtectedRoute><ProfilePage /></ProtectedRoute>
          } />

          <Route path="/tools" element={
            <ProtectedRoute><ToolsPage /></ProtectedRoute>
          }>
            <Route path="deg"         element={<DegAnalysisTool />} />
            <Route path="repurposing" element={<RepurposingTool />} />
            <Route path="toxicity"    element={<ToxicityTool />} />
            <Route path="ddi"         element={<DdiCheckerPage />} />
            <Route path="chemical-space" element={<ChemicalSpaceMap />} />
            <Route path="denovo"      element={<DeNovoTool />} />
            <Route path="admet"       element={<AdmetTool />} />
            <Route path="dti-gnn"     element={<DtiGnnTool />} />
          </Route>

          <Route path="*" element={<Navigate to="/dashboard" />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ErrorBoundary>
  );
}

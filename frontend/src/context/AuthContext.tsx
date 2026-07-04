import React, { createContext, useContext, useState, useEffect } from 'react';
import { authApi, User } from '../api/auth';

interface AuthContextType {
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  loading: boolean;
  tokenExpiry: number | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function decodeTokenExpiry(token: string): number | null {
  try {
    const payload = token.split('.')[1];
    const decoded = JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')));
    return typeof decoded.exp === 'number' ? decoded.exp : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [tokenExpiry, setTokenExpiry] = useState<number | null>(null);

  useEffect(() => {
    // Siempre intenta restaurar la sesión via /me/ — la autenticación real la gestiona
    // la cookie HttpOnly dg_auth (enviada automáticamente por withCredentials).
    // El token en localStorage sólo se usa para decodificar tokenExpiry (cache, no auth).
    const token = localStorage.getItem('dg_token');
    if (token) setTokenExpiry(decodeTokenExpiry(token));

    authApi.me()
      .then(res => setUser(res.data))
      .catch(() => {
        // Cookie inválida/expirada: limpiar cache de localStorage también.
        localStorage.removeItem('dg_token');
        localStorage.removeItem('dg_user');
        setTokenExpiry(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = async (email: string, password: string) => {
    const res = await authApi.login(email, password);
    const token = res.data.token;
    localStorage.setItem('dg_token', token);
    setTokenExpiry(decodeTokenExpiry(token));
    setUser(res.data.user);
  };

  const register = async (name: string, email: string, password: string) => {
    const res = await authApi.register(name, email, password);
    const token = res.data.token;
    localStorage.setItem('dg_token', token);
    setTokenExpiry(decodeTokenExpiry(token));
    setUser(res.data.user);
  };

  const logout = async () => {
    try {
      // Borra la cookie HttpOnly en el servidor.
      await authApi.logout();
    } catch {
      // Si falla (ej. ya expirada), continuar igualmente con la limpieza local.
    }
    localStorage.removeItem('dg_token');
    localStorage.removeItem('dg_user');
    setUser(null);
    setTokenExpiry(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, register, logout, loading, tokenExpiry }}>
      {!loading && children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within an AuthProvider');
  return context;
}

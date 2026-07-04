import axios from 'axios';

const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || 'http://localhost:8000/api',
  headers: { 'Content-Type': 'application/json' },
  // Necesario para que el navegador envíe la cookie HttpOnly dg_auth en cada petición.
  withCredentials: true,
});

api.interceptors.request.use((config) => {
  // El header Authorization es opcional: si hay un token en localStorage se envía
  // (retrocompatibilidad con scripts/API externos). La autenticación real la gestiona
  // la cookie HttpOnly dg_auth enviada automáticamente por withCredentials.
  const token = localStorage.getItem('dg_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let _redirectingToLogin = false;

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401 && !_redirectingToLogin) {
      _redirectingToLogin = true;
      localStorage.removeItem('dg_token');
      localStorage.removeItem('dg_user');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

export default api;
import api from './client';

export interface User {
  _id: string;
  email: string;
  name: string;
  is_admin: boolean;
}

export interface AuthResponse {
  token: string;
  user: User;
}

export const authApi = {
  login: (email: string, password: string) =>
    api.post<AuthResponse>('/auth/login/', { email, password }),
  register: (name: string, email: string, password: string) =>
    api.post<AuthResponse>('/auth/register/', { name, email, password }),
  me: () => api.get<User>('/auth/me/'),
  logout: () => api.post<{ ok: boolean }>('/auth/logout/'),
};
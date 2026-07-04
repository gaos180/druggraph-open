import api from './client';

export interface UserRecord {
  _id: string;
  email: string;
  name: string;
  is_admin: boolean;
  created_at: string;
}

export interface UsersListResponse {
  page: number;
  per_page: number;
  has_next: boolean;
  has_prev: boolean;
  results: UserRecord[];
}

export interface CreateUserParams {
  email: string;
  name: string;
  password: string;
  is_admin?: boolean;
}

export interface UpdateUserParams {
  name?: string;
  email?: string;
  is_admin?: boolean;
}

export const usersApi = {
  list: (params?: { search?: string; page?: number; per_page?: number }) =>
    api.get<UsersListResponse>('/auth/users/', { params }),

  get: (id: string) =>
    api.get<UserRecord>(`/auth/users/${id}/`),

  create: (data: CreateUserParams) =>
    api.post<UserRecord>('/auth/users/', data),

  update: (id: string, data: UpdateUserParams) =>
    api.patch<UserRecord>(`/auth/users/${id}/`, data),

  delete: (id: string) =>
    api.delete<{ deleted: boolean }>(`/auth/users/${id}/`),

  resetPassword: (id: string, new_password: string) =>
    api.post<{ ok: boolean }>(`/auth/users/${id}/reset-password/`, { new_password }),

  updateMe: (data: { name?: string; email?: string }) =>
    api.patch<UserRecord>('/auth/me/update/', data),

  changePassword: (current_password: string, new_password: string) =>
    api.post<{ ok: boolean }>('/auth/me/password/', { current_password, new_password }),
};

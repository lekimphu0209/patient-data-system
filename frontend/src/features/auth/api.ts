import { api } from '@/lib/api'

export interface AuthUser {
  id: number
  email: string
  full_name: string
  role: string
  is_active: boolean
  created_at?: string | null
  updated_at?: string | null
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: AuthUser
}

export async function login(email: string, password: string): Promise<LoginResponse> {
  const response = await api.post<LoginResponse>('/auth/login', { email, password })
  return response.data
}

export async function getMe(): Promise<AuthUser> {
  const response = await api.get<AuthUser>('/auth/me')
  return response.data
}

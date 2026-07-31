import { api } from '@/lib/api'

export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: {
    id: number
    email: string
    full_name: string
    role: string
  }
}

export interface RegisterRequest {
  email: string
  password: string
  full_name: string
  role?: string
}

export async function login(email: string, password: string): Promise<LoginResponse> {
  const response = await api.post<LoginResponse>('/auth/login', { email, password })
  return response.data
}

export async function register(data: RegisterRequest): Promise<LoginResponse> {
  const response = await api.post<LoginResponse>('/auth/register', data)
  return response.data
}

export async function getMe() {
  const response = await api.get('/auth/me')
  return response.data
}

export interface ChangePasswordRequest {
  current_password: string
  new_password: string
  confirm_password: string
}

export async function changePassword(data: ChangePasswordRequest): Promise<{ message: string }> {
  const response = await api.patch('/auth/password', data)
  return response.data
}

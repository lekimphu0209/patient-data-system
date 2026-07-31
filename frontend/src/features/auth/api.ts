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

export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: AuthUser
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

export async function getMe(): Promise<AuthUser> {
  const response = await api.get<AuthUser>('/auth/me')
  return response.data
}

export interface UpdateProfileRequest {
  full_name: string
}

export async function updateProfile(data: UpdateProfileRequest): Promise<AuthUser> {
  const response = await api.patch<AuthUser>('/auth/me', data)
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

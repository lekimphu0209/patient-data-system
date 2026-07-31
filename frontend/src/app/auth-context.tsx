import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'

import { getMe, type AuthUser } from '@/features/auth/api'

interface AuthContextType {
  user: AuthUser | null
  token: string | null
  login: (token: string, user: AuthUser) => void
  logout: () => void
  /** Replace the cached account after the user edits their own profile. */
  setUser: (user: AuthUser) => void
}

const AuthContext = createContext<AuthContextType | null>(null)

const TOKEN_KEY = 'token'
const USER_KEY = 'user'

function readStoredUser(): AuthUser | null {
  const raw = sessionStorage.getItem(USER_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as AuthUser
  } catch {
    return null
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUserState] = useState<AuthUser | null>(null)
  const [token, setToken] = useState<string | null>(null)

  const setUser = useCallback((next: AuthUser) => {
    sessionStorage.setItem(USER_KEY, JSON.stringify(next))
    setUserState(next)
  }, [])

  useEffect(() => {
    const storedToken = sessionStorage.getItem(TOKEN_KEY)
    if (!storedToken) return

    setToken(storedToken)
    // Render immediately from the cached copy, then reconcile with the server so
    // the header never shows a stale name or role.
    setUserState(readStoredUser())
    getMe()
      .then(setUser)
      .catch(() => {
        sessionStorage.removeItem(TOKEN_KEY)
        sessionStorage.removeItem(USER_KEY)
        setToken(null)
        setUserState(null)
        if (window.location.pathname !== '/login') {
          window.location.href = '/login'
        }
      })
  }, [setUser])

  const login = useCallback((newToken: string, newUser: AuthUser) => {
    sessionStorage.setItem(TOKEN_KEY, newToken)
    sessionStorage.setItem(USER_KEY, JSON.stringify(newUser))
    setToken(newToken)
    setUserState(newUser)
  }, [])

  const logout = useCallback(() => {
    sessionStorage.removeItem(TOKEN_KEY)
    sessionStorage.removeItem(USER_KEY)
    setToken(null)
    setUserState(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, token, login, logout, setUser }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}

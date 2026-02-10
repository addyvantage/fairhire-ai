"use client"

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react"
import { useRouter } from "next/navigation"
import { login as apiLogin, register as apiRegister } from "@/lib/api"

const TOKEN_KEY = "fairhire_access_token"

interface AuthContextValue {
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const router = useRouter()

  useEffect(() => {
    const stored = localStorage.getItem(TOKEN_KEY)
    if (stored) {
      setToken(stored)
    }
    setIsLoading(false)
  }, [])

  const login = useCallback(
    async (email: string, password: string) => {
      const data = await apiLogin(email, password)
      localStorage.setItem(TOKEN_KEY, data.access_token)
      setToken(data.access_token)
      router.push("/dashboard")
    },
    [router]
  )

  const register = useCallback(
    async (email: string, password: string) => {
      await apiRegister(email, password)
      const data = await apiLogin(email, password)
      localStorage.setItem(TOKEN_KEY, data.access_token)
      setToken(data.access_token)
      router.push("/dashboard")
    },
    [router]
  )

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    setToken(null)
    router.push("/login")
  }, [router])

  const value = useMemo(
    () => ({
      token,
      isAuthenticated: !!token,
      isLoading,
      login,
      register,
      logout,
    }),
    [token, isLoading, login, register, logout]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}

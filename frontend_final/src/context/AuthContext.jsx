import React, { createContext, useContext, useState, useEffect } from 'react'
import api from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem('sf_user')
    return stored ? JSON.parse(stored) : null
  })
  const [loading, setLoading] = useState(false)

  const login = async (email, password) => {
    const res = await api.post('/auth/login', { email, password })
    const { access_token, user: userData } = res.data
    localStorage.setItem('sf_token', access_token)
    localStorage.setItem('sf_user', JSON.stringify(userData))
    setUser(userData)
    return userData
  }

  const register = async (email, name, password, role = 'student') => {
    const res = await api.post('/auth/register', { email, name, password, role })
    const { access_token, user: userData } = res.data
    localStorage.setItem('sf_token', access_token)
    localStorage.setItem('sf_user', JSON.stringify(userData))
    setUser(userData)
    return userData
  }

  const logout = () => {
    localStorage.removeItem('sf_token')
    localStorage.removeItem('sf_user')
    setUser(null)
  }

  const refreshUser = async () => {
    try {
      const res = await api.get('/auth/me')
      const userData = res.data
      localStorage.setItem('sf_user', JSON.stringify(userData))
      setUser(userData)
    } catch {}
  }

  return (
    <AuthContext.Provider value={{ user, login, register, logout, refreshUser, loading }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)

import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import { LangProvider } from './context/LangContext'
import './index.css'

// Pages
import Landing from './pages/Landing'
import Login from './pages/Login'
import Register from './pages/Register'
import StudentDashboard from './pages/StudentDashboard'
import AdminDashboard from './pages/AdminDashboard'
import TakeAssessment from './pages/TakeAssessment'
import Portfolio from './pages/Portfolio'
import AssessmentResult from './pages/AssessmentResult'
import Profile from './pages/Profile'
import CodingSkills from './pages/CodingSkills'

function ProtectedRoute({ children, adminOnly = false }) {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  if (adminOnly && user.role !== 'admin') return <Navigate to="/dashboard" replace />
  return children
}

function AppRoutes() {
  const { user } = useAuth()

  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={user ? <Navigate to="/dashboard" /> : <Login />} />
      <Route path="/register" element={user ? <Navigate to="/dashboard" /> : <Register />} />

      <Route path="/dashboard" element={
        <ProtectedRoute>
          {user?.role === 'admin' ? <AdminDashboard /> : <StudentDashboard />}
        </ProtectedRoute>
      } />

      <Route path="/coding-skills" element={
        <ProtectedRoute adminOnly><CodingSkills /></ProtectedRoute>
      } />

      <Route path="/assessment/:id" element={
        <ProtectedRoute><TakeAssessment /></ProtectedRoute>
      } />

      <Route path="/result/:submissionId" element={
        <ProtectedRoute><AssessmentResult /></ProtectedRoute>
      } />

      <Route path="/portfolio" element={
        <ProtectedRoute><Portfolio /></ProtectedRoute>
      } />

      <Route path="/profile" element={
        <ProtectedRoute><Profile /></ProtectedRoute>
      } />

      <Route path="/admin" element={
        <ProtectedRoute adminOnly><AdminDashboard /></ProtectedRoute>
      } />

      <Route path="*" element={<Navigate to="/" />} />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <LangProvider>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </LangProvider>
    </BrowserRouter>
  )
}

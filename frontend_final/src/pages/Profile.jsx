import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useLang } from '../context/LangContext'
import { useAuth } from '../context/AuthContext'
import Sidebar from '../components/Sidebar'
import api from '../api/client'

export default function Profile() {
  const { t } = useLang()
  const { user, setUser } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({
    name: '',
    college: '',
    phone: '',
    bio: '',
    preferred_language: 'en'
  })
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get('/users/me').then(r => {
      setForm({
        name: r.data.name || '',
        college: r.data.college || '',
        phone: r.data.phone || '',
        bio: r.data.bio || '',
        preferred_language: r.data.preferred_language || 'en'
      })
    }).catch(() => {})
  }, [])

  const handleSave = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    setSaved(false)
    try {
      const res = await api.put('/users/profile', form)
      if (setUser) setUser(res.data)
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update profile')
    }
    setSaving(false)
  }

  const inputStyle = {
    width: '100%',
    padding: '12px 16px',
    borderRadius: 10,
    border: '1px solid var(--border)',
    background: 'var(--bg-input)',
    color: 'var(--text-primary)',
    fontSize: 15,
    fontFamily: 'inherit',
    outline: 'none',
    transition: 'border-color 0.2s',
  }

  const labelStyle = {
    display: 'block',
    fontSize: 13,
    fontWeight: 600,
    color: 'var(--text-secondary)',
    marginBottom: 6,
  }

  return (
    <div className="page-layout">
      <Sidebar />
      <main className="main-content" style={{ padding: '32px 24px' }}>
        <div style={{ maxWidth: 700, margin: '0 auto' }}>
          <h2 style={{ marginBottom: 8, fontSize: '1.5rem' }}>My Profile</h2>
          <p style={{ color: 'var(--text-secondary)', marginBottom: 32, fontSize: 14 }}>
            Manage your personal information and preferences.
          </p>

          {/* Avatar + Name header */}
          <div className="card" style={{ marginBottom: 24, display: 'flex', alignItems: 'center', gap: 20, padding: '20px 24px' }}>
            <div style={{
              width: 64, height: 64, borderRadius: '50%',
              background: user?.avatar_color || 'var(--primary)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 28, fontWeight: 800, color: '#fff', flexShrink: 0
            }}>
              {(form.name || 'U')[0].toUpperCase()}
            </div>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.1rem' }}>{form.name || 'User'}</h3>
              <p style={{ margin: '2px 0 0', color: 'var(--text-muted)', fontSize: 13 }}>
                {user?.email} · {user?.role === 'admin' ? 'Administrator' : 'Student'}
              </p>
              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                <span className="badge badge-primary">⚡ {user?.xp_points || 0} XP</span>
                <span className="badge badge-success">🔥 {user?.streak_days || 0} day streak</span>
              </div>
            </div>
          </div>

          {/* Edit form */}
          <form onSubmit={handleSave}>
            <div className="card" style={{ marginBottom: 24 }}>
              <h4 style={{ marginBottom: 20, color: 'var(--text-primary)', fontSize: '1rem' }}>Personal Information</h4>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
                <div>
                  <label style={labelStyle}>Full Name</label>
                  <input
                    type="text"
                    value={form.name}
                    onChange={(e) => setForm(f => ({ ...f, name: e.target.value }))}
                    style={inputStyle}
                    placeholder="Your full name"
                    required
                  />
                </div>
                <div>
                  <label style={labelStyle}>Phone Number</label>
                  <input
                    type="tel"
                    value={form.phone}
                    onChange={(e) => setForm(f => ({ ...f, phone: e.target.value }))}
                    style={inputStyle}
                    placeholder="+91 XXXXX XXXXX"
                  />
                </div>
              </div>

              <div style={{ marginBottom: 16 }}>
                <label style={labelStyle}>College / Institution</label>
                <input
                  type="text"
                  value={form.college}
                  onChange={(e) => setForm(f => ({ ...f, college: e.target.value }))}
                  style={inputStyle}
                  placeholder="e.g. AISSMS College of Engineering"
                />
              </div>

              <div style={{ marginBottom: 16 }}>
                <label style={labelStyle}>Bio</label>
                <textarea
                  value={form.bio}
                  onChange={(e) => setForm(f => ({ ...f, bio: e.target.value }))}
                  style={{ ...inputStyle, resize: 'vertical', minHeight: 80 }}
                  placeholder="Tell us about yourself..."
                  rows={3}
                />
              </div>

              <div style={{ marginBottom: 4 }}>
                <label style={labelStyle}>Preferred Language</label>
                <select
                  value={form.preferred_language}
                  onChange={(e) => setForm(f => ({ ...f, preferred_language: e.target.value }))}
                  style={inputStyle}
                >
                  <option value="en">English</option>
                  <option value="hi">Hindi</option>
                  <option value="mr">Marathi</option>
                </select>
              </div>
            </div>

            {/* Email (read-only) */}
            <div className="card" style={{ marginBottom: 24 }}>
              <h4 style={{ marginBottom: 16, color: 'var(--text-primary)', fontSize: '1rem' }}>Account Information</h4>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                <div>
                  <label style={labelStyle}>Email Address</label>
                  <input
                    type="email"
                    value={user?.email || ''}
                    style={{ ...inputStyle, opacity: 0.7, cursor: 'not-allowed' }}
                    disabled
                  />
                </div>
                <div>
                  <label style={labelStyle}>Role</label>
                  <input
                    type="text"
                    value={user?.role === 'admin' ? 'Administrator' : 'Student'}
                    style={{ ...inputStyle, opacity: 0.7, cursor: 'not-allowed' }}
                    disabled
                  />
                </div>
              </div>
              <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>
                Contact support to update your email address or role.
              </p>
            </div>

            {/* Alerts */}
            {error && (
              <div className="alert alert-error" style={{ marginBottom: 16 }}>⚠️ {error}</div>
            )}
            {saved && (
              <div className="alert alert-success" style={{ marginBottom: 16 }}>✅ Profile updated successfully!</div>
            )}

            {/* Save button */}
            <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
              <button type="button" className="btn btn-secondary" onClick={() => navigate('/dashboard')}>
                Cancel
              </button>
              <button type="submit" className="btn" disabled={saving}
                style={{ background: 'var(--grad-primary)', minWidth: 140 }}>
                {saving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </form>
        </div>
      </main>
    </div>
  )
}

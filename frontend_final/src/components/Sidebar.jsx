import React from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useLang } from '../context/LangContext'

function NavItem({ to, icon, label }) {
  return (
    <NavLink to={to} className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
      <span className="icon">{icon}</span>
      {label}
    </NavLink>
  )
}

export default function Sidebar() {
  const { user, logout } = useAuth()
  const { lang, setLang, t } = useLang()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  const langOptions = [
    { code: 'en', label: 'EN', flag: '🇺🇸' },
    { code: 'hi', label: 'HI', flag: '🇮🇳' },
    { code: 'mr', label: 'MR', flag: '🏛️' },
  ]

  return (
    <div className="sidebar">
      <div className="sidebar-brand">
        <span className="logo-icon">⚡</span>
        <span style={{ background: 'var(--grad-primary)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          KaushalyaAI
        </span>
      </div>

      {/* User info */}
      <div style={{ padding: '0 20px 12px', borderBottom: '1px solid var(--border)', marginBottom: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: '36px', height: '36px', borderRadius: '50%',
            background: user?.avatar_color || 'var(--primary)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontWeight: '700', fontSize: '0.9rem', color: '#fff', flexShrink: 0
          }}>
            {user?.name?.[0]?.toUpperCase()}
          </div>
          <div style={{ overflow: 'hidden' }}>
            <div style={{ fontSize: '0.85rem', fontWeight: '600', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {user?.name}
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              {user?.role === 'admin' ? '👑 Admin' : `⭐ ${user?.xp_points || 0} XP`}
            </div>
          </div>
        </div>
      </div>

      {/* Language toggle */}
      <div style={{ padding: '0 20px 12px', borderBottom: '1px solid var(--border)', marginBottom: '12px' }}>
        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 1 }}>
          {t('language')}
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          {langOptions.map(opt => (
            <button key={opt.code} onClick={() => setLang(opt.code)}
              style={{
                flex: 1, padding: '6px 4px', borderRadius: 6, border: 'none', cursor: 'pointer',
                fontSize: '0.7rem', fontWeight: 700, transition: 'all 0.2s',
                background: lang === opt.code ? 'var(--primary)' : 'var(--glass-bg)',
                color: lang === opt.code ? '#fff' : 'var(--text-secondary)',
              }}>
              {opt.flag} {opt.label}
            </button>
          ))}
        </div>
      </div>

      <nav className="sidebar-nav">
        {user?.role === 'admin' ? (
          <>
            <NavItem to="/dashboard" icon="📊" label={t('overview')} />
            <NavItem to="/coding-skills" icon="💻" label="Coding Skills" />
            <NavItem to="/portfolio" icon="📋" label={t('assessments')} />
            <NavItem to="/profile" icon="👤" label="Profile" />
          </>
        ) : (
          <>
            <NavItem to="/dashboard" icon="🏠" label={t('dashboard')} />
            <NavItem to="/portfolio" icon="🎓" label={t('portfolio')} />
            <NavItem to="/profile" icon="👤" label="Profile" />
          </>
        )}
      </nav>

      <div className="sidebar-footer">
        <button
          onClick={handleLogout}
          className="btn btn-secondary"
          style={{ width: '100%', justifyContent: 'center', fontSize: '0.85rem' }}
        >
          🚪 {t('signOut')}
        </button>
      </div>
    </div>
  )
}

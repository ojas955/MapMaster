import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Sidebar from '../components/Sidebar'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useLang } from '../context/LangContext'

export default function Portfolio() {
  const [submissions, setSubmissions] = useState([])
  const [certificates, setCertificates] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('submissions')
  const [certGenerating, setCertGenerating] = useState(null) // submission id being generated
  const { user } = useAuth()
  const { t } = useLang()
  const navigate = useNavigate()

  const loadData = () => {
    setLoading(true)
    Promise.all([
      api.get('/submissions/mine'),
      api.get('/certificates/mine')
    ]).then(([subRes, certRes]) => {
      setSubmissions(subRes.data)
      setCertificates(certRes.data)
    }).finally(() => setLoading(false))
  }

  useEffect(() => { loadData() }, [])

  const handleGenerateCert = async (submissionId) => {
    setCertGenerating(submissionId)
    try {
      const res = await api.post(`/certificates/generate/${submissionId}`)
      // Refresh data to show new certificate
      loadData()
      setActiveTab('certificates')
      alert(t('certGenerated'))
    } catch (err) {
      alert(err.response?.data?.detail || 'Certificate generation failed')
    }
    setCertGenerating(null)
  }

  const getRiskColor = (r) => ({ low: 'var(--success)', medium: 'var(--warning)', high: 'var(--danger)' }[r] || 'var(--text-muted)')

  if (loading) return (
    <div className="page-layout"><Sidebar />
      <div className="main-content loading-page"><div className="spinner" /><p>Loading portfolio...</p></div>
    </div>
  )

  return (
    <div className="page-layout">
      <Sidebar />
      <div className="main-content fade-in">
        <div className="page-header">
          <h1>🗂 {user?.name}'s {t('portfolio')}</h1>
          <p>{t('mySubmissions')} & {t('myCertificates')}</p>
        </div>

        {/* Summary Stats */}
        <div className="grid-3" style={{ marginBottom: '32px' }}>
          <div className="stat-card">
            <div className="stat-icon indigo">📝</div>
            <div className="stat-info"><h3>{submissions.length}</h3><p>{t('assessments')}</p></div>
          </div>
          <div className="stat-card">
            <div className="stat-icon green">🏅</div>
            <div className="stat-info"><h3>{certificates.length}</h3><p>{t('myCertificates')}</p></div>
          </div>
          <div className="stat-card">
            <div className="stat-icon amber">📊</div>
            <div className="stat-info">
              <h3>
                {submissions.length > 0
                  ? `${(submissions.reduce((a, s) => a + s.total_score, 0) / submissions.length).toFixed(0)}%`
                  : '—'}
              </h3>
              <p>{t('score')}</p>
            </div>
          </div>
        </div>

        {/* Tab Navigation */}
        <div style={{ display: 'flex', gap: '8px', marginBottom: '24px', borderBottom: '1px solid var(--border)', paddingBottom: '0' }}>
          {[
            { key: 'submissions', label: `📝 ${t('assessments')} (${submissions.length})` },
            { key: 'certificates', label: `🏅 ${t('myCertificates')} (${certificates.length})` },
          ].map(tab => (
            <button key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              style={{
                background: 'none', border: 'none', cursor: 'pointer', padding: '10px 20px',
                fontFamily: 'var(--font-body)', fontWeight: 600, fontSize: '0.9rem',
                color: activeTab === tab.key ? 'var(--primary-light)' : 'var(--text-secondary)',
                borderBottom: activeTab === tab.key ? '2px solid var(--primary)' : '2px solid transparent',
                transition: 'all 0.2s', marginBottom: '-1px'
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Submissions Tab */}
        {activeTab === 'submissions' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {submissions.length === 0 ? (
              <div className="card card-body" style={{ textAlign: 'center', padding: '48px' }}>
                <div style={{ fontSize: '3rem', marginBottom: '16px' }}>📭</div>
                <p style={{ color: 'var(--text-secondary)', marginBottom: '20px' }}>{t('noAssessments')}</p>
                <button onClick={() => navigate('/dashboard')} className="btn btn-primary">
                  🎓 {t('takeAssessment')}
                </button>
              </div>
            ) : (
              submissions.map(s => {
                const scoreColor = s.total_score >= 70 ? 'var(--success)' : s.total_score >= 50 ? 'var(--warning)' : 'var(--danger)'
                return (
                  <div key={s.id} className="card card-body" style={{ display: 'flex', gap: '16px', alignItems: 'center', padding: '20px', flexWrap: 'wrap' }}>
                    <div style={{ fontSize: '2rem' }}>{s.assessment_emoji}</div>

                    <div style={{ flex: 1, minWidth: 180 }}>
                      <div style={{ fontWeight: 700, marginBottom: '6px' }}>{s.assessment_title}</div>
                      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
                        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                          {new Date(s.submitted_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
                        </span>
                        <span style={{ fontSize: '0.75rem', color: getRiskColor(s.risk_level) }}>
                          🛡 {s.risk_level} risk
                        </span>
                        {s.has_certificate && <span className="badge badge-success">🏅 Certified</span>}
                      </div>
                    </div>

                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: '1.75rem', fontWeight: 900, color: scoreColor }}>{s.total_score.toFixed(0)}%</div>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{t('score')}</div>
                    </div>

                    <div style={{ display: 'flex', gap: '8px', flexDirection: 'column' }}>
                      <button className="btn btn-secondary btn-sm" onClick={() => navigate(`/result/${s.id}`)}>
                        {t('viewResults')}
                      </button>
                      {!s.has_certificate && s.total_score >= 40 && (
                        <button className="btn btn-primary btn-sm"
                          onClick={() => handleGenerateCert(s.id)}
                          disabled={certGenerating === s.id}
                        >
                          {certGenerating === s.id ? '⏳ ...' : `🏅 ${t('generateCert')}`}
                        </button>
                      )}
                    </div>
                  </div>
                )
              })
            )}
          </div>
        )}

        {/* Certificates Tab */}
        {activeTab === 'certificates' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {certificates.length === 0 ? (
              <div className="card card-body" style={{ textAlign: 'center', padding: '48px' }}>
                <div style={{ fontSize: '3rem', marginBottom: '16px' }}>🏅</div>
                <p style={{ color: 'var(--text-secondary)', marginBottom: '20px' }}>{t('noCertificates')}</p>
                <button onClick={() => navigate('/dashboard')} className="btn btn-primary">{t('takeAssessment')}</button>
              </div>
            ) : (
              certificates.map(c => (
                <div key={c.id} className="card" style={{ padding: 0, overflow: 'hidden' }}>
                  {/* Blockchain header */}
                  <div style={{
                    background: 'linear-gradient(135deg, #6366f1, #8b5cf6, #06b6d4)',
                    padding: '14px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center'
                  }}>
                    <div>
                      <h4 style={{ margin: 0, color: '#fff', fontSize: 15 }}>{c.assessment_title}</h4>
                      <p style={{ margin: '2px 0 0', color: 'rgba(255,255,255,0.75)', fontSize: 11 }}>
                        {t('blockchainVerified')} — SHA-256
                      </p>
                    </div>
                    <div style={{ width: 36, height: 36, borderRadius: 8, background: 'rgba(255,255,255,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18 }}>
                      🔗
                    </div>
                  </div>

                  <div style={{ padding: '20px 24px' }}>
                    {/* Hash */}
                    <div style={{ background: 'var(--glass-bg)', borderRadius: 8, padding: '10px 14px', marginBottom: 14, fontFamily: 'monospace' }}>
                      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 3 }}>{t('certHash')} (SHA-256)</div>
                      <div style={{ fontSize: 12, color: 'var(--primary)', wordBreak: 'break-all', fontWeight: 600 }}>
                        0x{c.qr_hash}
                      </div>
                    </div>

                    {/* Details row */}
                    <div style={{ display: 'flex', gap: 12, marginBottom: 14, flexWrap: 'wrap' }}>
                      <div style={{ flex: 1, minWidth: 100, padding: '8px 12px', borderRadius: 8, background: 'var(--glass-bg)' }}>
                        <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{t('issuedOn')}</div>
                        <div style={{ fontSize: 13, fontWeight: 600 }}>{new Date(c.issued_at).toLocaleDateString('en-IN')}</div>
                      </div>
                      <div style={{ flex: 1, minWidth: 100, padding: '8px 12px', borderRadius: 8, background: 'var(--glass-bg)' }}>
                        <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{t('score')}</div>
                        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--success)' }}>{c.score?.toFixed(0)}%</div>
                      </div>
                      <div style={{ flex: 1, minWidth: 100, padding: '8px 12px', borderRadius: 8, background: 'var(--glass-bg)' }}>
                        <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Holder</div>
                        <div style={{ fontSize: 13, fontWeight: 600 }}>{user?.name}</div>
                      </div>
                    </div>

                    {/* Actions */}
                    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                      <a href={c.cert_url} target="_blank" rel="noopener noreferrer" className="btn btn-primary btn-sm"
                        style={{ textDecoration: 'none', flex: 1, justifyContent: 'center', minWidth: 130 }}>
                        📥 {t('downloadCert')}
                      </a>
                      <a href={`/api/certificates/verify/${c.qr_hash}`} target="_blank" rel="noopener noreferrer"
                        className="btn btn-secondary btn-sm"
                        style={{ textDecoration: 'none', flex: 1, justifyContent: 'center', minWidth: 130 }}>
                        🔍 {t('verifyOn')}
                      </a>
                    </div>

                    {/* Blockchain notice */}
                    <div style={{ marginTop: 12, padding: '8px 12px', borderRadius: 6, border: '1px dashed var(--border)', fontSize: 11, color: 'var(--text-muted)' }}>
                      This certificate is secured with a SHA-256 cryptographic hash and QR verification code.
                      Any modification will invalidate the hash.
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  )
}

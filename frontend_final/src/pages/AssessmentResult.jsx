import React, { useState, useEffect } from 'react'
import { useParams, useLocation, useNavigate } from 'react-router-dom'
import { useLang } from '../context/LangContext'
import api from '../api/client'

export default function AssessmentResult() {
  const { submissionId } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const { t } = useLang()
  const [data, setData] = useState(location.state || null)
  const [certLoading, setCertLoading] = useState(false)
  const [certResult, setCertResult] = useState(null)

  useEffect(() => {
    if (!data && submissionId) {
      api.get(`/submissions/${submissionId}`).then(r => setData(r.data)).catch(() => navigate('/dashboard'))
    }
  }, [submissionId])

  if (!data) return <div className="page-container"><div className="loading-spinner" /></div>

  const { total_score, scores, feedback, confidence_scores, anticheat, pathway, xp_gained, proctoring } = data

  const generateCert = async () => {
    setCertLoading(true)
    try {
      const res = await api.post(`/certificates/generate/${data.submission_id || submissionId}`)
      setCertResult(res.data)
    } catch (err) {
      setCertResult({ error: err.response?.data?.detail || 'Certificate generation failed' })
    }
    setCertLoading(false)
  }

  const scoreColor = total_score >= 70 ? 'var(--success)' : total_score >= 40 ? 'var(--warning)' : 'var(--error)'
  const circumference = 2 * Math.PI * 60

  return (
    <div className="page-container">
      <h2 style={{ textAlign: 'center', marginBottom: 32, fontSize: '1.75rem' }}>{t('results')}</h2>

      {/* Score + XP + Integrity */}
      <div style={{ display: 'flex', justifyContent: 'center', gap: 40, marginBottom: 32, flexWrap: 'wrap' }}>
        <div style={{ textAlign: 'center' }}>
          <svg width="140" height="140" viewBox="0 0 140 140">
            <circle cx="70" cy="70" r="60" fill="none" stroke="var(--glass-bg)" strokeWidth="10" />
            <circle cx="70" cy="70" r="60" fill="none" stroke={scoreColor} strokeWidth="10"
              strokeDasharray={circumference} strokeDashoffset={circumference - (total_score / 100) * circumference}
              strokeLinecap="round" transform="rotate(-90 70 70)" style={{ transition: 'stroke-dashoffset 1s' }} />
            <text x="70" y="65" textAnchor="middle" fill="var(--text-primary)" fontSize="28" fontWeight="700">
              {total_score?.toFixed(1)}%
            </text>
            <text x="70" y="85" textAnchor="middle" fill="var(--text-muted)" fontSize="12">{t('score')}</text>
          </svg>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 12 }}>
          {xp_gained && (
            <div className="card" style={{ padding: '12px 20px', textAlign: 'center' }}>
              <span style={{ fontSize: 24, fontWeight: 700, color: 'var(--warning)' }}>+{xp_gained}</span>
              <span style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block' }}>{t('xpEarned')}</span>
            </div>
          )}
          {anticheat && (
            <div className="card" style={{ padding: '12px 20px', textAlign: 'center' }}>
              <span style={{
                fontSize: 16, fontWeight: 700,
                color: anticheat.risk_level === 'low' ? 'var(--success)' : anticheat.risk_level === 'medium' ? 'var(--warning)' : 'var(--error)'
              }}>
                {anticheat.integrity_score}/100
              </span>
              <span style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block' }}>{t('integrity')}</span>
            </div>
          )}
        </div>
      </div>

      {/* Integrity Flags */}
      {anticheat?.flags?.length > 0 && (
        <div className="card" style={{ marginBottom: 24, borderLeft: '3px solid var(--error)', background: 'rgba(239,68,68,0.05)' }}>
          <h4 style={{ color: 'var(--error)', marginBottom: 8 }}>{t('integrityFlags')}</h4>
          {anticheat.flags.map((flag, i) => (
            <div key={i} style={{ fontSize: 13, color: 'var(--text-secondary)', padding: '4px 0', borderBottom: '1px solid var(--border)' }}>
              ⚠ {flag}
            </div>
          ))}
        </div>
      )}
      {/* Proctoring Insights */}
      {proctoring && Object.keys(proctoring).length > 0 && (
        <div className="card" style={{ marginBottom: 24, borderLeft: '3px solid var(--accent)', padding: 0, overflow: 'hidden' }}>
          <div style={{ background: 'linear-gradient(135deg, rgba(6,182,212,0.15), rgba(99,102,241,0.1))', padding: '14px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h4 style={{ margin: 0, color: 'var(--accent)' }}>📷 AI Proctoring Insights</h4>
            <span className="badge" style={{
              background: proctoring.integrity_score >= 70 ? 'rgba(16,185,129,0.2)' : proctoring.integrity_score >= 40 ? 'rgba(245,158,11,0.2)' : 'rgba(239,68,68,0.2)',
              color: proctoring.integrity_score >= 70 ? 'var(--success)' : proctoring.integrity_score >= 40 ? 'var(--warning)' : 'var(--error)'
            }}>
              Proctor Score: {proctoring.integrity_score}%
            </span>
          </div>

          <div style={{ padding: 20 }}>
            {/* Metric cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 10, marginBottom: 16 }}>
              <div style={{ background: 'var(--glass-bg)', borderRadius: 8, padding: '10px 14px', textAlign: 'center' }}>
                <div style={{ fontSize: 22, fontWeight: 800, color: proctoring.face_present_pct >= 80 ? 'var(--success)' : 'var(--warning)' }}>
                  {proctoring.face_present_pct}%
                </div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Face Present</div>
              </div>
              <div style={{ background: 'var(--glass-bg)', borderRadius: 8, padding: '10px 14px', textAlign: 'center' }}>
                <div style={{ fontSize: 22, fontWeight: 800, color: proctoring.gaze_away_pct <= 20 ? 'var(--success)' : 'var(--error)' }}>
                  {100 - (proctoring.gaze_away_pct || 0)}%
                </div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Gaze On-Screen</div>
              </div>
              <div style={{ background: 'var(--glass-bg)', borderRadius: 8, padding: '10px 14px', textAlign: 'center' }}>
                <div style={{ fontSize: 22, fontWeight: 800, color: proctoring.multiple_faces_count === 0 ? 'var(--success)' : 'var(--error)' }}>
                  {proctoring.multiple_faces_count || 0}
                </div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Multi-Face Flags</div>
              </div>
              <div style={{ background: 'var(--glass-bg)', borderRadius: 8, padding: '10px 14px', textAlign: 'center' }}>
                <div style={{ fontSize: 22, fontWeight: 800, color: proctoring.confidence_score >= 60 ? 'var(--success)' : 'var(--warning)' }}>
                  {proctoring.confidence_score}%
                </div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{t('confidence')}</div>
              </div>
            </div>

            {/* Objects detected */}
            {proctoring.objects_detected?.length > 0 && (
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>Suspicious Objects Detected</div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {proctoring.objects_detected.map((obj, i) => (
                    <span key={i} className="badge" style={{ background: 'rgba(239,68,68,0.15)', color: 'var(--error)' }}>
                      📱 {obj}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Expression analysis */}
            {proctoring.expression_summary?.distribution && (
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>Expression Analysis</div>
                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  {Object.entries(proctoring.expression_summary.distribution).map(([expr, pct]) => {
                    const emoji = { neutral: '😐', happy: '😊', sad: '😢', angry: '😠', fearful: '😨', surprised: '😲', disgusted: '🤢' }[expr] || '😐'
                    return (
                      <span key={expr} className="badge" style={{ background: 'var(--glass-bg)', fontSize: 11 }}>
                        {emoji} {expr}: {pct}%
                      </span>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Violation timeline */}
            {proctoring.violations?.length > 0 && (
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>
                  Violation Timeline ({proctoring.violations.length} events)
                </div>
                <div style={{ maxHeight: 120, overflowY: 'auto', borderRadius: 8, background: 'var(--glass-bg)', padding: 8 }}>
                  {proctoring.violations.slice(0, 10).map((v, i) => (
                    <div key={i} style={{ fontSize: 11, color: 'var(--text-secondary)', padding: '3px 0', borderBottom: '1px solid var(--border)' }}>
                      <span style={{ color: v.type === 'object' ? 'var(--error)' : v.type === 'multiple_faces' ? 'var(--error)' : 'var(--warning)' }}>
                        ⚠ {v.type}
                      </span>
                      {' — '}{v.message}
                    </div>
                  ))}
                  {proctoring.violations.length > 10 && (
                    <div style={{ fontSize: 10, color: 'var(--text-muted)', paddingTop: 4 }}>
                      +{proctoring.violations.length - 10} more violations
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Duration */}
            {proctoring.duration_seconds && (
              <div style={{ marginTop: 12, fontSize: 11, color: 'var(--text-muted)', textAlign: 'center' }}>
                Monitored for {Math.floor(proctoring.duration_seconds / 60)}m {proctoring.duration_seconds % 60}s
              </div>
            )}
          </div>
        </div>
      )}

      {/* Per-question breakdown */}
      <h3 style={{ marginBottom: 16, fontSize: '1.25rem' }}>{t('question')}-by-{t('question')} Breakdown</h3>
      {scores && Object.entries(scores).map(([idx, qScores]) => (
        <div key={idx} className="card" style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
            <h4 style={{ margin: 0, fontSize: '1.05rem' }}>{t('question')} {parseInt(idx) + 1}</h4>
            {confidence_scores?.[idx] !== undefined && (
              <span className="badge" style={{
                background: confidence_scores[idx] >= 70 ? 'rgba(16,185,129,0.15)' : confidence_scores[idx] >= 40 ? 'rgba(245,158,11,0.15)' : 'rgba(239,68,68,0.15)',
                color: confidence_scores[idx] >= 70 ? 'var(--success)' : confidence_scores[idx] >= 40 ? 'var(--warning)' : 'var(--error)'
              }}>
                {t('confidence')}: {confidence_scores[idx]}%
              </span>
            )}
          </div>

          {/* Rubric bars */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 16px', marginBottom: 12 }}>
            {typeof qScores === 'object' && Object.entries(qScores).map(([criterion, val]) => {
              if (criterion === 'confidence') return null
              const barColor = val >= 7 ? 'var(--success)' : val >= 4 ? 'var(--warning)' : 'var(--error)'
              return (
                <div key={criterion}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, textTransform: 'capitalize', marginBottom: 2 }}>
                    <span>{criterion}</span>
                    <span style={{ fontWeight: 700, color: barColor }}>{val}/10</span>
                  </div>
                  <div style={{ background: 'var(--glass-bg)', borderRadius: 4, height: 6 }}>
                    <div style={{ background: barColor, borderRadius: 4, height: '100%', width: `${val * 10}%`, transition: 'width 0.5s' }} />
                  </div>
                </div>
              )
            })}
          </div>

          {/* AI Detection */}
          {anticheat?.ai_detection?.[idx] && (
            <div style={{ fontSize: 12, padding: '6px 10px', borderRadius: 6, background: 'rgba(139,92,246,0.08)', marginBottom: 8 }}>
              {anticheat.ai_detection[idx].gemini_ai_probability !== undefined && (
                <span style={{
                  fontWeight: 600,
                  color: anticheat.ai_detection[idx].gemini_ai_probability >= 70 ? 'var(--error)' : anticheat.ai_detection[idx].gemini_ai_probability >= 40 ? 'var(--warning)' : 'var(--success)'
                }}>
                  {t('aiDetection')}: {anticheat.ai_detection[idx].gemini_ai_probability}%
                </span>
              )}
              {anticheat.ai_detection[idx].ai_phrase_count > 0 && (
                <span style={{ marginLeft: 12, color: 'var(--text-muted)' }}>
                  ({anticheat.ai_detection[idx].ai_phrase_count} {t('aiPhrases')})
                </span>
              )}
            </div>
          )}

          {/* Feedback */}
          {feedback?.[idx] && (
            <p style={{ fontSize: 15, color: 'var(--text-secondary)', lineHeight: 1.6, margin: 0, padding: '10px 14px', background: 'var(--glass-bg)', borderRadius: 8 }}>
              {feedback[idx]}
            </p>
          )}
        </div>
      ))}

      {/* Adaptive Pathway */}
      {pathway && (
        <div className="card" style={{ marginBottom: 24, borderLeft: '3px solid var(--primary)' }}>
          <h3 style={{ marginBottom: 12, color: 'var(--primary)' }}>{t('learningPath')}</h3>
          {pathway.reason && (
            <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 16, lineHeight: 1.6 }}>{pathway.reason}</p>
          )}
          {pathway.skill_gaps?.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <h4 style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 8 }}>{t('skillGaps')}</h4>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {pathway.skill_gaps.map((gap, i) => (
                  <span key={i} className="badge" style={{ background: 'rgba(239,68,68,0.12)', color: 'var(--error)' }}>{gap}</span>
                ))}
              </div>
            </div>
          )}
          {pathway.recommended_activities?.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <h4 style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 8 }}>{t('recommendedActivities')}</h4>
              {pathway.recommended_activities.map((act, i) => (
                <div key={i} style={{ padding: '10px 14px', borderRadius: 8, background: 'var(--glass-bg)', marginBottom: 6, fontSize: 13, display: 'flex', gap: 8 }}>
                  <span style={{ color: 'var(--primary)', fontWeight: 700, flexShrink: 0 }}>{i + 1}.</span>{act}
                </div>
              ))}
            </div>
          )}
          {(pathway.next_difficulty || pathway.estimated_study_hours) && (
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
              {pathway.next_difficulty && <span className="badge" style={{ background: 'rgba(99,102,241,0.15)', color: 'var(--primary)' }}>Next: {pathway.next_difficulty}</span>}
              {pathway.estimated_study_hours && <span className="badge">Est. {pathway.estimated_study_hours}h study</span>}
            </div>
          )}
        </div>
      )}

      {/* ─── Certificate Section ─────────────────────────────────────────────── */}
      {total_score >= 40 && !certResult && (
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <button className="btn" onClick={generateCert} disabled={certLoading}
            style={{ background: 'var(--accent-gradient)', padding: '14px 32px', fontSize: 16 }}>
            {certLoading ? t('generatingCert') : t('generateCert')}
          </button>
        </div>
      )}

      {/* Blockchain Certificate Card */}
      {certResult && !certResult.error && (
        <div className="card" style={{ marginBottom: 24, padding: 0, overflow: 'hidden' }}>
          {/* Header strip */}
          <div style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6, #06b6d4)', padding: '16px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h3 style={{ margin: 0, color: '#fff', fontSize: 18 }}>{t('blockchainVerified')}</h3>
              <p style={{ margin: '4px 0 0', color: 'rgba(255,255,255,0.8)', fontSize: 12 }}>SHA-256 Hashed | QR Verified | Immutable</p>
            </div>
            <div style={{ width: 40, height: 40, borderRadius: 8, background: 'rgba(255,255,255,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20 }}>
              🔗
            </div>
          </div>

          <div style={{ padding: 24 }}>
            {/* Certificate hash */}
            <div style={{ background: 'var(--glass-bg)', borderRadius: 8, padding: '12px 16px', marginBottom: 16, fontFamily: 'monospace' }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>{t('certHash')} (SHA-256)</div>
              <div style={{ fontSize: 13, color: 'var(--primary)', wordBreak: 'break-all', fontWeight: 600 }}>
                0x{certResult.qr_hash}
              </div>
            </div>

            {/* Details grid */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
              <div style={{ padding: '10px 14px', borderRadius: 8, background: 'var(--glass-bg)' }}>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{t('issuedOn')}</div>
                <div style={{ fontSize: 14, fontWeight: 600 }}>{new Date(certResult.issued_at).toLocaleDateString()}</div>
              </div>
              <div style={{ padding: '10px 14px', borderRadius: 8, background: 'var(--glass-bg)' }}>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{t('score')}</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: scoreColor }}>{total_score?.toFixed(1)}%</div>
              </div>
            </div>

            {/* QR & Actions */}
            <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
              <div style={{ background: '#fff', padding: 8, borderRadius: 8, flexShrink: 0 }}>
                <img
                  src={certResult.cert_url}
                  alt="Certificate"
                  style={{ width: 100, height: 100, objectFit: 'contain', borderRadius: 4 }}
                  onError={(e) => { e.target.style.display = 'none' }}
                />
              </div>
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
                <a href={certResult.cert_url} target="_blank" rel="noopener noreferrer" className="btn"
                  style={{ textAlign: 'center', textDecoration: 'none', fontSize: 14 }}>
                  {t('downloadCert')}
                </a>
                <a href={`/api/certificates/verify/${certResult.qr_hash}`} target="_blank" rel="noopener noreferrer"
                  className="btn btn-secondary" style={{ textAlign: 'center', textDecoration: 'none', fontSize: 13 }}>
                  🔍 {t('verifyOn')}
                </a>
              </div>
            </div>

            {/* Blockchain info */}
            <div style={{ marginTop: 16, padding: '10px 14px', borderRadius: 8, border: '1px dashed var(--border)', fontSize: 12, color: 'var(--text-muted)' }}>
              <strong>Blockchain Verification:</strong> This certificate is secured with a SHA-256 cryptographic hash. 
              The QR code on the certificate links to our verification API. Any tampering will invalidate the hash, 
              ensuring the certificate's authenticity cannot be forged.
            </div>
          </div>
        </div>
      )}

      {certResult?.error && (
        <div className="card" style={{ textAlign: 'center', borderColor: 'var(--error)', marginBottom: 24 }}>
          <p style={{ color: 'var(--error)' }}>{certResult.error}</p>
        </div>
      )}

      <div style={{ textAlign: 'center', marginTop: 24 }}>
        <button className="btn btn-secondary" onClick={() => navigate('/dashboard')}>
          {t('backToDashboard')}
        </button>
      </div>
    </div>
  )
}

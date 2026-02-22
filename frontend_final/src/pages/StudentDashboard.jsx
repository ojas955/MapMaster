import React, { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Chart as ChartJS,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
  CategoryScale,
  LinearScale,
  BarElement
} from 'chart.js'
import { Radar, Bar } from 'react-chartjs-2'
import Sidebar from '../components/Sidebar'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useLang } from '../context/LangContext'

ChartJS.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip, Legend, CategoryScale, LinearScale, BarElement)

function StatCard({ icon, iconClass, value, label, sub }) {
  return (
    <div className="stat-card">
      <div className={`stat-icon ${iconClass}`}>{icon}</div>
      <div className="stat-info">
        <h3>{value}</h3>
        <p>{label}</p>
        {sub && <p style={{ fontSize: '0.75rem', color: 'var(--success)', marginTop: '2px' }}>{sub}</p>}
      </div>
    </div>
  )
}

export default function StudentDashboard() {
  const [analytics, setAnalytics] = useState(null)
  const [assessments, setAssessments] = useState([])
  const [loading, setLoading] = useState(true)
  const { user } = useAuth()
  const { t } = useLang()
  const navigate = useNavigate()

  useEffect(() => {
    Promise.all([
      api.get('/analytics/me'),
      api.get('/assessments')
    ]).then(([analyticsRes, assessmentsRes]) => {
      setAnalytics(analyticsRes.data)
      setAssessments(assessmentsRes.data)
    }).finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="page-layout">
      <Sidebar />
      <div className="main-content loading-page">
        <div className="spinner" />
        <p>Loading your dashboard...</p>
      </div>
    </div>
  )

  const radarData = {
    labels: analytics?.skill_radar?.labels || ['Depth', 'Accuracy', 'Application', 'Originality'],
    datasets: [{
      label: 'Your Skills',
      data: analytics?.skill_radar?.scores || [0, 0, 0, 0],
      backgroundColor: 'rgba(99, 102, 241, 0.2)',
      borderColor: '#6366f1',
      pointBackgroundColor: '#6366f1',
      pointBorderColor: '#fff',
      pointHoverBackgroundColor: '#fff',
      pointHoverBorderColor: '#6366f1',
    }]
  }

  const radarOptions = {
    scales: {
      r: {
        min: 0, max: 100,
        grid: { color: 'rgba(99,102,241,0.2)' },
        ticks: { color: '#64748b', font: { size: 11 }, stepSize: 25 },
        pointLabels: { color: '#94a3b8', font: { size: 12 } }
      }
    },
    plugins: { legend: { display: false } },
    maintainAspectRatio: true,
  }

  const barData = {
    labels: (analytics?.score_history || []).map(s => s.date),
    datasets: [{
      label: 'Score %',
      data: (analytics?.score_history || []).map(s => s.score),
      backgroundColor: 'rgba(99, 102, 241, 0.7)',
      borderRadius: 6,
    }]
  }

  const barOptions = {
    scales: {
      y: { min: 0, max: 100, grid: { color: 'rgba(99,102,241,0.1)' }, ticks: { color: '#64748b' } },
      x: { grid: { display: false }, ticks: { color: '#64748b' } }
    },
    plugins: { legend: { display: false } },
    maintainAspectRatio: false,
  }

  const getDifficultyBadge = (d) => {
    const map = { beginner: 'badge-success', intermediate: 'badge-warning', advanced: 'badge-danger' }
    return map[d] || 'badge-primary'
  }

  return (
    <div className="page-layout">
      <Sidebar />
      <div className="main-content fade-in">
        <div className="page-header">
          <h1>👋 {t('welcome')}, {user?.name?.split(' ')[0]}!</h1>
          <p>Here's your skill progress and available assessments.</p>
        </div>

        {/* Stats */}
        <div className="grid-4" style={{ marginBottom: '32px' }}>
          <StatCard icon="📝" iconClass="indigo" value={analytics?.total_submissions || 0} label="Assessments Taken" />
          <StatCard icon="⭐" iconClass="amber" value={`${analytics?.average_score || 0}%`} label="Average Score" />
          <StatCard icon="🏆" iconClass="green" value={`${analytics?.best_score || 0}%`} label="Best Score" />
          <StatCard icon="⚡" iconClass="violet" value={analytics?.xp_points || 0} label="XP Points" sub={`🔥 ${analytics?.streak_days || 0} day streak`} />
        </div>

        {/* Charts Row */}
        <div className="grid-2" style={{ marginBottom: '32px' }}>
          <div className="card card-body">
            <h3 style={{ marginBottom: '20px', fontSize: '1rem' }}>🎯 Skill Radar</h3>
            {analytics?.total_submissions > 0 ? (
              <div style={{ maxWidth: '300px', margin: '0 auto' }}>
                <Radar data={radarData} options={radarOptions} />
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}>
                <div style={{ fontSize: '2.5rem', marginBottom: '12px' }}>📊</div>
                <p>Complete an assessment to see your skill radar!</p>
              </div>
            )}
          </div>

          <div className="card card-body">
            <h3 style={{ marginBottom: '20px', fontSize: '1rem' }}>📈 Score History</h3>
            {analytics?.score_history?.length > 0 ? (
              <div style={{ height: '200px' }}>
                <Bar data={barData} options={barOptions} />
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}>
                <div style={{ fontSize: '2.5rem', marginBottom: '12px' }}>📉</div>
                <p>No submission history yet.</p>
              </div>
            )}
          </div>
        </div>

        {/* Adaptive Pathway */}
        {analytics?.pathway_steps?.length > 0 && (
          <div style={{ marginBottom: '32px' }}>
            <div className="section-title"><h2>🧭 Your Learning Pathway</h2><div className="line" /></div>
            <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
              {analytics.pathway_steps.map((step, i) => (
                <div key={i} className="card card-body" style={{ flex: '1', minWidth: '280px' }}>
                  <div style={{ display: 'flex', gap: '12px', marginBottom: '12px' }}>
                    <div style={{ fontSize: '1.5rem' }}>🎯</div>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: '0.9rem', marginBottom: '6px' }}>Personalized Recommendation</div>
                      <p style={{ fontSize: '0.825rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>{step.reason}</p>
                    </div>
                  </div>
                  {step.skill_gaps?.length > 0 && (
                    <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                      {step.skill_gaps.map((gap, j) => (
                        <span key={j} className="badge badge-warning" style={{ fontSize: '0.72rem' }}>⚠️ {gap}</span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Assessments */}
        <div>
          <div className="section-title"><h2>🎓 Available Assessments</h2><div className="line" /></div>
          {assessments.length === 0 ? (
            <div className="card card-body" style={{ textAlign: 'center', padding: '48px' }}>
              <div style={{ fontSize: '3rem', marginBottom: '16px' }}>📭</div>
              <p style={{ color: 'var(--text-secondary)' }}>No assessments available yet. Check back soon!</p>
            </div>
          ) : (
            <div className="grid-3">
              {assessments.map(a => (
                <div
                  key={a.id}
                  className="assessment-card"
                  onClick={() => navigate(`/assessment/${a.id}`)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={e => e.key === 'Enter' && navigate(`/assessment/${a.id}`)}
                  aria-label={`Start assessment: ${a.title}`}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div className="assessment-card-emoji">{a.thumbnail_emoji}</div>
                    {a.user_submitted && <span className="badge badge-success">✓ Done</span>}
                  </div>
                  <div>
                    <div className="assessment-card-title">{a.title}</div>
                    <div className="assessment-card-desc">{a.description}</div>
                  </div>
                  <div className="assessment-card-meta">
                    <span className={`badge ${getDifficultyBadge(a.difficulty)}`}>{a.difficulty}</span>
                    <span className="badge badge-primary">⏱ {a.time_limit_minutes}m</span>
                    <span className="badge badge-cyan">❓ {a.num_questions}Q</span>
                  </div>
                  <button className="btn btn-primary btn-sm" style={{ width: '100%', justifyContent: 'center' }}>
                    {a.user_submitted ? `🔄 Retake` : `▶ ${t('takeAssessment')}`}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

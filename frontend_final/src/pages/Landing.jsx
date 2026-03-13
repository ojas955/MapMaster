import React from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function Landing() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const goToLogin = () => {
    if (user) logout()
    navigate('/login')
  }

  const goToRegister = () => {
    if (user) logout()
    navigate('/register')
  }

  const features = [
    { icon: '🧠', title: 'AI-Powered Questions', desc: 'Upload any PDF and get instantly generated higher-order thinking questions aligned with Bloom\'s Taxonomy.' },
    { icon: '📊', title: 'Real Skill Evaluation', desc: 'AI evaluates depth, accuracy, application, and originality — not just right or wrong answers.' },
    { icon: '🎯', title: 'Adaptive Pathways', desc: 'Personalized learning paths generated from your performance to guide skill progression.' },
    { icon: '🎙️', title: 'Audio Responses', desc: 'Record verbal answers. Whisper AI transcribes and evaluates your spoken explanations.' },
    { icon: '🏅', title: 'Verifiable Certificates', desc: 'Earn certificates with QR codes. Share with employers and verify your real skills.' },
    { icon: '🔒', title: 'Anti-Cheat Integrity', desc: 'Plagiarism detection, originality scoring, and browser monitoring ensure authentic submissions.' },
  ]

  const stats = [
    { n: '10+', label: 'Question Types' },
    { n: '100%', label: 'AI Evaluated' },
    { n: '3', label: 'Languages' },
    { n: 'Free', label: 'Forever' },
  ]

  return (
    <div style={{ minHeight: '100vh', background: 'var(--grad-bg)' }}>
      {/* Navbar */}
      <nav className="navbar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '1.5rem' }}>⚡</span>
          <span style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '1.25rem', background: 'var(--grad-primary)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            KaushalyaAI
          </span>
        </div>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          {user && (
            <button onClick={() => navigate('/dashboard')} className="btn btn-secondary">
              Go to Dashboard
            </button>
          )}
          <button onClick={goToLogin} className="btn btn-secondary">Sign In</button>
          <button onClick={goToRegister} className="btn btn-primary">Get Started Free →</button>
        </div>
      </nav>

      {/* Hero */}
      <section style={{ textAlign: 'center', padding: '100px 32px 80px', position: 'relative', overflow: 'hidden' }}>
        {/* Animated glow orbs */}
        <div style={{ position: 'absolute', top: '10%', left: '10%', width: '400px', height: '400px', borderRadius: '50%', background: 'radial-gradient(circle, rgba(99,102,241,0.15) 0%, transparent 70%)', pointerEvents: 'none' }} />
        <div style={{ position: 'absolute', top: '20%', right: '10%', width: '300px', height: '300px', borderRadius: '50%', background: 'radial-gradient(circle, rgba(139,92,246,0.12) 0%, transparent 70%)', pointerEvents: 'none' }} />

        <div className="fade-in" style={{ position: 'relative' }}>
          <div className="badge badge-primary" style={{ marginBottom: '24px', display: 'inline-flex', fontSize: '0.8rem', padding: '6px 16px' }}>
            🚀 Built for Hackathon 2026 — 100% Free & Open Source
          </div>

          <h1 style={{ fontSize: 'clamp(2.5rem, 6vw, 4.5rem)', fontWeight: 900, lineHeight: 1.1, marginBottom: '24px', maxWidth: '900px', margin: '0 auto 24px' }}>
            Measure{' '}
            <span style={{ background: 'var(--grad-primary)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              Real Skills
            </span>
            {' '}with AI,<br />Not Rote Memory
          </h1>

          <p style={{ fontSize: '1.2rem', color: 'var(--text-secondary)', maxWidth: '650px', margin: '0 auto 40px', lineHeight: 1.7 }}>
            Upload a PDF chapter and instantly get AI-generated higher-order assessments. 
            KaushalyaAI evaluates <strong style={{ color: 'var(--text-primary)' }}>critical thinking, application, synthesis</strong> — not just what you memorized.
          </p>

          <div style={{ display: 'flex', gap: '16px', justifyContent: 'center', flexWrap: 'wrap' }}>
            <button onClick={goToRegister} className="btn btn-primary btn-lg" style={{ fontSize: '1.05rem' }}>
              🚀 Start Free Assessment
            </button>
            <button onClick={goToLogin} className="btn btn-secondary btn-lg">
              📊 View Demo Dashboard
            </button>
          </div>
        </div>

        {/* Stats bar */}
        <div style={{ display: 'flex', gap: '48px', justifyContent: 'center', marginTop: '64px', flexWrap: 'wrap' }}>
          {stats.map(s => (
            <div key={s.n} style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '2.5rem', fontWeight: 900, background: 'var(--grad-primary)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>{s.n}</div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>{s.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section style={{ padding: '80px 32px', maxWidth: '1100px', margin: '0 auto' }}>
        <div style={{ textAlign: 'center', marginBottom: '56px' }}>
          <h2 style={{ fontSize: '2.25rem', marginBottom: '16px' }}>Everything You Need to <span style={{ background: 'var(--grad-primary)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>Assess Real Skills</span></h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '1.05rem' }}>Designed for educators and HR professionals who want to go beyond surface-level testing.</p>
        </div>

        <div className="grid-3">
          {features.map((f, i) => (
            <div key={i} className="card card-body" style={{ animationDelay: `${i * 0.1}s` }}>
              <div style={{ fontSize: '2rem', marginBottom: '12px' }}>{f.icon}</div>
              <h3 style={{ fontSize: '1rem', marginBottom: '10px' }}>{f.title}</h3>
              <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Workflow */}
      <section style={{ padding: '80px 32px', background: 'rgba(99,102,241,0.04)', borderTop: '1px solid var(--border)', borderBottom: '1px solid var(--border)' }}>
        <div style={{ maxWidth: '900px', margin: '0 auto', textAlign: 'center' }}>
          <h2 style={{ fontSize: '2rem', marginBottom: '48px' }}>From PDF to Portfolio in <span style={{ background: 'var(--grad-success)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>4 Simple Steps</span></h2>
          <div className="grid-4">
            {[
              { step: '01', icon: '📄', title: 'Upload PDF', desc: 'Drop any PDF chapter — textbook, case study, or custom document.' },
              { step: '02', icon: '🤖', title: 'AI Generates Questions', desc: 'Gemini AI creates higher-order questions from the content.' },
              { step: '03', icon: '✍️', title: 'Student Responds', desc: 'Write, explain, or record verbal answers demonstrating mastery.' },
              { step: '04', icon: '🏅', title: 'Earn Certificate', desc: 'Get AI-evaluated scores, feedback, and a verifiable certificate.' },
            ].map((s, i) => (
              <div key={i} style={{ textAlign: 'center', padding: '24px 16px' }}>
                <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--primary)', letterSpacing: '2px', marginBottom: '12px' }}>STEP {s.step}</div>
                <div style={{ fontSize: '2.5rem', marginBottom: '12px' }}>{s.icon}</div>
                <h4 style={{ marginBottom: '8px', fontSize: '0.95rem' }}>{s.title}</h4>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section style={{ padding: '100px 32px', textAlign: 'center' }}>
        <div style={{ maxWidth: '600px', margin: '0 auto' }}>
          <h2 style={{ fontSize: '2.5rem', marginBottom: '20px' }}>Ready to Test <span style={{ background: 'var(--grad-primary)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>Real Skills?</span></h2>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '36px', lineHeight: 1.7 }}>
            Join educators and HR professionals who care about what candidates can actually <em>do</em>, not just what they've memorized.
          </p>
          <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', flexWrap: 'wrap' }}>
            <button onClick={goToRegister} className="btn btn-primary btn-lg">Create Free Account →</button>
            <button onClick={goToLogin} className="btn btn-secondary btn-lg">Demo Login</button>
          </div>
          <p style={{ marginTop: '20px', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Demo: admin@kaushalya.ai / admin123 &nbsp;|&nbsp; student@kaushalya.ai / student123
          </p>
        </div>
      </section>

      {/* Footer */}
      <footer style={{ borderTop: '1px solid var(--border)', padding: '24px 32px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
        ⚡ KaushalyaAI — Built with ❤️ for the AISSMS Hackathon 2026 &nbsp;|&nbsp; 100% Free & Open Source
      </footer>
    </div>
  )
}

import React, { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import Sidebar from '../components/Sidebar'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'

export default function AdminDashboard() {
  const [overview, setOverview] = useState(null)
  const [assessments, setAssessments] = useState([])
  const [uploading, setUploading] = useState(false)
  const [uploadResult, setUploadResult] = useState(null)
  const [uploadError, setUploadError] = useState('')
  const [dragging, setDragging] = useState(false)
  const [selectedFile, setSelectedFile] = useState(null)
  const [uploadSettings, setUploadSettings] = useState({ difficulty: 'intermediate', num_questions: 7, language: 'auto' })
  const fileInputRef = useRef()
  const navigate = useNavigate()

  useEffect(() => {
    Promise.all([
      api.get('/analytics/admin/overview'),
      api.get('/assessments')
    ]).then(([overviewRes, assessRes]) => {
      setOverview(overviewRes.data)
      setAssessments(assessRes.data)
    }).catch(() => {
      api.get('/assessments').then(r => setAssessments(r.data))
    })
  }, [])

  const handleFileDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer?.files?.[0] || e.target?.files?.[0]
    if (file && file.name.endsWith('.pdf')) {
      setSelectedFile(file)
      setUploadError('')
    } else {
      setUploadError('Please select a valid PDF file.')
    }
  }

  const handleUpload = async () => {
    if (!selectedFile) return setUploadError('Please select a PDF file first.')
    setUploading(true)
    setUploadError('')
    setUploadResult(null)

    const formData = new FormData()
    formData.append('file', selectedFile)
    formData.append('language', uploadSettings.language)
    formData.append('difficulty', uploadSettings.difficulty)
    formData.append('num_questions', uploadSettings.num_questions)

    try {
      const res = await api.post('/pdf/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      setUploadResult(res.data)
      setSelectedFile(null)
      // Refresh assessments list
      const assessRes = await api.get('/assessments')
      setAssessments(assessRes.data)
    } catch (err) {
      setUploadError(err?.response?.data?.detail || 'Upload failed. Please try again.')
    } finally {
      setUploading(false)
    }
  }

  const handleDeleteAssessment = async (id) => {
    if (!confirm('Deactivate this assessment?')) return
    await api.delete(`/assessments/${id}`)
    setAssessments(prev => prev.filter(a => a.id !== id))
  }

  return (
    <div className="page-layout">
      <Sidebar />
      <div className="main-content fade-in">
        <div className="page-header">
          <h1>👑 Admin Dashboard</h1>
          <p>Manage assessments, upload PDFs, and monitor student performance.</p>
        </div>

        {/* Stats Overview */}
        {overview && (
          <div className="grid-4" style={{ marginBottom: '32px' }}>
            <div className="stat-card">
              <div className="stat-icon indigo">👥</div>
              <div className="stat-info"><h3>{overview.total_users}</h3><p>Students</p></div>
            </div>
            <div className="stat-card">
              <div className="stat-icon violet">📋</div>
              <div className="stat-info"><h3>{overview.total_assessments}</h3><p>Assessments</p></div>
            </div>
            <div className="stat-card">
              <div className="stat-icon cyan">📝</div>
              <div className="stat-info"><h3>{overview.total_submissions}</h3><p>Submissions</p></div>
            </div>
            <div className="stat-card">
              <div className="stat-icon green">🏅</div>
              <div className="stat-info"><h3>{overview.total_certificates}</h3><p>Certificates Issued</p></div>
            </div>
          </div>
        )}

        {/* PDF Upload Section */}
        <div style={{ marginBottom: '32px' }}>
          <div className="section-title"><h2>📄 Upload PDF & Generate Assessment</h2><div className="line" /></div>

          <div className="card card-body">
            {/* Drop Zone */}
            <div
              className={`upload-zone ${dragging ? 'dragging' : ''}`}
              onDragOver={e => { e.preventDefault(); setDragging(true) }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleFileDrop}
              onClick={() => fileInputRef.current?.click()}
              role="button"
              tabIndex={0}
              aria-label="Upload PDF file"
              onKeyDown={e => e.key === 'Enter' && fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                style={{ display: 'none' }}
                onChange={handleFileDrop}
              />
              {selectedFile ? (
                <>
                  <div className="upload-zone-icon">📄</div>
                  <div className="upload-zone-title" style={{ color: 'var(--primary-light)' }}>{selectedFile.name}</div>
                  <div className="upload-zone-sub">{(selectedFile.size / 1024).toFixed(0)} KB — Click to change</div>
                </>
              ) : (
                <>
                  <div className="upload-zone-icon">📂</div>
                  <div className="upload-zone-title">Drag & drop your PDF chapter here</div>
                  <div className="upload-zone-sub">or click to browse · Max {20}MB · PDF only</div>
                </>
              )}
            </div>

            {/* Upload Settings */}
            <div className="grid-3" style={{ marginTop: '20px' }}>
              <div className="form-group">
                <label className="form-label">Difficulty</label>
                <select className="form-input form-select" value={uploadSettings.difficulty}
                  onChange={e => setUploadSettings(s => ({ ...s, difficulty: e.target.value }))}>
                  <option value="beginner">Beginner</option>
                  <option value="intermediate">Intermediate</option>
                  <option value="advanced">Advanced</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Number of Questions</label>
                <select className="form-input form-select" value={uploadSettings.num_questions}
                  onChange={e => setUploadSettings(s => ({ ...s, num_questions: parseInt(e.target.value) }))}>
                  {[5, 6, 7, 8, 9, 10].map(n => <option key={n}>{n}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Language</label>
                <select className="form-input form-select" value={uploadSettings.language}
                  onChange={e => setUploadSettings(s => ({ ...s, language: e.target.value }))}>
                  <option value="auto">Auto-detect</option>
                  <option value="en">English</option>
                  <option value="hi">Hindi</option>
                  <option value="mr">Marathi</option>
                </select>
              </div>
            </div>

            {uploadError && <div className="alert alert-error" style={{ marginTop: '16px' }}>{uploadError}</div>}

            {uploadResult && (
              <div className="alert alert-success" style={{ marginTop: '16px', flexDirection: 'column', alignItems: 'flex-start', gap: '4px' }}>
                <strong>✅ {uploadResult.message}</strong>
                <span>{uploadResult.assessment?.num_questions} questions generated · Assessment ID: #{uploadResult.assessment?.id}</span>
                <button className="btn btn-secondary btn-sm" style={{ marginTop: '8px' }}
                  onClick={() => navigate(`/assessment/${uploadResult.assessment?.id}`)}>
                  Preview Assessment →
                </button>
              </div>
            )}

            <button
              className="btn btn-primary"
              style={{ marginTop: '20px', justifyContent: 'center', width: '100%' }}
              onClick={handleUpload}
              disabled={!selectedFile || uploading}
            >
              {uploading ? '⏳ Processing PDF & Generating Questions...' : '🤖 Upload & Generate Assessment'}
            </button>
          </div>
        </div>

        {/* Assessment List */}
        <div>
          <div className="section-title"><h2>📋 All Assessments ({assessments.length})</h2><div className="line" /></div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {assessments.map(a => (
              <div key={a.id} className="card card-body" style={{ display: 'flex', alignItems: 'center', gap: '16px', padding: '16px 20px', flexWrap: 'wrap' }}>
                <span style={{ fontSize: '1.75rem' }}>{a.thumbnail_emoji}</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 700, marginBottom: '4px' }}>{a.title}</div>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    <span className={`badge ${a.difficulty === 'beginner' ? 'badge-success' : a.difficulty === 'advanced' ? 'badge-danger' : 'badge-warning'}`}>{a.difficulty}</span>
                    <span className="badge badge-cyan">{a.num_questions}Q</span>
                    <span className="badge badge-primary">👥 {a.submission_count}</span>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button className="btn btn-secondary btn-sm" onClick={() => navigate(`/assessment/${a.id}`)}>Preview</button>
                  <button className="btn btn-danger btn-sm" onClick={() => handleDeleteAssessment(a.id)}>Remove</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

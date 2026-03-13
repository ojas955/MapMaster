import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useLang } from '../context/LangContext'
import Proctor from '../components/Proctor'
import ProctorStats from '../components/ProctorStats'
import api from '../api/client'

const CAPTURE_PATTERN = /(draw|diagram|flow\s?chart|figure|sketch|illustrate|white\s?paper|whiteboard|write the steps|write steps|commands?|command sequence|workflow|architecture|block diagram|process flow)/i

function questionNeedsCapture(question) {
  if (!question) return false
  if (question.capture_required) return true
  const type = (question.type || '').toLowerCase()
  if (['whiteboard', 'whiteboard_capture', 'diagram', 'diagram_capture', 'flowchart', 'commands', 'steps', 'capture', 'visual'].includes(type)) {
    return true
  }
  return CAPTURE_PATTERN.test(question.text || '')
}

function getCaptureModeLabel(question) {
  const mode = question?.capture_mode || question?.type || 'capture'
  if (mode.includes('command')) return 'Commands'
  if (mode.includes('step')) return 'Steps'
  if (mode.includes('diagram') || mode.includes('flow')) return 'Diagram'
  return 'Whiteboard'
}

function isQuestionAnswered(question, index, answers, captureStatusByQuestion) {
  const hasText = !!answers[index]?.trim()
  const capture = captureStatusByQuestion[String(index)]
  const hasCapture = ['processing', 'completed'].includes(capture?.status)
  return questionNeedsCapture(question) ? (hasText || hasCapture) : hasText
}

export default function TakeAssessment() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { t } = useLang()
  const proctorRef = useRef(null)
  const [assessment, setAssessment] = useState(null)
  const [answers, setAnswers] = useState({})
  const [followups, setFollowups] = useState({})
  const [currentQ, setCurrentQ] = useState(0)
  const [timeLeft, setTimeLeft] = useState(0)
  const [submitting, setSubmitting] = useState(false)
  const [loadingFollowup, setLoadingFollowup] = useState(false)
  const [showFollowup, setShowFollowup] = useState(null)
  const [captureDevices, setCaptureDevices] = useState([])
  const [selectedCameraId, setSelectedCameraId] = useState('')
  const [capturePanelFor, setCapturePanelFor] = useState(null)
  const [captureStatusByQuestion, setCaptureStatusByQuestion] = useState({})
  const [captureBusy, setCaptureBusy] = useState(false)
  const [captureError, setCaptureError] = useState('')

  // Anti-cheat
  const [tabSwitches, setTabSwitches] = useState(0)
  const [copyPasteCount, setCopyPasteCount] = useState(0)

  // Proctoring
  const [proctorData, setProctorData] = useState(null)
  const [showProctor, setShowProctor] = useState(true)

  // Media recording
  const [isRecording, setIsRecording] = useState(false)
  const [recordingType, setRecordingType] = useState(null)
  const mediaRecorderRef = useRef(null)
  const streamRef = useRef(null)
  const videoPreviewRef = useRef(null)
  const chunksRef = useRef([])
  const captureStreamRef = useRef(null)
  const captureVideoRef = useRef(null)
  const captureCanvasRef = useRef(null)

  // Speech-to-text
  const [isListening, setIsListening] = useState(false)
  const [speechConfidence, setSpeechConfidence] = useState(null)
  const recognitionRef = useRef(null)

  useEffect(() => {
    api.get(`/assessments/${id}`).then(r => {
      setAssessment(r.data)
      setTimeLeft(r.data.time_limit_minutes * 60)
    }).catch(() => navigate('/dashboard'))
  }, [id])

  useEffect(() => {
    api.get(`/assessments/${id}/captures/me`).then((res) => {
      const next = {}
      res.data.forEach((item) => {
        next[String(item.question_index)] = item
      })
      setCaptureStatusByQuestion(next)
    }).catch(() => {})
  }, [id])

  // Timer
  useEffect(() => {
    if (!assessment || timeLeft <= 0) return
    const timer = setInterval(() => {
      setTimeLeft(t => {
        if (t <= 1) { handleSubmit(); return 0 }
        return t - 1
      })
    }, 1000)
    return () => clearInterval(timer)
  }, [assessment])

  // Anti-cheat listeners
  useEffect(() => {
    const onVisChange = () => { if (document.hidden) setTabSwitches(c => c + 1) }
    const onPaste = () => setCopyPasteCount(c => c + 1)
    document.addEventListener('visibilitychange', onVisChange)
    document.addEventListener('paste', onPaste)
    return () => {
      document.removeEventListener('visibilitychange', onVisChange)
      document.removeEventListener('paste', onPaste)
    }
  }, [])

  // Cleanup proctor on unmount
  useEffect(() => {
    return () => {
      if (proctorRef.current) proctorRef.current.stop()
      if (captureStreamRef.current) {
        captureStreamRef.current.getTracks().forEach(track => track.stop())
        captureStreamRef.current = null
      }
    }
  }, [])

  useEffect(() => {
    const hasProcessing = Object.values(captureStatusByQuestion).some(item => item?.status === 'processing')
    if (!hasProcessing) return

    const timer = setInterval(() => {
      api.get(`/assessments/${id}/captures/me`).then((res) => {
        const next = {}
        res.data.forEach((item) => {
          next[String(item.question_index)] = item
        })
        setCaptureStatusByQuestion(next)
      }).catch(() => {})
    }, 3500)

    return () => clearInterval(timer)
  }, [captureStatusByQuestion, id])

  const formatTime = (s) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, '0')}`

  const stopCaptureCamera = useCallback(() => {
    if (captureStreamRef.current) {
      captureStreamRef.current.getTracks().forEach(track => track.stop())
      captureStreamRef.current = null
    }
    if (captureVideoRef.current) {
      captureVideoRef.current.srcObject = null
    }
  }, [])

  const loadCameraDevices = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia || !navigator.mediaDevices?.enumerateDevices) {
      throw new Error('Camera APIs are not supported in this browser.')
    }

    const permissionStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
    permissionStream.getTracks().forEach(track => track.stop())

    const devices = await navigator.mediaDevices.enumerateDevices()
    const videos = devices.filter(device => device.kind === 'videoinput')
    setCaptureDevices(videos)
    if (!selectedCameraId && videos.length > 0) {
      setSelectedCameraId(videos[1]?.deviceId || videos[0].deviceId)
    }
    return videos
  }, [selectedCameraId])

  const startCaptureCamera = useCallback(async (deviceId) => {
    stopCaptureCamera()
    const constraints = {
      video: deviceId
        ? {
            deviceId: { exact: deviceId },
            width: { ideal: 1280 },
            height: { ideal: 720 },
          }
        : {
            facingMode: 'user',
            width: { ideal: 1280 },
            height: { ideal: 720 },
          },
      audio: false,
    }

    const stream = await navigator.mediaDevices.getUserMedia(constraints)
    captureStreamRef.current = stream
    if (captureVideoRef.current) {
      captureVideoRef.current.srcObject = stream
      await captureVideoRef.current.play().catch(() => {})
    }
  }, [stopCaptureCamera])

  const openCapturePanel = async (questionIndex) => {
    setCaptureError('')
    setCapturePanelFor(questionIndex)
    try {
      const devices = await loadCameraDevices()
      const nextDeviceId = selectedCameraId || devices[1]?.deviceId || devices[0]?.deviceId
      if (nextDeviceId) {
        setSelectedCameraId(nextDeviceId)
        await startCaptureCamera(nextDeviceId)
      }
    } catch (err) {
      setCaptureError(err?.message || 'Could not access the camera. Check permissions and try again.')
    }
  }

  const closeCapturePanel = useCallback(() => {
    stopCaptureCamera()
    setCapturePanelFor(null)
  }, [stopCaptureCamera])

  const handleCameraChange = async (deviceId) => {
    setSelectedCameraId(deviceId)
    setCaptureError('')
    try {
      await startCaptureCamera(deviceId)
    } catch (err) {
      setCaptureError(err?.message || 'Unable to switch to the selected camera.')
    }
  }

  const handleCaptureUpload = async (questionIndex) => {
    if (!captureVideoRef.current || !captureCanvasRef.current) return

    const video = captureVideoRef.current
    const canvas = captureCanvasRef.current
    const width = video.videoWidth || 1280
    const height = video.videoHeight || 720
    canvas.width = width
    canvas.height = height

    const context = canvas.getContext('2d')
    context.drawImage(video, 0, 0, width, height)

    setCaptureBusy(true)
    setCaptureError('')
    setCaptureStatusByQuestion(prev => ({
      ...prev,
      [String(questionIndex)]: { ...(prev[String(questionIndex)] || {}), status: 'uploading' }
    }))

    try {
      const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.92))
      if (!blob) throw new Error('Could not create image from the camera frame.')
      const formData = new FormData()
      formData.append('capture_file', blob, `whiteboard-q${questionIndex + 1}.jpg`)
      formData.append('typed_context', answers[questionIndex] || '')
      formData.append('device_label', captureDevices.find(d => d.deviceId === selectedCameraId)?.label || 'Camera')

      const res = await api.post(`/assessments/${id}/questions/${questionIndex}/capture`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })

      setCaptureStatusByQuestion(prev => ({
        ...prev,
        [String(questionIndex)]: {
          ...(prev[String(questionIndex)] || {}),
          capture_id: res.data.capture_id,
          question_index: questionIndex,
          status: 'processing',
          device_label: captureDevices.find(d => d.deviceId === selectedCameraId)?.label || 'Camera',
          analysis_summary: 'Image uploaded. AI is analyzing your handwritten response in the background.',
        }
      }))
      closeCapturePanel()
    } catch (err) {
      setCaptureError(err?.response?.data?.detail || 'Capture upload failed.')
      setCaptureStatusByQuestion(prev => ({
        ...prev,
        [String(questionIndex)]: { ...(prev[String(questionIndex)] || {}), status: 'failed' }
      }))
    } finally {
      setCaptureBusy(false)
    }
  }

  // ─── Speech-to-Text (Web Speech API) ─────────────────────────────────────
  const startSpeechToText = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) {
      alert('Speech recognition is not supported in this browser. Please use Chrome.')
      return
    }

    const recognition = new SpeechRecognition()
    recognition.continuous = true
    recognition.interimResults = true
    recognition.lang = 'en-US'

    recognition.onresult = (event) => {
      let finalTranscript = ''
      let interimTranscript = ''
      let totalConfidence = 0
      let confidenceCount = 0

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i]
        if (result.isFinal) {
          finalTranscript += result[0].transcript + ' '
          totalConfidence += result[0].confidence
          confidenceCount++
        } else {
          interimTranscript += result[0].transcript
        }
      }

      if (finalTranscript) {
        setAnswers(prev => ({
          ...prev,
          [currentQ]: (prev[currentQ] || '') + finalTranscript
        }))
      }

      if (confidenceCount > 0) {
        setSpeechConfidence(Math.round((totalConfidence / confidenceCount) * 100))
      }
    }

    recognition.onerror = (event) => {
      console.error('Speech error:', event.error)
      setIsListening(false)
    }

    recognition.onend = () => {
      setIsListening(false)
    }

    recognitionRef.current = recognition
    recognition.start()
    setIsListening(true)
  }

  const stopSpeechToText = () => {
    if (recognitionRef.current) {
      recognitionRef.current.stop()
      setIsListening(false)
    }
  }

  // ─── Media Recording ──────────────────────────────────────────────────────
  const startRecording = async (type) => {
    try {
      const constraints = type === 'video'
        ? { audio: true, video: { facingMode: 'user', width: 320, height: 240 } }
        : { audio: true }

      const stream = await navigator.mediaDevices.getUserMedia(constraints)
      streamRef.current = stream

      if (type === 'video' && videoPreviewRef.current) {
        videoPreviewRef.current.srcObject = stream
        videoPreviewRef.current.play()
      }

      const mimeType = MediaRecorder.isTypeSupported('video/webm;codecs=vp9,opus')
        ? 'video/webm;codecs=vp9,opus'
        : MediaRecorder.isTypeSupported('video/webm')
          ? 'video/webm'
          : 'audio/webm'

      const recorder = new MediaRecorder(stream, { mimeType: type === 'audio' ? 'audio/webm' : mimeType })
      chunksRef.current = []

      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data) }
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: type === 'video' ? 'video/webm' : 'audio/webm' })
        handleRecordingComplete(blob, type)
        stream.getTracks().forEach(t => t.stop())
        if (videoPreviewRef.current) videoPreviewRef.current.srcObject = null
      }

      mediaRecorderRef.current = recorder
      recorder.start()
      setIsRecording(true)
      setRecordingType(type)
    } catch (err) {
      alert(`Could not access ${type === 'video' ? 'camera' : 'microphone'}. Please check permissions.`)
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop()
      setIsRecording(false)
      setRecordingType(null)
    }
  }

  const handleRecordingComplete = async (blob, type) => {
    const text = `[${type === 'video' ? 'Video' : 'Audio'} response recorded — ${(blob.size / 1024).toFixed(0)}KB]`
    setAnswers(prev => ({ ...prev, [currentQ]: (prev[currentQ] || '') + '\n' + text }))
  }

  // ─── Follow-up Questions ──────────────────────────────────────────────────
  const requestFollowup = async (qIndex) => {
    const answer = answers[qIndex]
    if (!answer || answer.trim().length < 20) return

    setLoadingFollowup(true)
    try {
      const res = await api.post(`/assessments/${id}/followup`, {
        question_index: qIndex,
        student_answer: answer
      })
      if (res.data.followup) {
        setFollowups(prev => ({
          ...prev,
          [qIndex]: { question: res.data.followup, answer: '' }
        }))
        setShowFollowup(qIndex)
      }
    } catch (err) {
      console.error('Follow-up failed:', err)
    }
    setLoadingFollowup(false)
  }

  // ─── Submit ───────────────────────────────────────────────────────────────
  const handleSubmit = async () => {
    if (submitting) return

    const missingCaptureQuestions = (assessment?.questions || []).filter((question, index) => {
      if (!questionNeedsCapture(question)) return false
      const capture = captureStatusByQuestion[String(index)]
      const hasText = !!answers[index]?.trim()
      return !hasText && !capture?.capture_id && capture?.status !== 'processing' && capture?.status !== 'completed'
    })

    if (missingCaptureQuestions.length > 0) {
      const confirmed = window.confirm('Some whiteboard/capture questions do not have an uploaded image yet. Submit anyway?')
      if (!confirmed) return
    }

    setSubmitting(true)

    // Get proctoring stats
    const proctoringStats = proctorRef.current ? proctorRef.current.getStats() : null

    // Stop proctor camera
    if (proctorRef.current) proctorRef.current.stop()

    // Merge followup answers
    const finalAnswers = { ...answers }
    Object.entries(followups).forEach(([idx, fu]) => {
      if (fu.answer) {
        finalAnswers[`${idx}_followup`] = fu.answer
      }
    })

    try {
      const res = await api.post('/submissions', {
        assessment_id: parseInt(id),
        answers: finalAnswers,
        time_taken_seconds: assessment.time_limit_minutes * 60 - timeLeft,
        visual_capture_ids: Object.fromEntries(
          Object.entries(captureStatusByQuestion)
            .filter(([, value]) => value?.capture_id)
            .map(([key, value]) => [key, value.capture_id])
        ),
        anticheat_flags: {
          tab_switches: tabSwitches,
          copy_paste_count: copyPasteCount
        },
        proctoring_data: proctoringStats
      })
      navigate(`/result/${res.data.submission_id}`, { state: res.data })
    } catch (err) {
      alert('Submission failed: ' + (err.response?.data?.detail || err.message))
      setSubmitting(false)
    }
  }

  if (!assessment) return <div className="page-container"><div className="loading-spinner" /></div>

  const questions = assessment.questions || []
  const q = questions[currentQ]
  const progress = questions.filter((question, index) => isQuestionAnswered(question, index, answers, captureStatusByQuestion)).length

  return (
    <div className="page-container" style={{ maxWidth: 1100 }}>
      <div style={{ display: 'flex', gap: 20 }}>
        {/* Main content */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {/* Header bar */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24, flexWrap: 'wrap', gap: 12 }}>
            <div>
              <h2 style={{ margin: 0 }}>{assessment.title}</h2>
              <span className="badge">{assessment.difficulty}</span>
            </div>
            <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
              {tabSwitches > 0 && (
                <span className="badge" style={{ background: 'var(--error)', fontSize: 11 }}>
                  Tab switches: {tabSwitches}
                </span>
              )}
              <div style={{
                background: timeLeft < 60 ? 'var(--error)' : 'var(--glass-bg)',
                padding: '8px 16px', borderRadius: 8, fontWeight: 700, fontSize: 20,
                fontFamily: 'monospace', color: timeLeft < 60 ? '#fff' : 'var(--text-primary)'
              }}>
                {formatTime(timeLeft)}
              </div>
            </div>
          </div>

          {/* Progress bar */}
          <div style={{ background: 'var(--glass-bg)', borderRadius: 8, height: 6, marginBottom: 24 }}>
            <div style={{
              background: 'var(--accent-gradient)', borderRadius: 8, height: '100%',
              width: `${(progress / questions.length) * 100}%`, transition: 'width 0.3s'
            }} />
          </div>

          {/* Question navigator */}
          <div style={{ display: 'flex', gap: 6, marginBottom: 24, flexWrap: 'wrap' }}>
            {questions.map((_, i) => (
              <button key={i} onClick={() => { setShowFollowup(null); setCurrentQ(i); setCapturePanelFor(null); stopCaptureCamera() }}
                style={{
                  width: 36, height: 36, borderRadius: 8, border: 'none', cursor: 'pointer',
                  fontWeight: 600, fontSize: 13,
                  background: i === currentQ
                    ? 'var(--primary)'
                    : isQuestionAnswered(questions[i], i, answers, captureStatusByQuestion)
                      ? 'var(--success)'
                      : 'var(--glass-bg)',
                  color: (i === currentQ || isQuestionAnswered(questions[i], i, answers, captureStatusByQuestion)) ? '#fff' : 'var(--text-secondary)',
                }}>{i + 1}</button>
            ))}
          </div>

          {/* Question card */}
          <div className="card" style={{ marginBottom: 24 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12, gap: 12, flexWrap: 'wrap' }}>
              <span className="badge">{q?.bloom_level}</span>
              <span className="badge" style={{ background: 'rgba(99,102,241,0.15)', color: 'var(--primary)' }}>
                Q{currentQ + 1} of {questions.length}
              </span>
            </div>

            <h3 style={{ marginBottom: 8 }}>{q?.text}</h3>
            {q?.section_reference && (
              <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 16 }}>
                Reference: {q.section_reference}
              </p>
            )}

            {questionNeedsCapture(q) && (
              <div className="card" style={{ marginBottom: 16, background: 'rgba(2,136,209,0.06)', border: '1px solid rgba(2,136,209,0.18)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
                  <div>
                    <div style={{ fontWeight: 700, color: 'var(--accent)', marginBottom: 4 }}>📷 {getCaptureModeLabel(q)} response enabled</div>
                    <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                      Use your laptop camera or an attached external webcam to capture your handwritten page. Analysis runs in the background.
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {captureStatusByQuestion[String(currentQ)]?.status && (
                      <span className="badge" style={{
                        background: captureStatusByQuestion[String(currentQ)]?.status === 'completed'
                          ? 'rgba(46,125,50,0.12)'
                          : captureStatusByQuestion[String(currentQ)]?.status === 'failed'
                            ? 'rgba(198,40,40,0.12)'
                            : 'rgba(230,81,0,0.12)',
                        color: captureStatusByQuestion[String(currentQ)]?.status === 'completed'
                          ? 'var(--success)'
                          : captureStatusByQuestion[String(currentQ)]?.status === 'failed'
                            ? 'var(--error)'
                            : 'var(--warning)'
                      }}>
                        {captureStatusByQuestion[String(currentQ)]?.status === 'completed' ? '✅ Analyzed' : captureStatusByQuestion[String(currentQ)]?.status === 'failed' ? '⚠ Failed' : '⏳ Processing'}
                      </span>
                    )}
                    <button className="btn btn-secondary" onClick={() => openCapturePanel(currentQ)}>
                      {captureStatusByQuestion[String(currentQ)]?.capture_id ? '♻ Retake Capture' : '📸 Capture'}
                    </button>
                  </div>
                </div>
              </div>
            )}

            <textarea
              value={answers[currentQ] || ''}
              onChange={(e) => setAnswers(prev => ({ ...prev, [currentQ]: e.target.value }))}
              placeholder={questionNeedsCapture(q)
                ? 'Optional typed note: explain labels, commands, or anything that may be hard to read from the image.'
                : 'Type your detailed answer here... Use specific examples and demonstrate your understanding.'}
              rows={8}
              style={{
                width: '100%', padding: 16, borderRadius: 12, border: '1px solid var(--border)',
                background: 'var(--glass-bg)', color: 'var(--text-primary)', fontSize: 15,
                fontFamily: 'inherit', resize: 'vertical', outline: 'none'
              }}
            />

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8, flexWrap: 'wrap', gap: 8 }}>
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                {(answers[currentQ] || '').split(/\s+/).filter(Boolean).length} {t('wordsCount')}
              </span>
              {speechConfidence !== null && (
                <span className="badge" style={{
                  background: speechConfidence >= 70 ? 'rgba(16,185,129,0.15)' : 'rgba(245,158,11,0.15)',
                  color: speechConfidence >= 70 ? 'var(--success)' : 'var(--warning)'
                }}>
                  🎤 Voice confidence: {speechConfidence}%
                </span>
              )}
            </div>

            {/* Recording & Speech controls */}
            <div style={{ display: 'flex', gap: 8, marginTop: 16, flexWrap: 'wrap' }}>
              {!isRecording && !isListening ? (
                <>
                  <button className="btn btn-secondary" onClick={startSpeechToText}
                    style={{ fontSize: 13, padding: '8px 14px' }}>
                    🗣️ Voice Answer
                  </button>
                  <button className="btn btn-secondary" onClick={() => startRecording('audio')}
                    style={{ fontSize: 13, padding: '8px 14px' }}>
                    🎙️ {t('recordAudio')}
                  </button>
                  <button className="btn btn-secondary" onClick={() => startRecording('video')}
                    style={{ fontSize: 13, padding: '8px 14px' }}>
                    📹 {t('recordVideo')}
                  </button>
                  {questionNeedsCapture(q) && (
                    <button className="btn btn-secondary" onClick={() => openCapturePanel(currentQ)}
                      style={{ fontSize: 13, padding: '8px 14px' }}>
                      📸 Capture White Paper
                    </button>
                  )}
                  {answers[currentQ]?.trim()?.length > 20 && !followups[currentQ] && (
                    <button className="btn btn-secondary" onClick={() => requestFollowup(currentQ)}
                      disabled={loadingFollowup}
                      style={{ fontSize: 13, padding: '8px 14px', marginLeft: 'auto' }}>
                      {loadingFollowup ? `⏳ ${t('generating')}` : `🔄 ${t('getFollowup')}`}
                    </button>
                  )}
                </>
              ) : isListening ? (
                <button className="btn" onClick={stopSpeechToText}
                  style={{ background: 'var(--warning)', fontSize: 13, padding: '8px 14px', animation: 'pulse 1s infinite' }}>
                  🗣️ Listening... (tap to stop)
                </button>
              ) : (
                <button className="btn" onClick={stopRecording}
                  style={{ background: 'var(--error)', fontSize: 13, padding: '8px 14px', animation: 'pulse 1s infinite' }}>
                  ⏹ {t('stopRecording')}
                </button>
              )}
            </div>

            {/* Video preview */}
            {isRecording && recordingType === 'video' && (
              <div style={{ marginTop: 12, borderRadius: 12, overflow: 'hidden', maxWidth: 320 }}>
                <video ref={videoPreviewRef} muted style={{ width: '100%', borderRadius: 12, background: '#000' }} />
              </div>
            )}

            {questionNeedsCapture(q) && captureStatusByQuestion[String(currentQ)]?.analysis_summary && capturePanelFor !== currentQ && (
              <div style={{ marginTop: 14, padding: '12px 14px', borderRadius: 10, background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap', marginBottom: 6 }}>
                  <strong style={{ color: 'var(--accent)' }}>Capture analysis</strong>
                  {captureStatusByQuestion[String(currentQ)]?.overall_score ? (
                    <span className="badge badge-primary">{captureStatusByQuestion[String(currentQ)]?.overall_score}/10 visual score</span>
                  ) : null}
                </div>
                <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                  {captureStatusByQuestion[String(currentQ)]?.analysis_summary}
                </div>
              </div>
            )}

            {capturePanelFor === currentQ && (
              <div className="card" style={{ marginTop: 16, background: 'rgba(255,255,255,0.98)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'center', marginBottom: 14 }}>
                  <div>
                    <h4 style={{ margin: 0, fontSize: '1rem' }}>📷 Capture handwritten answer</h4>
                    <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
                      Pick a camera, frame the full paper, then capture. External webcams are supported when connected.
                    </p>
                  </div>
                  <button className="btn btn-secondary btn-sm" onClick={closeCapturePanel}>Close</button>
                </div>

                <div className="grid-2" style={{ alignItems: 'start' }}>
                  <div>
                    <label className="form-label" style={{ marginBottom: 6 }}>Camera source</label>
                    <select className="form-input form-select" value={selectedCameraId} onChange={(e) => handleCameraChange(e.target.value)}>
                      {captureDevices.length === 0 ? <option value="">No camera detected</option> : captureDevices.map(device => (
                        <option key={device.deviceId} value={device.deviceId}>{device.label || `Camera ${device.deviceId.slice(0, 5)}`}</option>
                      ))}
                    </select>
                    <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 8 }}>
                      Tip: if proctoring uses the laptop camera, choose the external webcam here for a smoother whiteboard setup.
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
                    <button className="btn btn-secondary btn-sm" onClick={() => handleCameraChange(selectedCameraId)}>
                      🔄 Refresh Camera
                    </button>
                    <button className="btn btn-primary btn-sm" onClick={() => handleCaptureUpload(currentQ)} disabled={captureBusy}>
                      {captureBusy ? '⏳ Uploading...' : '📸 Capture & Analyze'}
                    </button>
                  </div>
                </div>

                {captureError && <div className="alert alert-error" style={{ marginTop: 12 }}>{captureError}</div>}

                <div style={{ marginTop: 14, borderRadius: 14, overflow: 'hidden', background: '#0f172a', border: '1px solid rgba(255,255,255,0.08)' }}>
                  <video ref={captureVideoRef} muted playsInline style={{ width: '100%', maxHeight: 420, objectFit: 'cover', display: 'block' }} />
                </div>
                <canvas ref={captureCanvasRef} style={{ display: 'none' }} />
              </div>
            )}
          </div>

          {/* Follow-up question (dynamic) */}
          {followups[currentQ] && showFollowup === currentQ && (
            <div className="card" style={{ marginBottom: 24, borderLeft: '3px solid var(--warning)', background: 'rgba(245,158,11,0.05)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <span style={{ fontSize: 18 }}>🔄</span>
                <h4 style={{ margin: 0, color: 'var(--warning)' }}>{t('followupChallenge')}</h4>
                <span className="badge" style={{ background: 'rgba(245,158,11,0.2)', color: 'var(--warning)', fontSize: 11 }}>
                  {followups[currentQ].question?.probe_reason || 'deeper probe'}
                </span>
              </div>
              <p style={{ marginBottom: 12 }}>{followups[currentQ].question?.text}</p>
              <textarea
                value={followups[currentQ].answer || ''}
                onChange={(e) => setFollowups(prev => ({
                  ...prev,
                  [currentQ]: { ...prev[currentQ], answer: e.target.value }
                }))}
                placeholder="Answer the follow-up question..."
                rows={4}
                style={{
                  width: '100%', padding: 12, borderRadius: 8, border: '1px solid var(--border)',
                  background: 'var(--glass-bg)', color: 'var(--text-primary)', fontSize: 14,
                  fontFamily: 'inherit', resize: 'vertical', outline: 'none'
                }}
              />
            </div>
          )}

          {/* Navigation */}
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
            <button className="btn btn-secondary" onClick={() => { setShowFollowup(null); setCapturePanelFor(null); stopCaptureCamera(); setCurrentQ(Math.max(0, currentQ - 1)) }}
              disabled={currentQ === 0}>
              {t('previous')}
            </button>
            <div style={{ display: 'flex', gap: 12 }}>
              {currentQ < questions.length - 1 ? (
                <button className="btn" onClick={() => { setShowFollowup(null); setCapturePanelFor(null); stopCaptureCamera(); setCurrentQ(currentQ + 1) }}>
                  {t('next')}
                </button>
              ) : (
                <button className="btn" onClick={handleSubmit} disabled={submitting}
                  style={{ background: submitting ? 'var(--text-muted)' : 'var(--success)', minWidth: 160 }}>
                  {submitting ? t('submitting') : `${t('submit')} (${progress}/${questions.length} ${t('answered')})`}
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Proctor sidebar */}
        {showProctor && (
          <div style={{ width: 320, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ position: 'sticky', top: 20 }}>
              <Proctor
                ref={proctorRef}
                onViolation={(v) => console.log('Proctor violation:', v)}
                onStatsUpdate={setProctorData}
              />
              <div style={{ marginTop: 12 }}>
                <ProctorStats proctorData={proctorData} />
              </div>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => setShowProctor(false)}
                style={{ width: '100%', marginTop: 8, fontSize: 11, justifyContent: 'center' }}
              >
                Hide Camera
              </button>
            </div>
          </div>
        )}

        {/* Mini proctor toggle when hidden */}
        {!showProctor && (
          <button
            onClick={() => setShowProctor(true)}
            style={{
              position: 'fixed', bottom: 20, right: 20, zIndex: 50,
              width: 56, height: 56, borderRadius: '50%', border: 'none',
              background: proctorData?.faceDetected ? 'var(--success)' : 'var(--error)',
              color: '#fff', fontSize: 20, cursor: 'pointer',
              boxShadow: '0 4px 20px rgba(0,0,0,0.4)', transition: 'all 0.2s',
            }}
            title="Show proctor camera"
          >
            {proctorData?.faceDetected ? '📷' : '⚠️'}
          </button>
        )}
      </div>
    </div>
  )
}

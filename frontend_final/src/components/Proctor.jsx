import React, { useEffect, useRef, useState, useCallback, forwardRef, useImperativeHandle } from 'react'
import * as faceapi from 'face-api.js'

const Proctor = forwardRef(({ onViolation, onStatsUpdate }, ref) => {
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const intervalRef = useRef(null)
  const cocoModelRef = useRef(null)
  const [modelsLoaded, setModelsLoaded] = useState(false)
  const [cameraActive, setCameraActive] = useState(false)
  const [status, setStatus] = useState('initializing')
  const statsRef = useRef({
    totalChecks: 0,
    facePresent: 0,
    faceAbsent: 0,
    multipleFaces: 0,
    gazeAway: 0,
    objectsDetected: [],
    expressionHistory: [],
    violations: [],
    startTime: Date.now(),
  })

  // Expose stats via ref
  useImperativeHandle(ref, () => ({
    getStats: () => {
      const s = statsRef.current
      const totalChecks = Math.max(s.totalChecks, 1)
      return {
        face_present_pct: Math.round((s.facePresent / totalChecks) * 100),
        face_absent_count: s.faceAbsent,
        multiple_faces_count: s.multipleFaces,
        gaze_away_count: s.gazeAway,
        gaze_away_pct: Math.round((s.gazeAway / totalChecks) * 100),
        objects_detected: [...new Set(s.objectsDetected)],
        object_violation_count: s.objectsDetected.length,
        violations: s.violations,
        total_violations: s.violations.length,
        duration_seconds: Math.round((Date.now() - s.startTime) / 1000),
        expression_summary: getExpressionSummary(s.expressionHistory),
        confidence_score: calculateConfidence(s),
        integrity_score: calculateIntegrity(s),
      }
    },
    stop: () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
      const stream = videoRef.current?.srcObject
      if (stream) stream.getTracks().forEach(t => t.stop())
    }
  }))

  const calculateConfidence = (s) => {
    const totalChecks = Math.max(s.totalChecks, 1)
    const facePct = s.facePresent / totalChecks
    const gazeOnPct = 1 - (s.gazeAway / totalChecks)
    // Weigh face presence and gaze
    const score = Math.round((facePct * 40) + (gazeOnPct * 40) + 20)
    return Math.min(100, Math.max(0, score))
  }

  const calculateIntegrity = (s) => {
    let score = 100
    score -= s.faceAbsent * 3
    score -= s.multipleFaces * 10
    score -= s.gazeAway * 2
    score -= s.objectsDetected.length * 8
    return Math.max(0, Math.min(100, score))
  }

  const getExpressionSummary = (history) => {
    if (history.length === 0) return { dominant: 'neutral', distribution: {} }
    const counts = {}
    history.forEach(e => { counts[e] = (counts[e] || 0) + 1 })
    const total = history.length
    const distribution = {}
    Object.keys(counts).forEach(k => { distribution[k] = Math.round((counts[k] / total) * 100) })
    const dominant = Object.keys(counts).reduce((a, b) => counts[a] > counts[b] ? a : b)
    return { dominant, distribution }
  }

  // Load face-api models
  useEffect(() => {
    const loadModels = async () => {
      try {
        setStatus('loading models...')
        await faceapi.nets.tinyFaceDetector.loadFromUri('/models')
        await faceapi.nets.faceLandmark68Net.loadFromUri('/models')
        await faceapi.nets.faceExpressionNet.loadFromUri('/models')

        // Load COCO-SSD for object detection
        try {
          const cocoSsd = await import('@tensorflow-models/coco-ssd')
          cocoModelRef.current = await cocoSsd.load()
        } catch (e) {
          console.warn('COCO-SSD load failed, object detection disabled', e)
        }

        setModelsLoaded(true)
        setStatus('starting camera...')
      } catch (e) {
        console.error('Model loading error:', e)
        setStatus('model load failed')
      }
    }
    loadModels()
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [])

  // Start camera
  useEffect(() => {
    if (!modelsLoaded) return
    const startCamera = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { width: 320, height: 240, facingMode: 'user' },
          audio: false
        })
        if (videoRef.current) {
          videoRef.current.srcObject = stream
          setCameraActive(true)
          setStatus('active')
        }
      } catch (e) {
        console.error('Camera error:', e)
        setStatus('camera denied')
      }
    }
    startCamera()
  }, [modelsLoaded])

  // Detection loop
  useEffect(() => {
    if (!cameraActive || !modelsLoaded) return

    const detect = async () => {
      const video = videoRef.current
      if (!video || video.readyState < 2) return

      statsRef.current.totalChecks++

      // Face detection with landmarks + expressions
      const detections = await faceapi
        .detectAllFaces(video, new faceapi.TinyFaceDetectorOptions({ inputSize: 224, scoreThreshold: 0.4 }))
        .withFaceLandmarks()
        .withFaceExpressions()

      const now = new Date().toLocaleTimeString()

      if (detections.length === 0) {
        statsRef.current.faceAbsent++
        addViolation('no_face', `No face detected at ${now}`)
      } else {
        statsRef.current.facePresent++

        if (detections.length > 1) {
          statsRef.current.multipleFaces++
          addViolation('multiple_faces', `${detections.length} faces detected at ${now}`)
        }

        // Gaze check from landmarks
        const landmarks = detections[0].landmarks
        const nose = landmarks.getNose()
        const leftEye = landmarks.getLeftEye()
        const rightEye = landmarks.getRightEye()

        if (nose.length > 0 && leftEye.length > 0 && rightEye.length > 0) {
          const noseX = nose[0].x
          const eyeCenterX = (leftEye[0].x + rightEye[3].x) / 2
          const faceWidth = rightEye[3].x - leftEye[0].x
          const gazeOffset = Math.abs(noseX - eyeCenterX) / Math.max(faceWidth, 1)

          if (gazeOffset > 0.35) {
            statsRef.current.gazeAway++
            addViolation('gaze_away', `Looking away from screen at ${now}`)
          }
        }

        // Expression tracking
        const expressions = detections[0].expressions
        const dominant = Object.keys(expressions).reduce((a, b) =>
          expressions[a] > expressions[b] ? a : b
        )
        statsRef.current.expressionHistory.push(dominant)
        // Keep last 100 entries
        if (statsRef.current.expressionHistory.length > 100) {
          statsRef.current.expressionHistory = statsRef.current.expressionHistory.slice(-100)
        }
      }

      // Object detection (every other check to save CPU)
      if (cocoModelRef.current && statsRef.current.totalChecks % 2 === 0) {
        try {
          const predictions = await cocoModelRef.current.detect(video)
          // Detect phones, books, laptops, remotes, and extra people
          const personCount = predictions.filter(p => p.class === 'person' && p.score > 0.4).length
          const suspicious = predictions.filter(p =>
            ['cell phone', 'book', 'laptop', 'remote'].includes(p.class) && p.score > 0.45
          )
          // Flag if more than 1 person detected (third party assistance)
          if (personCount > 1) {
            statsRef.current.objectsDetected.push('extra person')
            addViolation('extra_person', `${personCount} people detected at ${now}`)
          }
          suspicious.forEach(obj => {
            statsRef.current.objectsDetected.push(obj.class)
            addViolation('object', `${obj.class} detected (${Math.round(obj.score * 100)}% confidence) at ${now}`)
          })
        } catch (e) {
          // Object detection can occasionally fail, ignore
        }
      }

      // Update parent with current stats
      if (onStatsUpdate) {
        onStatsUpdate({
          faceDetected: detections.length > 0,
          multipleFaces: detections.length > 1,
          gazeOnScreen: statsRef.current.gazeAway === 0 || (statsRef.current.totalChecks - statsRef.current.gazeAway) > statsRef.current.gazeAway,
          totalViolations: statsRef.current.violations.length,
          integrity: calculateIntegrity(statsRef.current),
          expression: detections.length > 0 ? Object.keys(detections[0].expressions).reduce((a, b) =>
            detections[0].expressions[a] > detections[0].expressions[b] ? a : b
          ) : 'unknown',
        })
      }

      // Draw on canvas
      if (canvasRef.current && video) {
        const displaySize = { width: video.videoWidth || 320, height: video.videoHeight || 240 }
        faceapi.matchDimensions(canvasRef.current, displaySize)
        const resized = faceapi.resizeResults(detections, displaySize)
        const ctx = canvasRef.current.getContext('2d')
        ctx.clearRect(0, 0, displaySize.width, displaySize.height)
        faceapi.draw.drawDetections(canvasRef.current, resized)
        faceapi.draw.drawFaceLandmarks(canvasRef.current, resized)
      }
    }

    intervalRef.current = setInterval(detect, 2000)
    return () => clearInterval(intervalRef.current)
  }, [cameraActive, modelsLoaded])

  const addViolation = (type, message) => {
    statsRef.current.violations.push({ type, message, timestamp: Date.now() })
    if (onViolation) onViolation({ type, message })
  }

  return (
    <div style={{ position: 'relative', borderRadius: 12, overflow: 'hidden', background: '#000', width: '100%', maxWidth: 320 }}>
      <video
        ref={videoRef}
        autoPlay
        muted
        playsInline
        style={{ width: '100%', display: 'block', borderRadius: 12 }}
      />
      <canvas
        ref={canvasRef}
        style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%' }}
      />
      {/* Status overlay */}
      <div style={{
        position: 'absolute', top: 8, left: 8,
        background: status === 'active' ? 'rgba(16,185,129,0.85)' : status === 'camera denied' ? 'rgba(239,68,68,0.85)' : 'rgba(99,102,241,0.85)',
        color: '#fff', padding: '3px 10px', borderRadius: 20, fontSize: 11, fontWeight: 600
      }}>
        {status === 'active' ? '🟢 Proctoring' : status === 'camera denied' ? '🔴 Camera denied' : `⏳ ${status}`}
      </div>
    </div>
  )
})

Proctor.displayName = 'Proctor'
export default Proctor

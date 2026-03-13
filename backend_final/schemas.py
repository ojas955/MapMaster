from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime


# ─── Auth Schemas ──────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    email: EmailStr
    name: str
    password: str
    role: str = "student"  # student or admin

    @field_validator("role")
    @classmethod
    def role_must_be_valid(cls, v):
        if v not in ["student", "admin"]:
            raise ValueError("Role must be student or admin")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    role: str
    avatar_color: str
    xp_points: int
    streak_days: int
    preferred_language: str
    college: str = ""
    phone: str = ""
    bio: str = ""
    created_at: datetime

    class Config:
        from_attributes = True


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    college: Optional[str] = None
    phone: Optional[str] = None
    bio: Optional[str] = None
    preferred_language: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ─── PDF Schemas ───────────────────────────────────────────────────────────────

class PDFResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    num_pages: int
    language: str
    file_size_kb: float
    upload_date: datetime

    class Config:
        from_attributes = True


# ─── Assessment Schemas ────────────────────────────────────────────────────────

class QuestionSchema(BaseModel):
    id: int
    text: str
    type: str  # 'open_ended', 'scenario', 'audio'
    bloom_level: str  # apply/analyze/evaluate/create
    section_reference: str = ""
    max_score: int = 10
    rubric: Dict[str, str] = {}


class AssessmentCreate(BaseModel):
    title: str
    description: str = ""
    questions: List[QuestionSchema]
    difficulty: str = "intermediate"
    category: str = "General"
    time_limit_minutes: int = 30
    language: str = "en"
    tags: List[str] = []
    thumbnail_emoji: str = "📚"


class AssessmentResponse(BaseModel):
    id: int
    title: str
    description: str
    questions: List[Dict[str, Any]]
    difficulty: str
    category: str
    time_limit_minutes: int
    language: str
    tags: List[str]
    thumbnail_emoji: str
    created_at: datetime
    created_by: int
    pdf_id: Optional[int]

    class Config:
        from_attributes = True


# ─── Submission Schemas ────────────────────────────────────────────────────────

class SubmissionCreate(BaseModel):
    assessment_id: int
    answers: Dict[str, str]  # {question_index: answer_text}
    time_taken_seconds: int = 0
    anticheat_flags: Optional[Dict[str, Any]] = {}
    proctoring_data: Optional[Dict[str, Any]] = None
    visual_capture_ids: Optional[Dict[str, int]] = None


class SubmissionResponse(BaseModel):
    id: int
    user_id: int
    assessment_id: int
    answers: Dict[str, Any]
    scores: Optional[Dict[str, Any]]
    feedback: Optional[Dict[str, Any]]
    total_score: float
    max_score: float
    time_taken_seconds: int
    anticheat_flags: Optional[Dict[str, Any]]
    submitted_at: datetime
    evaluated_at: Optional[datetime]

    class Config:
        from_attributes = True


# ─── Certificate Schemas ───────────────────────────────────────────────────────

class CertificateResponse(BaseModel):
    id: int
    user_id: int
    submission_id: int
    qr_hash: str
    issued_at: datetime
    is_valid: bool
    cert_url: str = ""

    class Config:
        from_attributes = True


# ─── Analytics Schemas ────────────────────────────────────────────────────────

class SkillRadarData(BaseModel):
    labels: List[str]
    scores: List[float]


class StudentAnalytics(BaseModel):
    total_submissions: int
    average_score: float
    best_score: float
    xp_points: int
    streak_days: int
    skill_radar: SkillRadarData
    recent_submissions: List[Dict[str, Any]]
    pathway_steps: List[Dict[str, Any]]


class GroupAnalytics(BaseModel):
    assessment_id: int
    assessment_title: str
    total_participants: int
    average_score: float
    score_distribution: Dict[str, int]  # {'0-20': count, '21-40': count, ...}
    question_averages: List[float]

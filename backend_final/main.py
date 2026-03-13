import os
import sys
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from config import settings
from database import create_tables
from routes import auth_routes, pdf_routes, assessment_routes, submission_routes, certificate_routes, analytics_routes, user_routes

# ─── Add SkillSync backend to Python path ────────────────────────────────────
SKILLSYNC_BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skillsync-backend")
if os.path.isdir(SKILLSYNC_BACKEND_DIR):
    sys.path.insert(0, SKILLSYNC_BACKEND_DIR)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    create_tables()
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.CERT_DIR, exist_ok=True)

    # Auto-seed demo data if DB is empty
    try:
        from database import SessionLocal
        from models import User
        db = SessionLocal()
        if db.query(User).count() == 0:
            print("📦 Seeding demo data...")
            import seed_data
            seed_data.seed(db)
            print("✅ Demo data seeded!")
        db.close()
    except Exception as e:
        print(f"⚠️  Seed failed (non-critical): {e}")

    if not settings.GEMINI_API_KEY:
        print("⚠️  GEMINI_API_KEY not set — AI features will use fallback mode")
    else:
        print(f"✅ Gemini AI configured ({settings.GEMINI_MODEL})")

    yield
    print("👋 Shutting down KaushalyaAI")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-Driven Skill Assessment Platform — measures real skills, not rote knowledge",
    lifespan=lifespan
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin for origin in [
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            settings.FRONTEND_URL,
        ] if origin
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_routes.router)
app.include_router(pdf_routes.router)
app.include_router(assessment_routes.router)
app.include_router(submission_routes.router)
app.include_router(certificate_routes.router)
app.include_router(analytics_routes.router)
app.include_router(user_routes.router)

# Serve certificate files
if os.path.exists(settings.CERT_DIR):
    app.mount("/certificates", StaticFiles(directory=settings.CERT_DIR), name="certificates")

# ─── Mount SkillSync Coding Backend as Sub-Application ──────────────────────
# All SkillSync routes become available at /api/coding/*
# e.g. /api/coding/execute, /api/coding/submit, /api/coding/batch-submit
try:
    import importlib.util
    from fastapi.routing import APIRoute
    skillsync_main_path = os.path.join(SKILLSYNC_BACKEND_DIR, "main.py")
    if os.path.isfile(skillsync_main_path):
        spec = importlib.util.spec_from_file_location("skillsync_main", skillsync_main_path)
        skillsync_mod = importlib.util.module_from_spec(spec)
        sys.modules["skillsync_main"] = skillsync_mod
        spec.loader.exec_module(skillsync_mod)
        # Use include_router instead of mount() — mount() silently fails for
        # sub-apps loaded via importlib. include_router merges routes directly.
        skillsync_app = skillsync_mod.app
        app.router.include_router(skillsync_app.router, prefix="/api/coding")
        route_count = len([r for r in skillsync_app.routes if isinstance(r, APIRoute)])
        print(f"✅ SkillSync coding backend mounted at /api/coding ({route_count} routes)")
    else:
        print(f"⚠️  SkillSync main.py not found at {skillsync_main_path}")
except Exception as e:
    import traceback
    print(f"⚠️  SkillSync coding backend not mounted: {e}")
    traceback.print_exc()


@app.get("/")
def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
        "message": "AI-Driven Skill Assessment Platform 🧠⚡"
    }


@app.get("/health")
def health():
    return {"status": "healthy", "ai_enabled": bool(settings.GEMINI_API_KEY)}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)


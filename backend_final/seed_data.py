"""
Demo data seeder for SkillForge hackathon demo.
Run: python seed_data.py  OR  auto-runs on first startup.
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database import SessionLocal, create_tables
import models
from auth import get_password_hash


DEMO_ASSESSMENTS = [
    {
        "title": "Critical Thinking in Machine Learning",
        "description": "Evaluate your ability to analyze, apply, and critique ML concepts beyond memorization. Focuses on real-world application, bias detection, and model evaluation trade-offs.",
        "difficulty": "intermediate",
        "category": "Data Science",
        "time_limit_minutes": 25,
        "language": "en",
        "tags": ["ML", "critical-thinking", "AI"],
        "thumbnail_emoji": "🤖",
        "questions": [
            {
                "id": 1,
                "text": "A company's ML model achieves 97% accuracy on test data but performs poorly in production. Analyze at least three possible causes and explain how you would diagnose and resolve each systematically.",
                "type": "open_ended",
                "bloom_level": "analyze",
                "section_reference": "Model Evaluation and Deployment",
                "max_score": 10,
                "rubric": {
                    "depth": "Identifies multiple nuanced causes beyond simple overfitting",
                    "accuracy": "Technical explanations are correct (distribution shift, data leakage, etc.)",
                    "application": "Provides concrete diagnostic steps",
                    "originality": "Novel debugging approaches or tools mentioned"
                }
            },
            {
                "id": 2,
                "text": "You're building a hiring algorithm for a tech company. Describe how you would detect and mitigate bias in the training data and model outputs. What ethical frameworks would you apply?",
                "type": "scenario",
                "bloom_level": "evaluate",
                "section_reference": "AI Ethics and Fairness",
                "max_score": 10,
                "rubric": {
                    "depth": "Covers technical and ethical dimensions of bias",
                    "accuracy": "Correct use of fairness metrics and techniques",
                    "application": "Practical bias mitigation strategies",
                    "originality": "Creative governance or audit mechanisms"
                }
            },
            {
                "id": 3,
                "text": "Compare precision-recall trade-off vs ROC-AUC for evaluating a medical diagnosis model where false negatives are catastrophic. Which metric would you optimize for and why?",
                "type": "open_ended",
                "bloom_level": "evaluate",
                "section_reference": "Classification Metrics",
                "max_score": 10,
                "rubric": {
                    "depth": "Deep understanding of both metrics' implications",
                    "accuracy": "Correct mathematical understanding",
                    "application": "Medical context appropriately considered",
                    "originality": "Creative threshold selection strategies"
                }
            },
            {
                "id": 4,
                "text": "Design a machine learning pipeline for detecting fraudulent transactions in real-time for a bank processing 10,000 transactions/second. Address data, model, and infrastructure choices.",
                "type": "scenario",
                "bloom_level": "create",
                "section_reference": "Production ML Systems",
                "max_score": 10,
                "rubric": {
                    "depth": "Comprehensive system design coverage",
                    "accuracy": "Technically sound architecture",
                    "application": "Practical constraints (latency, scale) addressed",
                    "originality": "Innovative system design elements"
                }
            },
            {
                "id": 5,
                "text": "Explain how you would explain a complex neural network's decision to a non-technical stakeholder who's been denied a loan. What interpretability techniques would you use?",
                "type": "explanation",
                "bloom_level": "apply",
                "section_reference": "Explainable AI",
                "max_score": 10,
                "rubric": {
                    "depth": "Covers both technical tools and communication strategies",
                    "accuracy": "SHAP, LIME, or other XAI tools correctly described",
                    "application": "Adapted for non-technical audience effectively",
                    "originality": "Novel communication approaches"
                }
            }
        ]
    },
    {
        "title": "Software Architecture: Design Patterns & Trade-offs",
        "description": "Test your ability to apply, compare, and critique software design patterns and architectural decisions in realistic scenarios.",
        "difficulty": "advanced",
        "category": "Software Engineering",
        "time_limit_minutes": 35,
        "language": "en",
        "tags": ["architecture", "design-patterns", "engineering"],
        "thumbnail_emoji": "⚙️",
        "questions": [
            {
                "id": 1,
                "text": "A startup is migrating from a monolith to microservices. Analyze the risks of this migration for a team of 8 developers. When would you advise against it, and what intermediate patterns would you suggest?",
                "type": "scenario",
                "bloom_level": "evaluate",
                "section_reference": "Distributed Systems Architecture",
                "max_score": 10,
                "rubric": {
                    "depth": "Covers organizational, technical, and operational risks",
                    "accuracy": "Technically sound assessment",
                    "application": "Practical team-size and codebase considerations",
                    "originality": "Novel intermediate patterns (modular monolith, etc.)"
                }
            },
            {
                "id": 2,
                "text": "Design a notification system that needs to support email, SMS, push, and in-app notifications, with the ability to add new channels without modifying existing code. Which design pattern(s) would you use and why?",
                "type": "open_ended",
                "bloom_level": "create",
                "section_reference": "OOP Design Patterns",
                "max_score": 10,
                "rubric": {
                    "depth": "Pattern selection with strong justification",
                    "accuracy": "Correct pattern implementation described",
                    "application": "Extensibility requirements addressed",
                    "originality": "Creative combination of patterns"
                }
            },
            {
                "id": 3,
                "text": "You discover that 80% of your application's database queries come from just 3 endpoints. How would you approach optimizing performance? Discuss query optimization, caching strategies, and when each is appropriate.",
                "type": "scenario",
                "bloom_level": "apply",
                "section_reference": "Performance Optimization",
                "max_score": 10,
                "rubric": {
                    "depth": "Multi-layer optimization strategy",
                    "accuracy": "Correct caching and query optimization techniques",
                    "application": "Prioritization and measurement approach",
                    "originality": "Unconventional optimization ideas"
                }
            }
        ]
    },
    {
        "title": "Entrepreneurship & Business Strategy",
        "description": "Higher-order thinking assessment on startup strategy, market analysis, and business model innovation. For MBA and business students.",
        "difficulty": "intermediate",
        "category": "Business",
        "time_limit_minutes": 30,
        "language": "en",
        "tags": ["startup", "strategy", "MBA"],
        "thumbnail_emoji": "💼",
        "questions": [
            {
                "id": 1,
                "text": "A competitor just launched a product identical to yours with VC backing and is undercutting your price by 40%. You have 6 months of runway. Analyze your strategic options and their trade-offs.",
                "type": "scenario",
                "bloom_level": "evaluate",
                "section_reference": "Competitive Strategy",
                "max_score": 10,
                "rubric": {
                    "depth": "Comprehensive competitive response analysis",
                    "accuracy": "Sound strategic frameworks applied",
                    "application": "Resource constraints realistically considered",
                    "originality": "Unconventional competitive responses"
                }
            },
            {
                "id": 2,
                "text": "Critique the freemium business model using at least two real-world examples. Under what conditions does it work, and when does it fail? Propose a hybrid model that could work better in a specific industry.",
                "type": "open_ended",
                "bloom_level": "create",
                "section_reference": "Business Model Innovation",
                "max_score": 10,
                "rubric": {
                    "depth": "Deep analysis of freemium dynamics",
                    "accuracy": "Correct examples and analysis",
                    "application": "Industry-specific considerations",
                    "originality": "Innovative hybrid model design"
                }
            }
        ]
    },
    {
        "title": "KaushalyaAI Platform Orientation",
        "description": "A beginner-friendly introductory assessment to get familiar with the KaushalyaAI platform and higher-order thinking. Take this first!",
        "difficulty": "beginner",
        "category": "Orientation",
        "time_limit_minutes": 15,
        "language": "en",
        "tags": ["intro", "beginner", "orientation"],
        "thumbnail_emoji": "🌟",
        "questions": [
            {
                "id": 1,
                "text": "Describe a skill you've learned in the past year. How did you learn it, what challenges did you face, and how have you applied it in a real situation?",
                "type": "open_ended",
                "bloom_level": "apply",
                "section_reference": "Learning & Application",
                "max_score": 10,
                "rubric": {
                    "depth": "Reflective and thoughtful self-analysis",
                    "accuracy": "Honest and specific about the experience",
                    "application": "Real application described concretely",
                    "originality": "Personal insights and reflection"
                }
            },
            {
                "id": 2,
                "text": "If you could redesign how your school or workplace evaluates performance, what would you change and why? What would better metrics look like?",
                "type": "open_ended",
                "bloom_level": "create",
                "section_reference": "Assessment Design",
                "max_score": 10,
                "rubric": {
                    "depth": "Thoughtful critique of current systems",
                    "accuracy": "Feasible improvements proposed",
                    "application": "Context-specific solutions",
                    "originality": "Creative and novel evaluation approaches"
                }
            }
        ]
    }
]


def seed(db: Session):
    """Seed demo data into the database."""

    # Create admin user
    admin = models.User(
        email="admin@kaushalya.ai",
        name="Prof. Arjun Sharma",
        hashed_password=get_password_hash("admin123"),
        role="admin",
        avatar_color="#6366f1",
        xp_points=5000,
        streak_days=30
    )
    db.add(admin)

    # Create student users
    students = [
        models.User(
            email="student@kaushalya.ai",
            name="Priya Patel",
            hashed_password=get_password_hash("student123"),
            role="student",
            avatar_color="#8b5cf6",
            xp_points=1250,
            streak_days=7
        ),
        models.User(
            email="rahul@kaushalya.ai",
            name="Rahul Mehta",
            hashed_password=get_password_hash("student123"),
            role="student",
            avatar_color="#06b6d4",
            xp_points=890,
            streak_days=3
        ),
        models.User(
            email="sneha@kaushalya.ai",
            name="Sneha Kulkarni",
            hashed_password=get_password_hash("student123"),
            role="student",
            avatar_color="#10b981",
            xp_points=2100,
            streak_days=14
        )
    ]
    for s in students:
        db.add(s)

    db.flush()  # Get IDs

    # Create assessments
    assessment_records = []
    for a_data in DEMO_ASSESSMENTS:
        a = models.Assessment(
            title=a_data["title"],
            description=a_data["description"],
            questions=a_data["questions"],
            difficulty=a_data["difficulty"],
            category=a_data["category"],
            time_limit_minutes=a_data["time_limit_minutes"],
            language=a_data["language"],
            created_by=admin.id,
            tags=a_data["tags"],
            thumbnail_emoji=a_data["thumbnail_emoji"],
            is_active=True
        )
        db.add(a)
        assessment_records.append(a)

    db.flush()

    # Create sample submissions for demo
    sample_submission = models.Submission(
        user_id=students[0].id,
        assessment_id=assessment_records[0].id,
        answers={
            "0": "The model likely suffers from distribution shift, where training data doesn't match production data. Additionally, there could be data leakage during training causing inflated test metrics. I would investigate by monitoring feature distributions in production, checking for time-based splits in training data, and implementing model monitoring with drift detection.",
            "1": "To detect bias, I would audit training data for underrepresentation of groups, apply fairness metrics like demographic parity and equalized odds. I would use techniques like re-weighting, adversarial debiasing, and post-processing calibration. Ethically, I'd follow IEEE guidelines and implement regular auditing with diverse stakeholders.",
            "2": "For medical diagnosis, I would optimize for recall (sensitivity) to minimize false negatives, as missing a disease is catastrophic. ROC-AUC provides an overall view but doesn't capture domain-specific costs. I'd set the decision threshold based on the cost ratio of false negatives to false positives, potentially accepting lower precision.",
        },
        scores={
            "0": {"depth": 8.0, "accuracy": 8.5, "application": 7.5, "originality": 7.0},
            "1": {"depth": 9.0, "accuracy": 8.0, "application": 8.5, "originality": 8.0},
            "2": {"depth": 8.5, "accuracy": 9.0, "application": 8.0, "originality": 7.5},
        },
        feedback={
            "0": "Excellent identification of distribution shift and data leakage. Strong diagnostic approach. Could expand on monitoring infrastructure choices.",
            "1": "Comprehensive coverage of both technical and ethical dimensions. Good use of specific fairness metrics.",
            "2": "Strong prioritization of recall for medical context. Good mathematical understanding of the threshold trade-off.",
        },
        total_score=82.5,
        max_score=100.0,
        time_taken_seconds=1450,
        anticheat_flags={
            "tab_switches": 0,
            "copy_paste_count": 0,
            "risk_level": "low",
            "overall_integrity_score": 100,
            "flags_triggered": []
        },
        evaluated_at=datetime.utcnow() - timedelta(days=1)
    )
    db.add(sample_submission)
    db.flush()

    # Create a certificate for the demo submission
    import hashlib
    qr_hash = hashlib.sha256(f"demo_cert_{sample_submission.id}".encode()).hexdigest()[:32]
    cert = models.Certificate(
        user_id=students[0].id,
        submission_id=sample_submission.id,
        cert_filename=f"cert_{qr_hash}.png",
        qr_hash=qr_hash,
        is_valid=True
    )
    db.add(cert)

    # Create pathway step
    pathway = models.PathwayStep(
        user_id=students[0].id,
        source_assessment_id=assessment_records[0].id,
        reason="Strong performance in analysis! Focus on synthesis skills to level up to advanced content.",
        skill_gaps=["Synthesis", "System Design"],
        recommended_topics=["Software Architecture Assessment", "Entrepreneurship Assessment"]
    )
    db.add(pathway)

    db.commit()
    print(f"✅ Seeded: 4 users, {len(DEMO_ASSESSMENTS)} assessments, 1 demo submission, 1 certificate")


if __name__ == "__main__":
    create_tables()
    db = SessionLocal()
    try:
        from models import User
        if db.query(User).count() > 0:
            print("⚠️  Database already has data. To reset: delete kaushalya.db and re-run.")
        else:
            seed(db)
    finally:
        db.close()

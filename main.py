from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import joblib
import pandas as pd
import os
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLASS_MODEL_PATH = os.path.join(BASE_DIR, "model", "student_model.joblib")
SCORE_MODEL_PATH = os.path.join(BASE_DIR, "model", "student_score_model.joblib")
CONFIG_PATH = os.path.join(BASE_DIR, "model", "feature_config.json")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
INDEX_HTML = os.path.join(FRONTEND_DIR, "index.html")

app = FastAPI(
    title="AI Student Performance Prediction API",
    description="Predicts pass/fail, estimated score and gives study suggestions.",
    version="1.3.0",
)

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


class StudentFeatures(BaseModel):
    # Features used by ML model
    hours_study_per_day: float = Field(..., ge=0, le=24)
    past_average_score: float = Field(..., ge=0, le=100)
    absences: int = Field(..., ge=0)
    parent_education: str
    internet: str
    health: int = Field(..., ge=1, le=5)

    # Extra questions (only used for advice, not for ML)
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    screen_time_hours: float | None = Field(default=None, ge=0, le=24)
    exam_stress_level: int | None = Field(default=None, ge=1, le=5)
    has_study_plan: bool | None = None


class ParentMessagePayload(BaseModel):
    mobile: str
    message: str


def load_class_model():
    if not os.path.exists(CLASS_MODEL_PATH):
        raise FileNotFoundError(
            f"Classification model not found at {CLASS_MODEL_PATH}. "
            "Please run 'python model/train_model.py' first."
        )
    return joblib.load(CLASS_MODEL_PATH)


def load_score_model():
    if not os.path.exists(SCORE_MODEL_PATH):
        raise FileNotFoundError(
            f"Score model not found at {SCORE_MODEL_PATH}. "
            "Please run 'python model/train_model.py' first."
        )
    return joblib.load(SCORE_MODEL_PATH)


def load_config():
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(
            f"Config not found at {CONFIG_PATH}. "
            "Please run 'python model/train_model.py' first."
        )
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_suggestions(features: StudentFeatures, proba: float) -> dict:
    suggestions: list[str] = []

    # Risk by probability
    if proba >= 0.85:
        risk_level = "low"
        suggestions.append("You are on a good track. Keep your current habits consistent.")
    elif proba >= 0.65:
        risk_level = "medium"
        suggestions.append("You are doing okay, but a bit more consistency can push you higher.")
    else:
        risk_level = "high"
        suggestions.append("You are at risk. You need a proper study plan and regular routine.")

    # Study hours
    if features.hours_study_per_day < 1:
        suggestions.append("Increase focused study time to at least 1–2 hours per day on weekdays.")
    elif 1 <= features.hours_study_per_day < 2:
        suggestions.append("Try to reach 2+ hours of distraction-free study per day for better results.")
    else:
        suggestions.append("You already study decent hours. Focus on quality (no phone, no multitasking).")

    # Absences
    if features.absences > 10:
        suggestions.append("Your absences are high. Try not to miss important classes and labs.")
    elif 5 <= features.absences <= 10:
        suggestions.append("Reduce absences. Even small gaps in topics can reduce your confidence in exams.")

    # Past score
    if features.past_average_score < 50:
        suggestions.append("Revise previous semester basics. Weak fundamentals affect current performance.")
    elif 50 <= features.past_average_score < 70:
        suggestions.append("Solve more practice questions and previous year papers to push your score up.")
    else:
        suggestions.append("You have good academic history. Aim for consistency and avoid last-minute stress.")

    # Health
    if features.health <= 2:
        suggestions.append("Take care of your health: proper sleep, water, and short breaks while studying.")
    elif features.health == 3:
        suggestions.append("Maintain a balanced lifestyle. Small improvements in sleep and diet will help focus.")

    # Extra optional fields
    if features.sleep_hours is not None:
        if features.sleep_hours < 6:
            suggestions.append("You are sleeping very less. Aim for 7–8 hours of sleep for better memory & focus.")
        elif features.sleep_hours > 9:
            suggestions.append("Too much sleep can also reduce productivity. Try to stabilise around 7–8 hours.")

    if features.screen_time_hours is not None:
        if features.screen_time_hours > 5:
            suggestions.append("Reduce screen time (social media / reels) especially during study hours.")
        elif 3 <= features.screen_time_hours <= 5:
            suggestions.append("Keep your phone away while studying to avoid losing focus.")
        else:
            suggestions.append("Good control over screen time. Keep treating your time as valuable.")

    if features.exam_stress_level is not None:
        if features.exam_stress_level >= 4:
            suggestions.append("You seem very stressed. Use short revision slots + mock tests to build confidence.")
        elif features.exam_stress_level == 3:
            suggestions.append("Mild exam stress is normal. Convert it to motivation by following a simple daily plan.")
        else:
            suggestions.append("You handle exam pressure well. Help friends who struggle with stress, if you can.")

    if features.has_study_plan is not None:
        if not features.has_study_plan:
            suggestions.append("Create a simple weekly study plan (what to study each day) and stick to it.")
        else:
            suggestions.append("You already have a study plan. Review and refine it every Sunday for next week.")

    return {"risk_level": risk_level, "suggestions": suggestions}


@app.get("/")
def root():
    if os.path.exists(INDEX_HTML):
        return FileResponse(INDEX_HTML)
    return {
        "message": "AI Student Performance Prediction API",
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/api/info")
def api_info():
    return {
        "message": "AI Student Performance Prediction API",
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.post("/predict")
def predict_performance(features: StudentFeatures):
    try:
        class_model = load_class_model()
        score_model = load_score_model()
        config = load_config()
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))

    try:
        feature_order = config.get("feature_order")
        if not feature_order:
            raise ValueError("feature_order missing in feature_config.json")

        data = {name: [getattr(features, name)] for name in feature_order}
        X = pd.DataFrame(data)

        proba = class_model.predict_proba(X)[0][1]
        pred = int(proba >= 0.5)

        raw_score = float(score_model.predict(X)[0])
        estimated_score = max(0.0, min(100.0, raw_score))

        if hasattr(features, "model_dump"):
            inputs = features.model_dump()
        else:
            inputs = features.dict()

        advice = generate_suggestions(features, proba)

        return {
            "passed": bool(pred),
            "probability_pass": float(proba),
            "estimated_score": round(estimated_score, 1),
            "risk_level": advice["risk_level"],
            "suggestions": advice["suggestions"],
            "inputs": inputs,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction error: {e}")


@app.post("/send-parent-message")
def send_parent_message(payload: ParentMessagePayload):
    """
    Simulated SMS/email sending endpoint.
    In a real system, this is where we'd integrate Twilio / SMS gateway / email SMTP.
    """
    mobile = payload.mobile.strip()
    if not mobile or len(mobile) < 8:
        raise HTTPException(status_code=400, detail="Invalid mobile number.")

    # Simulate sending: log to console for demo
    print("=== PARENT MESSAGE SENT ===")
    print(f"Mobile: {mobile}")
    print("Message:")
    print(payload.message)
    print("===========================")

    return {
        "status": "ok",
        "detail": f"Message prepared for sending to parent at {mobile} (simulated).",
    }

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import models
import schemas
from auth import get_current_user
from database import get_db

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("/me", response_model=schemas.UserResponse)
def get_profile(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.put("/profile", response_model=schemas.UserResponse)
def update_profile(
    data: schemas.ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if data.name is not None:
        current_user.name = data.name
    if data.college is not None:
        current_user.college = data.college
    if data.phone is not None:
        current_user.phone = data.phone
    if data.bio is not None:
        current_user.bio = data.bio
    if data.preferred_language is not None:
        current_user.preferred_language = data.preferred_language

    db.commit()
    db.refresh(current_user)
    return current_user

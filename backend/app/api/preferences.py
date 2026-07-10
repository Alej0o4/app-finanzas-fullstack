from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user
from app.models import models
from app.schemas import schemas

router = APIRouter()


@router.get("/me/preferences")
def get_preferences(current_user: models.User = Depends(get_current_user)):
    return {
        "preferred_currency": current_user.preferred_currency,
        "preferred_locale": current_user.preferred_locale,
        "preferred_theme": current_user.preferred_theme,
    }


@router.patch("/me/preferences")
def update_preferences(
    prefs: schemas.PreferencesUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    update_data = prefs.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return {
        "preferred_currency": current_user.preferred_currency,
        "preferred_locale": current_user.preferred_locale,
        "preferred_theme": current_user.preferred_theme,
    }

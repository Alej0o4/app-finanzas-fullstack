from fastapi import APIRouter, Depends
from app.core.security import get_current_user
from app.models import models

router = APIRouter()


@router.get("/me/preferences")
def get_preferences(current_user: models.User = Depends(get_current_user)):
    return {
        "preferred_currency": current_user.preferred_currency,
        "preferred_locale": current_user.preferred_locale,
        "theme": "dark",
    }

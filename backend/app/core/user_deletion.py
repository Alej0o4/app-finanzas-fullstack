"""Borrado físico de un usuario y todo lo que le pertenece (Fase 21 §21.2).

Compartido entre el endpoint `DELETE /api/v1/users/me` y el script de limpieza por
`python -c` (Decisión A2/A5 de docs/specs/fase_21_spec.md) — una sola copia de la
cascada, sin lógica de borrado duplicada en ningún punto del código.
"""

from sqlalchemy.orm import Session

from app.models import models


def delete_user_cascade(db: Session, user: models.User) -> None:
    """Borra físicamente un usuario y todo lo que le pertenece, en el orden que exigen
    las FKs (ninguna tiene ondelete=CASCADE — ver Hallazgo 3 de docs/specs/fase_21_spec.md).
    Una sola transacción: el caller hace el único db.commit() al final."""
    # HiddenCategory primero: referencia tanto users.id como categories.id, y Category
    # se borra más abajo en este mismo método (Decisión A2).
    db.query(models.HiddenCategory).filter(models.HiddenCategory.user_id == user.id).delete()
    db.query(models.Notification).filter(models.Notification.user_id == user.id).delete()
    db.query(models.PushSubscription).filter(models.PushSubscription.user_id == user.id).delete()
    db.query(models.ApiKey).filter(models.ApiKey.user_id == user.id).delete()
    db.query(models.Budget).filter(models.Budget.user_id == user.id).delete()
    # IdempotencyKey.transaction_id -> transactions.id: antes de Transaction.
    db.query(models.IdempotencyKey).filter(models.IdempotencyKey.user_id == user.id).delete()
    db.query(models.Transaction).filter(models.Transaction.user_id == user.id).delete()
    db.query(models.Account).filter(models.Account.user_id == user.id).delete()
    db.query(models.Category).filter(models.Category.user_id == user.id).delete()
    db.query(models.RefreshToken).filter(models.RefreshToken.user_id == user.id).delete()
    db.query(models.PasswordResetToken).filter(models.PasswordResetToken.user_id == user.id).delete()
    db.query(models.EmailVerificationToken).filter(models.EmailVerificationToken.user_id == user.id).delete()
    db.delete(user)


def delete_user_by_email(db: Session, email: str) -> bool:
    """Wrapper para el script de limpieza (Decisión A5) — resuelve por email, no persigue
    la sesión de un usuario autenticado. Devuelve False si el email no existe, sin lanzar."""
    user = db.query(models.User).filter(models.User.email == email.lower().strip()).first()
    if user is None:
        return False
    delete_user_cascade(db, user)
    db.commit()
    return True

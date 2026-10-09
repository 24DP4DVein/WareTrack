from sqlalchemy.orm import Session

from app.models import ActivityLog, User


def log_activity(db: Session, user: User | None, action: str, entity_type: str, entity_id: object, message: str) -> None:
    db.add(ActivityLog(user_id=user.id if user else None, action=action, entity_type=entity_type,
                       entity_id=str(entity_id) if entity_id is not None else None, message=message))


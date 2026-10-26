from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import ActivityLog, InventoryBalance, Item, Transfer, User

router = APIRouter(tags=["Kopsavilkums un atskaites"])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    items = list(db.scalars(select(Item).options(selectinload(Item.inventory_balances))))
    transfers = list(db.scalars(select(Transfer)))
    activities = list(db.scalars(select(ActivityLog).options(joinedload(ActivityLog.user)).order_by(ActivityLog.created_at.desc()).limit(8)))
    return {
        "totalItems": len(items), "totalUnits": sum(sum(b.quantity for b in i.inventory_balances) for i in items),
        "lowStockCount": sum(
            i.min_stock * .3 < sum(b.quantity for b in i.inventory_balances) < i.min_stock
            for i in items
        ),
        "criticalStockCount": sum(
            sum(b.quantity for b in i.inventory_balances) <= i.min_stock * .3
            for i in items
        ),
        "activeTransfers": sum(t.status in {"pending", "in-transit"} for t in transfers),
        "stockValue": round(sum(sum(b.quantity for b in i.inventory_balances) * i.price for i in items), 2),
        "activities": [{"id": a.id, "message": a.message, "userName": a.user.name if a.user else None,
                        "createdAt": a.created_at.isoformat()} for a in activities],
    }


@router.get("/reports")
def reports(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    items = list(db.scalars(select(Item).options(joinedload(Item.category), selectinload(Item.inventory_balances))))
    transfers = list(db.scalars(select(Transfer).options(joinedload(Transfer.item))))
    completed = [t for t in transfers if t.status == "done"]
    distribution: dict[str, int] = {}
    for item in items:
        distribution[item.category.name] = distribution.get(item.category.name, 0) + sum(
            balance.quantity for balance in item.inventory_balances
        )
    movement: dict[str, int] = {}
    for t in completed: movement[t.item.name] = movement.get(t.item.name, 0) + t.quantity
    return {
        "totalUnits": sum(sum(b.quantity for b in i.inventory_balances) for i in items),
        "totalValue": round(sum(sum(b.quantity for b in i.inventory_balances) * i.price for i in items), 2),
        "completedTransfers": len(completed),
        "lowStockCount": sum(sum(b.quantity for b in i.inventory_balances) < i.min_stock for i in items),
        "categoryDistribution": [{"name": k, "units": v} for k, v in distribution.items()],
        "topItems": [{"name": k, "movement": v} for k, v in sorted(movement.items(), key=lambda p: p[1], reverse=True)[:5]],
    }


@router.get("/activity")
def activity(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.scalars(select(ActivityLog).options(joinedload(ActivityLog.user)).order_by(ActivityLog.created_at.desc()).limit(50))
    return [{"id": a.id, "message": a.message, "action": a.action, "entityType": a.entity_type,
             "userName": a.user.name if a.user else None, "createdAt": a.created_at.isoformat()} for a in rows]


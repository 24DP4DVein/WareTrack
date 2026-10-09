from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_admin
from app.database import get_db
from app.models import Category, Item, Location, Supplier, User
from app.schemas import CategoryIn, CategoryOut, LocationIn, LocationOut, SupplierIn, SupplierOut
from app.services.activity import log_activity

categories = APIRouter(prefix="/categories", tags=["Kategorijas"])
suppliers = APIRouter(prefix="/suppliers", tags=["Pieg?üd?üt?üji"])
locations = APIRouter(prefix="/locations", tags=["Noliktavas vietas"])


def category_out(c: Category, count: int) -> CategoryOut:
    return CategoryOut(id=c.id, name=c.name, description=c.description, icon=c.icon, color=c.color,
                       item_count=count, created_at=c.created_at)


@categories.get("", response_model=list[CategoryOut])
def category_list(db: Session = Depends(get_db)):
    rows = db.execute(select(Category, func.count(Item.id)).outerjoin(Item).group_by(Category.id).order_by(Category.name)).all()
    return [category_out(c, count) for c, count in rows]


@categories.get("/{category_id}", response_model=CategoryOut)
def category_get(category_id: int, db: Session = Depends(get_db)):
    category = db.get(Category, category_id)
    if not category:
        raise HTTPException(404, "Kategorija nav atrasta")
    count = db.scalar(select(func.count(Item.id)).where(Item.category_id == category.id)) or 0
    return category_out(category, count)


@categories.post("", response_model=CategoryOut, status_code=201)
def category_create(data: CategoryIn, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    category = Category(**data.model_dump())
    db.add(category)
    try:
        db.flush()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, "Kategorija ar ?Ī?üdu nosaukumu jau past?üv")
    log_activity(db, user, "create", "category", category.id, f"Izveidota kategorija ŌĆ£{category.name}ŌĆØ")
    db.commit(); db.refresh(category)
    return category_out(category, 0)


@categories.put("/{category_id}", response_model=CategoryOut)
def category_update(category_id: int, data: CategoryIn, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    category = db.get(Category, category_id)
    if not category: raise HTTPException(404, "Kategorija nav atrasta")
    for key, value in data.model_dump().items(): setattr(category, key, value)
    try: db.flush()
    except IntegrityError: db.rollback(); raise HTTPException(409, "Kategorija ar ?Ī?üdu nosaukumu jau past?üv")
    log_activity(db, user, "update", "category", category.id, f"Atjaunin?üta kategorija ŌĆ£{category.name}ŌĆØ")
    count = db.scalar(select(func.count(Item.id)).where(Item.category_id == category.id)) or 0
    db.commit(); db.refresh(category)
    return category_out(category, count)


@categories.delete("/{category_id}", status_code=204)
def category_delete(category_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    category = db.get(Category, category_id)
    if not category: raise HTTPException(404, "Kategorija nav atrasta")
    if category.items: raise HTTPException(409, "Nevar dz?ōst kategoriju, kurai piesaist?½tas preces")
    name = category.name; db.delete(category)
    log_activity(db, user, "delete", "category", category_id, f"Dz?ōsta kategorija ŌĆ£{name}ŌĆØ")
    db.commit()


@suppliers.get("", response_model=list[SupplierOut])
def supplier_list(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return list(db.scalars(select(Supplier).order_by(Supplier.name)))


@suppliers.get("/{supplier_id}", response_model=SupplierOut)
def supplier_get(supplier_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(404, "Pieg?üd?üt?üjs nav atrasts")
    return supplier


@suppliers.post("", response_model=SupplierOut, status_code=201)
def supplier_create(data: SupplierIn, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    supplier = Supplier(**data.model_dump()); db.add(supplier)
    try: db.flush()
    except IntegrityError: db.rollback(); raise HTTPException(409, "Pieg?üd?üt?üja nosaukums vai e-pasts jau tiek izmantots")
    log_activity(db, user, "create", "supplier", supplier.id, f"Izveidots pieg?üd?üt?üjs ŌĆ£{supplier.name}ŌĆØ")
    db.commit(); db.refresh(supplier); return supplier


@suppliers.put("/{supplier_id}", response_model=SupplierOut)
def supplier_update(supplier_id: int, data: SupplierIn, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    supplier = db.get(Supplier, supplier_id)
    if not supplier: raise HTTPException(404, "Pieg?üd?üt?üjs nav atrasts")
    for key, value in data.model_dump().items(): setattr(supplier, key, value)
    try: db.flush()
    except IntegrityError: db.rollback(); raise HTTPException(409, "Pieg?üd?üt?üja nosaukums vai e-pasts jau tiek izmantots")
    log_activity(db, user, "update", "supplier", supplier.id, f"Atjaunin?üts pieg?üd?üt?üjs ŌĆ£{supplier.name}ŌĆØ")
    db.commit(); db.refresh(supplier); return supplier


@suppliers.delete("/{supplier_id}", status_code=204)
def supplier_delete(supplier_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    supplier = db.get(Supplier, supplier_id)
    if not supplier: raise HTTPException(404, "Pieg?üd?üt?üjs nav atrasts")
    if supplier.items: raise HTTPException(409, "Nevar dz?ōst pieg?üd?üt?üju, kuram piesaist?½tas preces")
    name = supplier.name; db.delete(supplier)
    log_activity(db, user, "delete", "supplier", supplier_id, f"Dz?ōsts pieg?üd?üt?üjs ŌĆ£{name}ŌĆØ")
    db.commit()


def location_out(location: Location, used: int) -> LocationOut:
    return LocationOut(id=location.id, code=location.code, name=location.name, capacity=location.capacity,
                       used_capacity=used, created_at=location.created_at)


@locations.get("", response_model=list[LocationOut])
def location_list(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.execute(select(Location, func.coalesce(func.sum(Item.stock), 0)).outerjoin(Item).group_by(Location.id).order_by(Location.code)).all()
    return [location_out(location, int(used)) for location, used in rows]


@locations.get("/{location_id}", response_model=LocationOut)
def location_get(location_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    location = db.get(Location, location_id)
    if not location:
        raise HTTPException(404, "Noliktavas vieta nav atrasta")
    used = db.scalar(select(func.coalesce(func.sum(Item.stock), 0)).where(Item.location_id == location.id)) or 0
    return location_out(location, int(used))


@locations.post("", response_model=LocationOut, status_code=201)
def location_create(data: LocationIn, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    location = Location(**data.model_dump()); db.add(location)
    try: db.flush()
    except IntegrityError: db.rollback(); raise HTTPException(409, "Vietas kods jau tiek izmantots")
    log_activity(db, user, "create", "location", location.id, f"Izveidota vieta ŌĆ£{location.name}ŌĆØ")
    db.commit(); db.refresh(location); return location_out(location, 0)


@locations.put("/{location_id}", response_model=LocationOut)
def location_update(location_id: int, data: LocationIn, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    location = db.get(Location, location_id)
    if not location: raise HTTPException(404, "Noliktavas vieta nav atrasta")
    for key, value in data.model_dump().items(): setattr(location, key, value)
    db.commit(); db.refresh(location)
    used = db.scalar(select(func.coalesce(func.sum(Item.stock), 0)).where(Item.location_id == location.id)) or 0
    return location_out(location, int(used))


@locations.delete("/{location_id}", status_code=204)
def location_delete(location_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    location = db.get(Location, location_id)
    if not location: raise HTTPException(404, "Noliktavas vieta nav atrasta")
    if location.items: raise HTTPException(409, "Nevar dz?ōst vietu, kur?ü ir preces")
    db.delete(location); db.commit()


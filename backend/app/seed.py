import os

from sqlalchemy import select

from app.auth.security import hash_password
from app.database import Base, SessionLocal, engine
from app.migrations import migrate_legacy_inventory, migrate_user_roles
from app.models import ActivityLog, Category, InventoryBalance, Item, Location, Role, StockMovement, Supplier, Transfer, User


def add_realistic_catalog(db, actor: User) -> int:
    """Add missing demo catalog rows without changing user-created data."""
    category_data = {
        "Elektropreces": ("Elektronika un biroja tehnika", "Laptop", "blue"),
        "Iepakojums": ("Iepakošanas un nosūtīšanas materiāli", "Package", "amber"),
        "Darba drošība": ("Individuālie aizsardzības līdzekļi", "Shield", "green"),
        "Instrumenti": ("Noliktavas un darbnīcas instrumenti", "Wrench", "purple"),
    }
    categories = {}
    for name, (description, icon, color) in category_data.items():
        category = db.scalar(select(Category).where(Category.name == name))
        if not category:
            category = Category(name=name, description=description, icon=icon, color=color)
            db.add(category)
            db.flush()
        categories[name] = category

    supplier_data = {
        "Rīgas Loģistika SIA": ("Laura Ozola", "pasutijumi@rigaslogistika.lv", "+371 67123456", "Dzelzavas iela 12, Rīga, LV-1084", "Iepakojums", "net30"),
        "Baltijas Tehnika SIA": ("Mārtiņš Bērziņš", "info@baltijastehnika.lv", "+371 63001234", "Aviācijas iela 8, Jelgava, LV-3004", "Elektropreces", "net30"),
        "Kurzemes Darba Apģērbs SIA": ("Ilze Liepa", "klienti@kda.lv", "+371 63456789", "Ganību iela 99, Liepāja, LV-3401", "Darba drošība", "net60"),
    }
    suppliers = {}
    for name, values in supplier_data.items():
        supplier = db.scalar(select(Supplier).where(Supplier.name == name))
        if not supplier:
            supplier = Supplier(name=name, contact_person=values[0], email=values[1], phone=values[2], address=values[3], category=values[4], payment_terms=values[5])
            db.add(supplier)
            db.flush()
        suppliers[name] = supplier

    location_data = {
        "RIG-A01": ("Rīga — A zona, 1. plaukts", 500),
        "RIG-B01": ("Rīga — B zona, 1. plaukts", 800),
        "RIG-C01": ("Rīga — C zona, 1. plaukts", 600),
        "JEL-A01": ("Jelgava — A zona", 700),
    }
    locations = {}
    for code, (name, capacity) in location_data.items():
        location = db.scalar(select(Location).where(Location.code == code))
        if not location:
            location = Location(code=code, name=name, capacity=capacity)
            db.add(location)
            db.flush()
        locations[code] = location

    product_data = [
        ("Bezvadu svītrkodu skeneris Honeywell 1472G", "SCN-1472G", "Elektropreces", "Baltijas Tehnika SIA", "RIG-A01", 18, 6, 149.00),
        ("Termoprintera etiķetes 58×40 mm, 1000 gab.", "ETK-5840", "Iepakojums", "Rīgas Loģistika SIA", "RIG-B01", 180, 50, 12.50),
        ("Stiepjamā plēve 500 mm × 300 m", "PLE-500300", "Iepakojums", "Rīgas Loģistika SIA", "RIG-B01", 34, 12, 8.90),
        ("Nitrila darba cimdi, L izmērs, 100 gab.", "CIM-NIT-L", "Darba drošība", "Kurzemes Darba Apģērbs SIA", "RIG-C01", 26, 10, 9.75),
        ("Aizsargbrilles ar pretmiglas pārklājumu", "BRL-AIZ-01", "Darba drošība", "Kurzemes Darba Apģērbs SIA", "RIG-C01", 14, 8, 4.60),
        ("Rokas palešu ratiņi 2500 kg", "PAL-2500", "Instrumenti", "Baltijas Tehnika SIA", "JEL-A01", 3, 1, 385.00),
        ("Plastmasas uzglabāšanas kaste 60 l", "KST-PL-60", "Iepakojums", "Rīgas Loģistika SIA", "JEL-A01", 42, 15, 14.80),
        ("USB termoprinteris etiķetēm", "PRN-USB-01", "Elektropreces", "Baltijas Tehnika SIA", "RIG-A01", 5, 2, 189.00),
    ]
    added = 0
    for name, sku, category_name, supplier_name, location_code, quantity, minimum, price in product_data:
        if db.scalar(select(Item).where(Item.sku == sku)):
            continue
        item = Item(name=name, sku=sku, category_id=categories[category_name].id,
                    supplier_id=suppliers[supplier_name].id, min_stock=minimum, price=price)
        db.add(item)
        db.flush()
        db.add(InventoryBalance(item_id=item.id, location_id=locations[location_code].id, quantity=quantity))
        db.add(StockMovement(item_id=item.id, destination_location_id=locations[location_code].id,
                             quantity=quantity, action="initial_receipt", user_id=actor.id))
        added += 1

    if added:
        db.add(ActivityLog(user_id=actor.id, action="seed", entity_type="system", entity_id=None,
                           message=f"Pievienotas {added} reālistiskas demo preces"))
    return added


def seed():
    environment = os.getenv("WARETRACK_ENV", os.getenv("ENVIRONMENT", "production")).lower()
    if environment not in {"development", "test"}:
        raise RuntimeError("Demo seed data is restricted to development and test environments")
    Base.metadata.create_all(bind=engine)
    migrate_legacy_inventory(engine)
    migrate_user_roles(engine)
    db = SessionLocal()
    try:
        existing_user = db.scalar(select(User).limit(1))
        demo_accounts = [
            ("WareTrack administrators", "admin@waretrack.lv", "Admin123!", Role.ADMIN),
            ("Noliktavas vadītājs", "manager@waretrack.lv", "Manager123!", Role.VADITAJS),
            ("Noliktavas lietotājs", "viewer@waretrack.lv", "Viewer123!", Role.LIETOTAJS),
        ]
        if existing_user:
            for name, email, password, role in demo_accounts:
                if not db.scalar(select(User.id).where(User.email == email)):
                    db.add(User(name=name, email=email, password_hash=hash_password(password), role=role))
            db.flush()
            actor = db.scalar(select(User).where(User.role == "ADMIN")) or existing_user
            added = add_realistic_catalog(db, actor)
            db.commit()
            print(f"Datubāze jau pastāv; pievienotas {added} jaunas demo preces.")
            return
        admin = User(name=demo_accounts[0][0], email=demo_accounts[0][1],
                 password_hash=hash_password(demo_accounts[0][2]), role=Role.ADMIN)
        user = User(name=demo_accounts[1][0], email=demo_accounts[1][1],
                password_hash=hash_password(demo_accounts[1][2]), role=Role.VADITAJS)
        readonly = User(name=demo_accounts[2][0], email=demo_accounts[2][1],
                password_hash=hash_password(demo_accounts[2][2]), role=Role.LIETOTAJS)
        categories = [
            Category(name="Elektropreces", description="Elektronika un biroja tehnika", icon="Laptop", color="blue"),
            Category(name="Iepakojums", description="Iepakošanas un nosūtīšanas materiāli", icon="Package", color="amber"),
            Category(name="Darba drošība", description="Individuālie aizsardzības līdzekļi", icon="Shield", color="green"),
            Category(name="Instrumenti", description="Noliktavas un darbnīcas instrumenti", icon="Wrench", color="purple"),
        ]
        suppliers = [
            Supplier(name="Rīgas Loģistika SIA", contact_person="Laura Ozola", email="pasutijumi@rigaslogistika.lv",
                     phone="+371 67123456", address="Dzelzavas iela 12, Rīga, LV-1084", category="Iepakojums", payment_terms="net30"),
            Supplier(name="Baltijas Tehnika SIA", contact_person="Mārtiņš Bērziņš", email="info@baltijastehnika.lv",
                     phone="+371 63001234", address="Aviācijas iela 8, Jelgava, LV-3004", category="Elektropreces", payment_terms="net30"),
            Supplier(name="Kurzemes Darba Apģērbs SIA", contact_person="Ilze Liepa", email="klienti@kda.lv",
                     phone="+371 63456789", address="Ganību iela 99, Liepāja, LV-3401", category="Darba drošība", payment_terms="net60"),
        ]
        locations = [
            Location(code="RIG-A01", name="Rīga — A zona, 1. plaukts", capacity=500),
            Location(code="RIG-B01", name="Rīga — B zona, 1. plaukts", capacity=800),
            Location(code="RIG-C01", name="Rīga — C zona, 1. plaukts", capacity=600),
            Location(code="JEL-A01", name="Jelgava — A zona", capacity=700),
        ]
        db.add_all([admin, user, readonly, *categories, *suppliers, *locations]); db.flush()
        items = [
            Item(name="Svītrkodu skeneris Zebra DS2208", sku="ZEB-DS2208", category_id=categories[0].id,
                 supplier_id=suppliers[1].id, min_stock=8, price=119.90),
            Item(name="Kartona kaste 400×300×300 mm", sku="KST-403030", category_id=categories[1].id,
                 supplier_id=suppliers[0].id, min_stock=100, price=1.15),
            Item(name="Atstarojošā drošības veste", sku="DRV-VESTE-L", category_id=categories[2].id,
                 supplier_id=suppliers[2].id, min_stock=15, price=6.75),
            Item(name="Līmlente 48 mm × 66 m", sku="LIM-4866", category_id=categories[1].id,
                 supplier_id=suppliers[0].id, min_stock=40, price=1.89),
            Item(name="Akumulatora skrūvgriezis", sku="INS-SKR-18V", category_id=categories[3].id,
                 supplier_id=suppliers[1].id, min_stock=5, price=84.50),
        ]
        db.add_all(items); db.flush()
        db.add_all([
            InventoryBalance(item_id=items[0].id, location_id=locations[0].id, quantity=24),
            InventoryBalance(item_id=items[1].id, location_id=locations[1].id, quantity=420),
            InventoryBalance(item_id=items[2].id, location_id=locations[2].id, quantity=7),
            InventoryBalance(item_id=items[3].id, location_id=locations[1].id, quantity=12),
            InventoryBalance(item_id=items[4].id, location_id=locations[0].id, quantity=16),
        ])
        db.flush()
        transfer = Transfer(code="PRV-00001", item_id=items[0].id, source_location_id=locations[0].id,
                            destination_location_id=locations[3].id, quantity=3, status="pending", priority="normal",
                            creator_id=user.id, notes="Jelgavas nodaļas papildināšanai")
        db.add(transfer)
        db.add(ActivityLog(user_id=admin.id, action="seed", entity_type="system", entity_id=None,
                           message="Izveidoti WareTrack demonstrācijas dati"))
        db.commit()
        print("WareTrack demonstrācijas datubāze izveidota.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()


from sqlalchemy import select

from app.auth.security import hash_password
from app.database import Base, SessionLocal, engine
from app.models import ActivityLog, Category, Item, Location, Supplier, Transfer, User


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.scalar(select(User).limit(1)):
            print("Datub?üz?ō jau ir dati; s?ükotn?ōj?ü aizpild?½?Īana izlaista.")
            return
        admin = User(name="WareTrack administrators", email="admin@waretrack.lv",
                     password_hash=hash_password("Admin123!"), role="ADMIN")
        user = User(name="Noliktavas lietot?üjs", email="user@waretrack.lv",
                    password_hash=hash_password("User123!"), role="USER")
        categories = [
            Category(name="Elektropreces", description="Elektronika un biroja tehnika", icon="Laptop", color="blue"),
            Category(name="Iepakojums", description="Iepako?Īanas un nos?½t?½?Īanas materi?üli", icon="Package", color="amber"),
            Category(name="Darba dro?Ī?½ba", description="Individu?ülie aizsardz?½bas l?½dzek??i", icon="Shield", color="green"),
            Category(name="Instrumenti", description="Noliktavas un darbn?½cas instrumenti", icon="Wrench", color="purple"),
        ]
        suppliers = [
            Supplier(name="R?½gas Lo?Żistika SIA", contact_person="Laura Ozola", email="pasutijumi@rigaslogistika.lv",
                     phone="+371 67123456", address="Dzelzavas iela 12, R?½ga, LV-1084", category="Iepakojums", payment_terms="net30"),
            Supplier(name="Baltijas Tehnika SIA", contact_person="M?ürti?å?Ī B?ōrzi?å?Ī", email="info@baltijastehnika.lv",
                     phone="+371 63001234", address="Avi?ücijas iela 8, Jelgava, LV-3004", category="Elektropreces", payment_terms="net30"),
            Supplier(name="Kurzemes Darba Ap?Ż?ōrbs SIA", contact_person="Ilze Liepa", email="klienti@kda.lv",
                     phone="+371 63456789", address="Gan?½bu iela 99, Liep?üja, LV-3401", category="Darba dro?Ī?½ba", payment_terms="net60"),
        ]
        locations = [
            Location(code="RIG-A01", name="R?½ga ŌĆö A zona, 1. plaukts", capacity=500),
            Location(code="RIG-B01", name="R?½ga ŌĆö B zona, 1. plaukts", capacity=800),
            Location(code="RIG-C01", name="R?½ga ŌĆö C zona, 1. plaukts", capacity=600),
            Location(code="JEL-A01", name="Jelgava ŌĆö A zona", capacity=700),
        ]
        db.add_all([admin, user, *categories, *suppliers, *locations]); db.flush()
        items = [
            Item(name="Sv?½trkodu skeneris Zebra DS2208", sku="ZEB-DS2208", category_id=categories[0].id,
                 supplier_id=suppliers[1].id, location_id=locations[0].id, stock=24, min_stock=8, price=119.90),
            Item(name="Kartona kaste 400?Ś300?Ś300 mm", sku="KST-403030", category_id=categories[1].id,
                 supplier_id=suppliers[0].id, location_id=locations[1].id, stock=420, min_stock=100, price=1.15),
            Item(name="Atstarojo?Ī?ü dro?Ī?½bas veste", sku="DRV-VESTE-L", category_id=categories[2].id,
                 supplier_id=suppliers[2].id, location_id=locations[2].id, stock=7, min_stock=15, price=6.75),
            Item(name="L?½mlente 48 mm ?Ś 66 m", sku="LIM-4866", category_id=categories[1].id,
                 supplier_id=suppliers[0].id, location_id=locations[1].id, stock=12, min_stock=40, price=1.89),
            Item(name="Akumulatora skr?½vgriezis", sku="INS-SKR-18V", category_id=categories[3].id,
                 supplier_id=suppliers[1].id, location_id=locations[0].id, stock=16, min_stock=5, price=84.50),
        ]
        db.add_all(items); db.flush()
        transfer = Transfer(code="PRV-00001", item_id=items[0].id, source_location_id=locations[0].id,
                            destination_location_id=locations[3].id, quantity=3, status="pending", priority="normal",
                            creator_id=user.id, notes="Jelgavas noda??as papildin?ü?Īanai")
        db.add(transfer)
        db.add(ActivityLog(user_id=admin.id, action="seed", entity_type="system", entity_id=None,
                           message="Izveidoti WareTrack demonstr?ücijas dati"))
        db.commit()
        print("WareTrack demonstr?ücijas datub?üze izveidota.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()


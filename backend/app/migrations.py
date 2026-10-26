"""Small, non-destructive schema migration helpers for the SQLite deployment.

The original release stored one location and one stock value on ``items``.  The
new balance table is the source of truth, but the old columns are intentionally
left in place so an existing database can be upgraded without a destructive
table rebuild.
"""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def migrate_user_roles(engine: Engine) -> None:
    if "users" not in inspect(engine).get_table_names():
        return

    with engine.begin() as connection:
        connection.execute(text("UPDATE users SET role = 'VADITAJS' WHERE role = 'USER'"))
        connection.execute(
            text("UPDATE users SET role = 'LIETOTAJS' WHERE role NOT IN ('LIETOTAJS', 'VADITAJS', 'ADMIN')")
        )
        if engine.dialect.name == "sqlite":
            connection.exec_driver_sql(
                """CREATE TRIGGER IF NOT EXISTS validate_user_role_insert
                BEFORE INSERT ON users
                WHEN NEW.role NOT IN ('LIETOTAJS', 'VADITAJS', 'ADMIN')
                BEGIN SELECT RAISE(ABORT, 'invalid user role'); END"""
            )
            connection.exec_driver_sql(
                """CREATE TRIGGER IF NOT EXISTS validate_user_role_update
                BEFORE UPDATE OF role ON users
                WHEN NEW.role NOT IN ('LIETOTAJS', 'VADITAJS', 'ADMIN')
                BEGIN SELECT RAISE(ABORT, 'invalid user role'); END"""
            )


def migrate_legacy_inventory(engine: Engine) -> None:
    inspector = inspect(engine)
    if "items" not in inspector.get_table_names() or "inventory_balances" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("items")}
    if not {"location_id", "stock"}.issubset(columns):
        return

    with engine.begin() as connection:
        rows = connection.execute(
            text("SELECT id, location_id, stock FROM items WHERE location_id IS NOT NULL")
        ).mappings().all()
        for row in rows:
            quantity = int(row["stock"] or 0)
            if quantity < 0:
                raise RuntimeError(f"Cannot migrate negative stock for item {row['id']}")
            exists = connection.execute(
                text(
                    "SELECT 1 FROM inventory_balances "
                    "WHERE item_id = :item_id AND location_id = :location_id"
                ),
                {"item_id": row["id"], "location_id": row["location_id"]},
            ).first()
            if not exists:
                connection.execute(
                    text(
                        "INSERT INTO inventory_balances "
                        "(item_id, location_id, quantity) "
                        "VALUES (:item_id, :location_id, :quantity)"
                    ),
                    {
                        "item_id": row["id"],
                        "location_id": row["location_id"],
                        "quantity": quantity,
                    },
                )

        # SQLite cannot drop or change NOT NULL legacy columns in place.  Once
        # balances are copied, rebuild only the affected table so new inserts
        # cannot be forced to maintain a second stock source of truth.
        if engine.dialect.name == "sqlite":
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.exec_driver_sql("PRAGMA legacy_alter_table=ON")
            connection.exec_driver_sql("ALTER TABLE items RENAME TO items_legacy")
            connection.exec_driver_sql(
                """CREATE TABLE items (
                    id INTEGER NOT NULL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    sku VARCHAR(30) NOT NULL,
                    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
                    supplier_id INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
                    min_stock INTEGER NOT NULL DEFAULT 0,
                    price FLOAT NOT NULL DEFAULT 0,
                    description TEXT NOT NULL DEFAULT '',
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )"""
            )
            connection.exec_driver_sql(
                """INSERT INTO items
                    (id, name, sku, category_id, supplier_id, min_stock, price, description, created_at, updated_at)
                    SELECT id, name, sku, category_id, supplier_id, min_stock, price, description, created_at, updated_at
                    FROM items_legacy"""
            )
            connection.exec_driver_sql("DROP TABLE items_legacy")
            connection.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_items_name ON items(name)")
            connection.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS ix_items_sku ON items(sku)")
            connection.exec_driver_sql("PRAGMA legacy_alter_table=OFF")
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")


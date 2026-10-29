# Company-scoped warehouse API

Inventory and master data now require a company path and authenticated company access:

- `/api/companies/{company_id}/items`
- `/api/companies/{company_id}/categories`
- `/api/companies/{company_id}/suppliers`
- `/api/companies/{company_id}/locations`

Each resource supports list, detail, create, update and delete. Item reads and writes require company read/edit permission. Master-data writes require the company manager permission; authenticated company members may read master data needed to edit items. Global ADMIN retains system access.

The previous unscoped items, categories, suppliers, locations, transfers, dashboard, reports and activity routes return HTTP 410. The current frontend still calls those paths and is intentionally incompatible until company selection and company-aware transfer/report routes are implemented. It cannot expose or modify company-owned warehouse data through the legacy API.

Revision `0004_company_scoped_uniqueness` preserves legacy rows and nullable owners while replacing global uniqueness with partial per-company uniqueness for category name, supplier name/email, location code and item SKU. Migration remains an explicit Alembic operation; application startup never applies it automatically.

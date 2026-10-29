# Company-scoped transfers and inventory balances

Revision `0005_inventory_balances` adds `inventory_balances`, keyed by company, item and location. `quantity` is the physical stock at that location and `reserved` is the part held by pending or in-transit transfers. The database enforces non-negative values and `reserved <= quantity`.

Creating a transfer atomically reserves source availability. Cancellation or deletion of a pending transfer releases it. Completion atomically subtracts quantity and reservation from the source and adds quantity to the destination. `Item.stock` remains the company-wide total, so movement between locations does not change it. Repeating completion is rejected before any balance update.

The migration deliberately creates no balance rows. Existing `Item.stock` and IDs remain unchanged because deciding how historical stock is distributed among locations is a business-data decision. A legacy item without an explicit source balance cannot be transferred and returns HTTP 409. Before enabling transfers for it, an approved conversion must create balance rows whose quantities sum exactly to `Item.stock`, with zero reservations, and whose company/item/location ownership matches.

New items created through the company-scoped inventory API receive one initial balance at their selected location. Direct stock or primary-location edits are rejected after a ledger exists; a future explicit inventory-adjustment workflow is required for such changes.

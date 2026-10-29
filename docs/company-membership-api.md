# Company registration and membership API

Public registration requires `companyId`. It creates an active global `USER` account and a
`PENDING` join request in one transaction. It does not create a membership. The account can
authenticate immediately, but company warehouse routes remain unavailable until a manager
approves the request.

`GET /api/companies/public` lists active companies without authentication. Authenticated users
can use `GET /api/companies/mine` and `GET /api/companies/my-requests`. A regular user sees only
active companies backed by an active approved membership. A global `ADMIN` sees every active
company in `/mine` with the synthetic local role `ADMIN`, because global administration grants
system access without creating company memberships.

Company `VADITAJS` and global `ADMIN` users review requests and manage memberships under
`/api/companies/{company_id}`. Approval always grants `LIETOTAJS`; promotion to `VADITAJS` is a
separate explicit membership update. Revocation preserves membership history and removes access
on the next request. Self-demotion, self-revocation, and removal of the last active manager are
blocked.

Global company administration is under `/api/admin`: companies can be listed, created with an
initial manager, renamed, activated, or safely deactivated. Deactivation is rejected while the
company has pending or in-transit transfers or pending join requests. Global administrators can
also list join requests across companies and use the company-specific review endpoints.

No migration is required for these endpoints; they use the `companies`, `company_memberships`,
and `company_join_requests` tables introduced by revision `0002_company_models`.

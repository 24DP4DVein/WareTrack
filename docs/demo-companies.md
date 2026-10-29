# Multi-company demonstrācijas datubāze

Demo ģenerators veido atsevišķu SQLite failu ar trim neatkarīgiem uzņēmumiem:

- `SIA TechStore` (`techstore`) — portatīvie datori, monitori, tastatūras un aksesuāri;
- `SIA AutoParts` (`autoparts`) — eļļas filtri, bremžu diski, gaisa filtri un siksnas;
- `SIA BuildMaster` (`buildmaster`) — cements, krāsas, skrūves un instrumenti.

Katram uzņēmumam ir savas kategorijas, piegādātājs, divas noliktavas, četras
preces, atlikumi, pabeigts pārvietojums, aktivitātes, viens `VADITAJS` un viens
`LIETOTAJS`. Ir arī viens globāls `ADMIN`. Dati netiek koplietoti starp uzņēmumiem.

## Droša izveide

Komandas jāizpilda no `backend` mapes. Failam jābūt jaunam vai agrāk ar šo pašu
ģeneratoru izveidotam demo failam. Parole netiek glabāta repozitorijā vai izdrukāta.

```powershell
$env:WARETRACK_DEMO_MODE = '1'
$env:WARETRACK_DEMO_PASSWORD = '<lokāla-stipra-parole-ar-Lielo-burtu-un-2026>'
python -m app.seed_demo_companies --database "$env:TEMP/waretrack-demo.db"
```

Administratora e-pastu var iestatīt ar `WARETRACK_DEMO_ADMIN_EMAIL`. Uzņēmumu
lietotāju e-pastus var pārrakstīt, piemēram, ar
`WARETRACK_DEMO_TECHSTORE_MANAGER_EMAIL` un
`WARETRACK_DEMO_TECHSTORE_USER_EMAIL` (analogi `AUTOPARTS` un `BUILDMASTER`).
Visiem kontiem lieto tikai izpildes vidē nodoto `WARETRACK_DEMO_PASSWORD`.

Ģenerators atsakās strādāt bez explicit demo režīma, ar parasto
`backend/waretrack.db`, production/staging nosaukumu, ne-SQLite `DATABASE_URL`,
failu, kas sakrīt ar parasto `DATABASE_URL`, vai nezināmu ne-tukšu datubāzi.
Atkārtota palaišana ir idempotenta; mainīti atlikumi vai paroles netiek pārrakstīti.

Pēc ģenerēšanas serverim jānorāda tieši demo fails un atsevišķa lokāla JWT
atslēga. Demo failu nedrīkst izmantot production vai kā production backup.
Atiestatīšanai aptur serveri, izdzēs tikai paša ģeneratora izveidoto demo failu
un izveido jaunu. Ģenerators pats nedzēš un neatiestata esošu datubāzi.

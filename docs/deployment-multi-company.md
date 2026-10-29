# Multi-company izvietošanas kontrolsaraksts

## Pirms migrācijas

1. Apturēt rakstīšanu un izveidot pārbaudītu, autonomu SQLite backup kopiju.
2. Pārbaudīt `PRAGMA integrity_check`, `PRAGMA foreign_key_check` un pašreizējo
   Alembic revīziju uz kopijas.
3. Ja datubāze ir pirms `0005_inventory_balances`, vispirms atjaunināt
   vienreizlietojamu kopiju līdz šai revīzijai.
4. Sagatavot un cilvēkam apstiprināt pilnu īpašnieku reģistru saskaņā ar
   `company-ownership-backfill.md`. Legacy ierakstu nedrīkst piešķirt pēc minējuma.
5. Uz migrācijas kopijas izpildīt ownership dry-run, tad `--apply`. Apply vienā
   transakcijā piešķir apstiprinātos īpašniekus un izveido sākotnējos location
   atlikumus no jau esošajiem `item.location_id` un `item.stock`.
6. Salīdzināt uzņēmumu, lietotāju, dalību, preču, atlikumu, pārvietojumu un
   aktivitāšu skaitu ar pirmsmigrācijas pārskatu.

## Migrācija un validācija

1. Ar skaidri norādītu kopijas `DATABASE_URL` izpildīt `alembic upgrade head`.
2. `0006_company_integrity` apstājas pirms DDL, ja ir NULL īpašnieki,
   starpuzņēmumu saites, negatīvi daudzumi vai `items.stock` nesakrīt ar ledger.
3. Pārbaudīt Alembic `current`, `check`, SQLite integritāti un ārējās atslēgas.
4. Palaist backend testus un frontend typecheck, lint un production build.
5. Veikt smoke test: login, uzņēmuma izvēle, preču CRUD, pārvietojums,
   dashboard/report/activity, pieprasījuma apstiprināšana un ADMIN uzņēmumu skats.
6. Tikai pēc kopijas pārbaudes ieplānot production apkopes logu un atkārtot
   identisko, iepriekš pārbaudīto procedūru ar jaunu backup.

Lietotnes startup neveic migration, stamp vai seed. Pirms servera palaišanas
datubāzei jābūt precīzi `0006_company_integrity`; nezināma, nepilna vai mainīta
shēma tiek noraidīta.

## Atcelšana

Downgrade ir aizliegts. Kļūmes gadījumā apturēt lietotni, saglabāt kļūdaino failu
analīzei un atjaunot pārbaudīto backup citā jaunā ceļā. Pārbaudīt atjaunoto failu
pirms `DATABASE_URL` pārslēgšanas. Pēc backup brīža radušos rakstus atjaunot tikai
ar atsevišķi apstiprinātu datu procedūru.

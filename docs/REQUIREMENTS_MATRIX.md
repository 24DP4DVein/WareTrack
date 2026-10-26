# WareTrack prasību matrica

Šī matrica atdala dokumentētas prasības no faktiski pārbaudītā koda stāvokļa.
Galvenie avoti ir `Doc/WareTrack_projekta_apraksts (2).pdf` (projekta apraksts),
`Doc/WareTrack_sist _old_version.pdf` (prasības, lomas un ER apraksts) un
`Doc/waretrack_er.drawio.png` (funkcionālais sadalījums).

| Avots / sadaļa | Prasība | Modulis | Sākotnējais stāvoklis | Ieviestā pārbaude |
|---|---|---|---|---|
| Projekta apraksts, 2.2 | Klienta-servera trīs slāņu arhitektūra | `src/`, `backend/app/`, SQLite | Bija ieviesta ar Next.js/FastAPI | Frontend build, backend tests, README |
| Projekta apraksts, 2.2; tehnoloģiju tabula, 3. nodaļa | Tehnoloģiju avoti ir pretrunīgi: Next.js/React/FastAPI/Python pret Vue/Vuetify/Laravel/PHP | Viss projekts | README sekoja Next/FastAPI | Konflikts saglabāts kā neatrisināts dokumentācijas jautājums; netika veikta nepārbaudīta migrācija |
| Vecā versija, 2.4–2.5 | Lietotāji, darbību vēsture, pārvietojumi, piegādātāji, preces, kategorijas, vietas | `backend/app/models/` | Viena `location_id` un globāls `stock` uz preces | `InventoryBalance` un `StockMovement`, saglabājot vecās datubāzes datus ar migrāciju |
| Lietojumgadījumu/ER apraksts | Autentifikācija un lomu kontrole | `backend/app/auth/`, routers | Daļa GET maršrutu bija publiski | Aizsargāti lasīšanas maršruti; operatīvās mutācijas pieejamas `VADITAJS` un `ADMIN`, lietotāju administrēšana tikai `ADMIN` |
| WareTrack piekļuves modelis | Tieši trīs lomas: `LIETOTAJS` (lasīšana), `VADITAJS` (operatīvās darbības), `ADMIN` (administrēšana); noklusējums ir `LIETOTAJS` | `backend/app/models/`, `backend/app/auth/`, `src/types/` | Bija `USER` un `ADMIN`; publiska reģistrācija izveidoja `USER` | `USER` migrē uz `VADITAJS`; mutācijas pārbauda lomu servera pusē; reģistrācija vienmēr piešķir `LIETOTAJS` |
| Pārvietojumu workflow | Pozitīvs daudzums, atšķirīgs avots/mērķis, pietiekams krājums un ietilpība | `backend/app/routers/transfers.py` | Pabeigšana mainīja tikai atrašanās vietu īpašā pilna krājuma gadījumā | Atomāra daļēja pārvietošana, rezervāciju pārbaude, statusu mašīna, auditēšana |
| Funkcionālais sadalījums, statistika | Dashboard un atskaites no faktiskajiem datiem | `backend/app/routers/dashboard.py` | Rādītāji balstījās uz `Item.stock` | Rādītāji tiek summēti no `inventory_balances` |
| README / projekta apraksts | Atkārtojama palaišana un seed | `README.md`, `backend/app/seed.py` | Nepilnīgs env/setup apraksts, bojāts Unicode | Pievienoti env piemēri, migrācijas/seed komandas un demo brīdinājums |
| ER/diagrammas | Vizuālajam modelim jāatbilst īstenībai | `docs/`, `Doc/` | Diagramma neattēloja vairākas bilances | Šajā izpildē saglabāta oriģinālā diagramma; `InventoryBalance` un konfliktu ietekme dokumentēta README |

## Neatrisināti dokumentācijas jautājumi

1. Tehnoloģiju tabula prasa Vue/Vuetify/Laravel/PHP, bet arhitektūras sadaļa un esošā
   ieviešana apraksta Next.js/React/FastAPI/Python. Šis ir materiāls framework migrācijai,
   kas jāapstiprina projekta īpašniekam pirms tā uzsākšanas.
2. Vecajā ER aprakstā pārvietojumam nav atsevišķi avota un galamērķa lauki, bet lietotne
   un darba plūsma tos izmanto. Pašreizējais API saglabā abus laukus un bilances pa vietām.
3. PDF/Excel eksports ir aprakstīts kā paredzēta funkcija, bet esošajā kodā eksporta
   endpointa nav; UI neuzrāda neīstenotu eksporta pogu.

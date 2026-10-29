# WareTrack

WareTrack ir noliktavas pārvaldības sistēma preču, krājumu un pārvietojumu uzskaitei.
Frontend izmanto Next.js, React, TypeScript un Tailwind CSS. Backend izmanto Python,
FastAPI, SQLAlchemy un SQLite. Datu apmaiņa notiek caur autentificētu REST API.

## Funkcijas

- preču CRUD, meklēšana, filtrēšana un krājuma statusi;
- kategoriju, piegādātāju un noliktavas vietu pārvaldība;
- krājuma bilances vienai precei vairākās vietās;
- pārvietojumu izveide, nosūtīšana, pabeigšana un atcelšana;
- atomāra daļēja pārvietošana ar avota krājuma un galamērķa ietilpības pārbaudi;
- lietotāju autentifikācija, LIETOTAJS/VADITAJS/ADMIN lomas un darbību vēsture;
- dashboard un atskaites no faktiskajām datubāzes bilancēm.

## Priekšnoteikumi

- Python 3.11+;
- Node.js 18+ un npm.

## Palaišana no tīras darba vides

1. Backend:

   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

   Nokopējiet `.env.example` vērtības savā vidē. Izstrādei `JWT_SECRET_KEY` ir jānorāda
   kā nejauša virkne ar vismaz 32 rakstzīmēm. Ja vēlaties izveidot tikai lokālai
   izstrādei nepieciešamo administratora kontu, iestatiet:

   ```powershell
   $env:WARETRACK_BOOTSTRAP_ADMIN = "true"
   $env:WARETRACK_ADMIN_EMAIL = "admin@waretrack.local"
   $env:WARETRACK_ADMIN_PASSWORD = "StrongPassword123!"
   ```

   `WARETRACK_BOOTSTRAP_ADMIN` ir obligāti jāieslēdz manuāli; produkcijā vai jebkurā
   pasteidzētā vidē šis iestatījums paliek izslēgts, lai nepieļautu automātisku
   administratora konta izveidi.

   ```powershell
   python -m app.seed
   python -m uvicorn app.main:app --reload --port 8000
   ```

   `app.main` izveido trūkstošās tabulas, pārceļ esošos `USER` kontus uz `VADITAJS`
   un vienreizēji pārnes vecā modeļa `items.location_id`/`items.stock` vērtības uz
   `inventory_balances`. Datubāze netiek
   dzēsta vai atiestatīta. Seed komanda ir droša atkārtotai palaišanai: ja dati jau
   pastāv, tā saglabā esošos ierakstus un pievieno trūkstošos demo kontus un katalogu.

2. Frontend jaunā terminālī:

   ```powershell
   npm install
   npm run dev
   ```

   Atveriet <http://localhost:3000>.

## Demo konti

Seed izveido tikai izstrādes demonstrācijas kontus:

- `ADMIN`: `admin@waretrack.lv` / `Admin123!`
- `VADITAJS`: `manager@waretrack.lv` / `Manager123!`
- `LIETOTAJS`: `viewer@waretrack.lv` / `Viewer123!`

Seed komanda darbojas tikai tad, ja `WARETRACK_ENV` ir `development` vai `test`.
Demo paroles nedrīkst izmantot produkcijā, un publiskā reģistrācija vienmēr piešķir
`LIETOTAJS` lomu.

## Pārbaudes

```powershell
cd backend
python -m pytest -q

cd ..
npx tsc --noEmit
npm run build
```

`npm run lint` ir konfigurēts ar Next.js ESLint noteikumiem, taču Next.js 14 var
pieprasīt interaktīvu konfigurācijas izvēli, ja ESLint konfigurācija nav atpazīta.

## Datu modelis un drošība

`InventoryBalance(product, location, quantity)` ir vienīgais aktuālā daudzuma avots.
`StockMovement` un `ActivityLog` saglabā pārvietošanas un sistēmas vēsturi. Pabeigta
pārvietošana vienā transakcijā samazina avota bilanci, palielina mērķa bilanci,
izveido kustības ierakstu un nomaina statusu. SQLite izmanto rakstīšanas transakcijas
serializāciju; citām datubāzēm tiek izmantota `FOR UPDATE` semantika, ja tā ir pieejama.

Visiem inventāra, kategoriju, piegādātāju, vietu, dashboard un atskaišu pieprasījumiem
vajadzīgs Bearer JWT. `LIETOTAJS` var tikai lasīt; `VADITAJS` veic atļautās ikdienas
preču, kategoriju, piegādātāju, vietu un pārvietojumu darbības; `ADMIN` papildus
pārvalda lietotājus un lomas. Serveris validē attiecības, daudzumus, statusu pārejas,
ietilpību un lomu atļaujas.

## Dokumentācija un zināmie ierobežojumi

Detalizēta prasību matrica ir [docs/REQUIREMENTS_MATRIX.md](docs/REQUIREMENTS_MATRIX.md).
Pievienotajos PDF dokumentos ir tehnoloģiju konflikts: vienā sadaļā prasīts
Vue/Vuetify/Laravel/PHP, bet citā dokumentēta Next.js/React/FastAPI/Python arhitektūra.
Šis konflikts nav atrisināms ar drošu lokālu refaktoringu un ir jāapstiprina projekta
īpašniekam pirms framework migrācijas. PDF/Excel eksports ir dokumentēts kā iecere,
bet endpointa pašlaik nav.

# Миграции БД WareTrack

## Область и изменение запуска

Alembic управляет схемой SQLite. Baseline `0001_baseline` фиксирует прежние users, categories, suppliers, locations, items, transfers и activity_logs. Ревизии `0002`–`0005` добавляют компании, временно nullable-владение, company-scoped уникальность и ledger остатков. Финальная `0006_company_integrity` требует заполненного владения, делает шесть `company_id` обязательными и добавляет составные FK, которые блокируют межфирменные связи. Она также закрепляет неотрицательные остатки и согласованность ledger. Старые записи и ID не переназначаются автоматически. SQL выпущенных ревизий — неизменяемые снимки.

`backend/migrations/env.py` импортирует все модели до установки `target_metadata = Base.metadata`; включены `render_as_batch`, сравнение типов и server defaults. `backend/alembic.ini` не содержит URL/паролей. Для CLI нужен явно заданный `DATABASE_URL`; значение не сохраняется и не проходит интерполяцию ConfigParser (символ `%` допустим). Путь к alembic.ini можно указывать абсолютным, поэтому команды работают и вне backend. Относительный путь SQLite в DATABASE_URL по-прежнему считается от текущего рабочего каталога; для безопасности используйте абсолютный.

FastAPI lifespan теперь **только проверяет** ревизию и схему. Он не создаёт таблицы, не вызывает upgrade/stamp, не дополняет существующую БД. В отличие от предыдущей инфраструктуры, пустую development-БД нужно явно подготовить Alembic перед Uvicorn. Отсутствующий обычный SQLite-файл при проверке startup не создаётся. Импорт приложения остаётся без подключения к БД.

Данные ревизии и автоматическая проверка поддерживают SQLite. Другой диалект отклоняется. Offline `--sql` отключён: безопасное принятие требует проверки живой схемы. SQLite batch mode настроен для будущих миграций; их операции по-прежнему требуют отдельного review и испытаний. `0001_baseline` и `0002_company_models` принимаются как промежуточные ревизии только для явного upgrade, а startup требует проверенный head `0003_company_ownership`. При добавлении следующей ревизии необходимо обновить политику проверки ревизий/схем в `app/migration_support.py`.

## Подготовка окружения

Команды ниже — инструкция оператору, не отчёт об изменении рабочей БД. Выполнять из `backend` с активированным Python-окружением; зависимости — `python -m pip install -r requirements.txt`. Перед операциями проверить ветку, путь к конфигурации и фактический DATABASE_URL без публикации секретов. Никогда не запускать тесты против production/staging. В CI/pytest DATABASE_URL заменяется на in-memory до импорта приложения.

Не использовать seed как замену миграции: старый `app.seed` не назначает ревизию Alembic. Startup такую БД не примет без проверенного adoption.

## Новая пустая development-БД

Пример PowerShell создаёт уникальный временный каталог, чтобы не затронуть существующий файл:

```powershell
$demoDirectory = Join-Path ([IO.Path]::GetTempPath()) ('waretrack-dev-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $demoDirectory | Out-Null
$demoDatabase = Join-Path $demoDirectory 'development.db'
$env:DATABASE_URL = 'sqlite:///' + $demoDatabase.Replace('\', '/')
python -m alembic -c alembic.ini upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Migration failed; do not start the application' }
python -m alembic -c alembic.ini current
python -m uvicorn app.main:app --port 8000
```

Новая БД получает десять предметных таблиц, шестнадцать явных индексов (включая частичный уникальный индекс PENDING-заявок и шесть company_id-индексов), SQLite autoindexes для PK/UNIQUE, таблицу alembic_version и ревизию `0003_company_ownership`. Компании, членства, заявки и другие предметные записи не создаются автоматически. Повторный `upgrade head` не изменяет данные. Регистрация через приложение после миграции сохраняет прежнее поведение USER.

## Принятие существующей БД

1. Остановить процессы записи. Определить фактический абсолютный путь БД, не полагаться на default. Зафиксировать версию кода и схему, контрольные количества и записи, включая IDs и password_hash (не публиковать значения хешей).
2. Снять согласованную резервную копию. Для SQLite использовать Backup API либо согласованную копию при полностью остановленных соединениях; нельзя копировать только основной файл активной WAL-БД. Проверить `integrity_check`/`foreign_key_check` и восстановление в отдельный файл.
3. Все первые прогоны делать на отдельной восстановленной копии. Ниже оператор подставляет путь **этой копии**, а не production. Применение на реальной БД — отдельная управляемая операция после проверки backup и окна обслуживания.

```powershell
$adoptionCopy = 'C:/ABSOLUTE/PATH/TO/VERIFIED-COPY.db'
if (-not (Test-Path -LiteralPath $adoptionCopy -PathType Leaf)) { throw 'Verified copy not found' }
$env:DATABASE_URL = 'sqlite:///' + $adoptionCopy.Replace('\', '/')
python -m alembic -c alembic.ini -x adopt_existing=true upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Adoption rejected; do not stamp or repair automatically' }
python -m alembic -c alembic.ini current
python -m alembic -c alembic.ini check
```

Обычный upgrade непустой unversioned-БД отказывается работать без явного adoption. Adoption сверяет полный SQLite DDL с frozen baseline: таблицы, порядок/типы/nullable/default колонок, PK/UNIQUE/CHECK, действия FK, индексы, collations; лишние таблицы, индексы, views и triggers также отклоняются. Дополнительно проверяется целостность БД и данных FK. Неизвестная, пустая или модифицированная таблица ревизий отклоняется.

Сравнение консервативное: игнорируются пробелы вне строковых литералов, но даже эквивалентные иначе записанные определения могут быть отклонены. Это повод для ручного анализа схемы, а не разрешение ослаблять проверку или удалять объекты. Baseline принятия соответствует фактическим текущим ORM-типам: например, price FLOAT и role VARCHAR(20), без новых CHECK и без server defaults для клиентских default SQLAlchemy.

Принятие legacy-БД выполняют сначала только до `0005_inventory_balances`: Alembic проверяет baseline, добавляет служебную таблицу ревизии и переходные структуры, сохраняя прежние company_id как NULL. Затем нужен отдельный утверждённый backfill из [company-ownership-backfill.md](company-ownership-backfill.md). Только после dry-run, apply и сверки данных разрешён `upgrade head`. Прямой переход legacy-БД на head блокируется при первом нерешённом владельце. Не выполнять `alembic stamp head`: stamp отключён.

## Проверка версии и upgrade одноразовой копии

После явной установки DATABASE_URL на проверенную временную БД:

```powershell
python -m alembic -c alembic.ini current
python -m alembic -c alembic.ini heads
python -m alembic -c alembic.ini history
python -m alembic -c alembic.ini check
python -m alembic -c alembic.ini upgrade head
```

`current` проверяет подключённую схему и показывает текущую ревизию; `heads/history` показывают цепочку файлов миграций. На unversioned непустой БД `current` также откажет без режима adoption; это не меняет её данные. `check` сравнивает ORM и мигрированную схему. Ни одна из этих команд не должна выполняться с непроверенным URL.

## Сбой и восстановление

Миграции используют явную SQLite-транзакцию `BEGIN IMMEDIATE`; preflight, DDL и изменение ревизии входят в одну транзакцию. Проверки включают искусственный сбой посередине DDL. Это не заменяет backup при аварии диска/процесса. Downgrade всех выпущенных ревизий намеренно запрещён, чтобы не удалить таблицы и данные.

При сбое остановить доступ/записи и сохранить неисправную БД для анализа. Не удалять и не перезаписывать её. Восстановить проверенную backup в **новый путь**, проверить её отдельно и переключить DATABASE_URL вместе с совместимой версией приложения. Нельзя запускать старое приложение поверх будущей схемы без проверки совместимости.

Пример копирования уже согласованной, автономной, проверенной backup (не активного WAL-файла):

```powershell
$verifiedBackup = 'C:/ABSOLUTE/PATH/TO/VERIFIED-BACKUP.db'
$restoreDirectory = Join-Path ([IO.Path]::GetTempPath()) ('waretrack-restore-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $restoreDirectory | Out-Null
$restoredDatabase = Join-Path $restoreDirectory 'restored.db'
if (-not (Test-Path -LiteralPath $verifiedBackup -PathType Leaf)) { throw 'Backup not found' }
Copy-Item -LiteralPath $verifiedBackup -Destination $restoredDatabase -ErrorAction Stop
if ((Get-FileHash -LiteralPath $verifiedBackup).Hash -ne (Get-FileHash -LiteralPath $restoredDatabase).Hash) { throw 'Backup copy mismatch' }
$env:DATABASE_URL = 'sqlite:///' + $restoredDatabase.Replace('\', '/')
python -c "import os, sqlite3; from sqlalchemy.engine import make_url; c=sqlite3.connect(make_url(os.environ['DATABASE_URL']).database); assert c.execute('PRAGMA integrity_check').fetchall()==[('ok',)]; assert c.execute('PRAGMA foreign_key_check').fetchall()==[]; c.close()"
if ($LASTEXITCODE -ne 0) { throw 'Restored database failed validation' }
```

Если backup уже versioned, выполнить `alembic current`, сверку предметных данных и smoke-test соответствующей версии приложения. Если backup до Alembic, использовать совместимую старую версию приложения либо отдельно пройти проверенный adoption восстановленной копии. Не ставить stamp ради запуска. Новые записи после времени backup не терять молча: до переключения согласовать их восстановление/повторный ввод.

## Тестирование и границы изменений

Из корня репозитория, в подготовленном Python-окружении:

```powershell
$env:DATABASE_URL = 'sqlite://'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
python -B -m pytest -p no:cacheprovider backend/tests -q
```

Каждая API-фикстура получает отдельный in-memory engine и готовит схему Alembic. Сценарии adoption используют только tmp_path и искусственные legacy-данные. Основной engine запрещён для тестовых подключений; проверки запуска работают в subprocess с явным временным URL. Отдельно проверяются несовместимые DDL, неверные FK-данные, неизвестная ревизия, отсутствие записи при отказе, повторный upgrade, запрет stamp/downgrade, rollback DDL и startup после миграции.

Будущий staging: `backend/requirements.txt` (только строка Alembic), `backend/alembic.ini`, `backend/migrations/`, новый `backend/app/migration_support.py`, изменения `backend/app/database.py`, `backend/tests/conftest.py`, `backend/tests/test_database_lifecycle.py`, новый `backend/tests/test_migrations.py`, этот документ. Прежние исправления кодировки/латышского текста и любые остальные изменения не включать. `main.py` уже вызывает проверку через lifespan и дополнительных правок не требует.

Рекомендуемое сообщение будущего коммита: `Add database migration infrastructure`. Коммит не должен содержать идентификаторы задач. Эта работа не включает staging, commit, push, изменение реальных БД или multi-tenancy.

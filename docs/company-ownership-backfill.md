# Реестр владения прежними данными

`0003_company_ownership` только добавляет nullable `company_id` в categories, suppliers, locations, items, transfers и activity_logs. Миграция не угадывает владельца и не обновляет предметные строки. Старые API пока не считаются tenant-aware и не должны использоваться для работы нескольких компаний.

Backfill выполняется отдельной командой `python -m app.ownership_backfill`. Она требует явно заданный `DATABASE_URL`, по умолчанию делает только dry-run и никогда не создаёт компании, членства или демоданные. Рабочую БД нельзя выбирать для первого прогона: восстановите проверенную backup в отдельный путь, остановите записи и проверьте реестр на этой копии.

## Формат утверждённого реестра

```json
{
  "approved_by": "Имя согласовавшего",
  "approved_at": "2026-10-29T12:00:00+02:00",
  "reason": "Основание распределения прежних данных",
  "assignments": [
    {"table": "categories", "id": 1, "company_id": 10},
    {"table": "locations", "id": 1, "company_id": 10},
    {"table": "items", "id": 1, "company_id": 10}
  ]
}
```

В реестре должна присутствовать каждая строка с `company_id IS NULL` из всех шести таблиц. ID компании должны уже существовать. Дубликаты, неизвестные таблицы/строки/компании, конфликт с ранее установленным владельцем и отсутствие timezone в `approved_at` отклоняются.

Перед записью инструмент под `BEGIN IMMEDIATE` проверяет полный реестр и связи: Item, его Category, Location и nullable Supplier должны принадлежать одной компании; Transfer, Item и оба Location также должны совпадать. Любая нерешённая или cross-company связь отменяет всю операцию. ActivityLog требует явного решения в реестре и не получает владельца из `user_id` или `entity_id`.

## Безопасный прогон на одноразовой копии

Из каталога `backend`:

```powershell
$copy = 'C:/ABSOLUTE/PATH/TO/VERIFIED-COPY.db'
$plan = 'C:/ABSOLUTE/PATH/TO/APPROVED-ownership.json'
if (-not (Test-Path -LiteralPath $copy -PathType Leaf)) { throw 'Database copy not found' }
if (-not (Test-Path -LiteralPath $plan -PathType Leaf)) { throw 'Ownership registry not found' }
$env:DATABASE_URL = 'sqlite:///' + $copy.Replace('\', '/')
python -m alembic -c alembic.ini current
python -m app.ownership_backfill $plan
```

Dry-run возвращает JSON с `"dry_run": true` и не обновляет строки. После независимой сверки количества записей, ID, значений, связей, backup и утверждённого реестра запись на той же проверяемой копии запускается отдельно:

```powershell
python -m app.ownership_backfill $plan --apply
```

Успешный apply обновляет только NULL `company_id`, повторный запуск того же реестра идемпотентен. Инструмент не вводит `NOT NULL` и составные FK: это отдельная contract-фаза после перевода всех путей чтения/записи на company context. При ошибке не использовать `stamp`, не удалять строки и не исправлять владельца автоматически; сохранить копию для анализа и исправить утверждённый реестр.

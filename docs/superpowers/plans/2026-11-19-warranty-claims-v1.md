# Warranty Claims App v1 Implementation Plan

> **For agentic workers:** Build this plan one task at a time and stop after each task for the owner's review. Follow "How we build" in `CLAUDE.md`, which overrides the continuous-execution rule in the superpowers execution skills. Review depth for each task is in "Build order and review depth" below. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build v1 of the warranty claims app. Techs file claims with photos from an iPhone. Reviewers edit them, chat with the tech, and export correctly named photos. Everything runs on the owner's laptop in test mode.

**Architecture:**
- **Frontend and API:** a React + Vite + TypeScript single-page app (shadcn/ui, light and dark themes) calls a FastAPI JSON API under `/api` on the same origin. In development, Vite proxies `/api` to the backend.
- **Database:** PostgreSQL stores users, sessions, claims, photos, chat messages and read state. Claims use real columns plus a jsonb `form_data` column.
- **Photos:** the browser uploads them straight to S3-compatible storage through pre-signed POSTs. On submit, the backend moves them under the claim.
- **OCR:** runs in the browser (Tesseract.js).
- **VIN decoding:** goes through the backend to NHTSA vPIC.
- **Reviewer email:** sent over SMTP to a local mail catcher.
- **Production shape (prepared, not deployed):** an nginx container serves the built frontend and reverse-proxies `/api/` to a separate backend container, which is never published on a host port. Task 17 builds both images and runs them locally under a Compose profile.

**Tech Stack:**
- **Backend:** Python 3.14 managed by `uv` (committed `uv.lock`), FastAPI, Uvicorn, SQLAlchemy 2, Pydantic 2, pydantic-settings, Alembic, psycopg 3, boto3, httpx, pytest, moto.
- **Frontend:** Node 22+, React, Vite, TypeScript, Tailwind CSS, shadcn/ui, React Router, TanStack Query, Tesseract.js, Vitest, React Testing Library.
- **Docker Compose:** Postgres 18, SeaweedFS (S3-compatible), Mailpit. The `app` profile adds the production `frontend` (nginx) and `backend` containers.

**Spec:** `docs/superpowers/specs/2026-11-19-warranty-claims-design.md`, approved 2026-11-19. It builds on `warranty_wireframe_v2.excalidraw`.

**Where to run:** the owner's personal laptop, which has Node and Docker. Never commit or copy the sample invoice PDF (`ASSURANT.*.pdf`): it holds real customer data.

## Global Constraints

**Platforms and versions**
- Python 3.14, Node ≥ 22, Postgres 18 via Docker Compose (design §4, runtime versions).
- The backend depends on `tzdata`, because Windows has no system time-zone database.
- Backend dependencies are managed with `uv`: ranges in `pyproject.toml`, exact versions in a committed `uv.lock`, Python pinned to `3.14` in `backend/.python-version`. Backend commands run through `uv run`. The laptop's default `python3` is 3.9, so never use a bare `python -m venv`.
- The frontend's `package-lock.json` is committed. Images install with `uv sync --frozen` and `npm ci`.

**Deployment readiness (design §17)**
- `APP_ENV` is `development` (default) or `production`. In production the backend refuses to start on unsafe settings (Task 1).
- Tests build the database from the Alembic migrations, never `create_all` (Task 2).
- Bucket setup (creation, `uploads/` expiry, CORS) lives in `python -m app.setup_bucket`, not in `mc` commands (Task 4).
- Outside development, only nginx is reachable. The backend container publishes no host port.

**API and test data**
- All API routes live under `/api`. The frontend only calls relative `/api/...` paths.
- No real customer data anywhere. Test data uses made-up names, `example.com` email addresses and the public sample VIN `1M8GDM9AXKP042788`.
- `.gitignore` excludes `*.pdf` and `.env`.
- Customer phone, address, city, state and ZIP never appear in emails or logs.

**Sessions and requests**
- Session cookie:
  - Named `warranty_session`, HttpOnly, `SameSite=Lax`, `Max-Age=31536000` (365 days).
  - Renewed once its expiry is more than a day short of a full 365 days.
  - `Secure` is set by `SESSION_COOKIE_SECURE`, which is false in v1 because the iPhone uses plain HTTP over Wi-Fi.
  - The database stores only a SHA-256 hash of the token.
- A POST, PATCH, PUT or DELETE whose `Origin` header isn't in `ALLOWED_ORIGINS` gets 403. Requests without an `Origin` header pass.

**Photos and storage**
- Photo types are `image/jpeg` or `image/png` only, at most 30 MB each.
- Photos upload exactly as the browser provides them: no resizing or re-encoding. With `accept="image/jpeg,image/png"` on the file input, iOS Safari hands over full-resolution JPEGs instead of HEIC.
- Storage keys:
  - Uploads land at `uploads/{user_id}/{uuid}.{ext}`.
  - On attach they move to `claims/{claim_id}/{uuid}.{ext}`.
  - The bucket expires `uploads/` after 7 days.
- The S3 client uses signature v4 and path-style addressing, needed for a local S3 store on an IP address.

**Phone access over Wi-Fi**
- Every address the phone uses comes from config, never a `localhost` literal: `APP_BASE_URL`, `S3_ENDPOINT_URL`, `ALLOWED_ORIGINS`.
- The frontend must work over plain HTTP: no `crypto.randomUUID`, no `navigator.clipboard`.

**Data rules**
- Timestamps are timezone-aware and set in Python with `datetime.now(UTC)`, never the server's `now()`. Unread logic compares IDs, not times.
- VIN rule: 17 characters from `[A-HJ-NPR-Z0-9]`, stored uppercase.
- Export filename: `{WARRANTY COMPANY}.{last 8 of VIN}.{CUSTOMER LAST NAME}.{photo description}.{MM}.{YY}.{ext}`.
  - MM and YY are the submission month and year in the claim's `submission_tz`.
  - Example: `ASSURANT.KP042788.SMITH.Wheel.RF.11.26.jpg`.
- Statuses are `submitted`, `approved` and `closed`. Roles are `tech` and `reviewer`. Photo kinds are `vin`, `mileage` and `damage`.

**UI**
- The UI is built from shadcn/ui components in `src/components/ui`.
- Colors come only from shadcn's theme CSS variables (no hard-coded colors), so light and dark both work.
- The theme follows the device setting unless the user picks Light or Dark. The choice is stored in `localStorage` under `warranty.theme`.
- The test-mode banner text is exactly `Test mode — don't enter real customer data`.

**Frontend tests**
- Mock API calls with `vi.mock("../api/client", …)`. Mock `src/ocr/tesseract.ts` and `src/photos/image.ts` in component tests.

## Review Focus

1. **Safari reloads mid-intake, even mid-upload:**
   - Uploaded photos, descriptions and fields come back.
   - A photo that was still uploading comes back as failed with "Pick again", never as uploaded.
   - Tests: Task 13, Task 14.
2. **The iPhone reaches the laptop by LAN IP:** pre-signed URLs and the emailed link use the configured addresses, not `localhost`. Tests: Task 4, Task 9.
3. **A forged or reused photo key at submit** (someone else's upload, a key never uploaded, a key already attached): 422, no claim is created, and no photo is moved. Test: Task 6.
4. **Excluded photos and repeated descriptions at export:**
   - Excluded photos are left out.
   - Names stay unique (`-2`).
   - An export where every photo is excluded is refused.
   - Tests: Task 5, Task 7.
5. **A tech in another time zone near month end:** MM/YY follows the tech's `submission_tz`, and an invalid zone is rejected at submit. Tests: Task 5, Task 6.

## Build order and review depth

Tasks are built in order and one at a time. After each task there's a review with the owner, at one of three depths:

- **Walk-through:** the code holds the app's architecture or business rules. Explain:
  - how a request or action flows through the new code;
  - why it's shaped that way, and what the alternatives were;
  - the few places that matter most;
  - what the tests prove.

  The owner reads the whole diff.
- **Summary:** setup, wiring or glue. Say what was added and where, point out anything non-obvious, and show the test results. The owner skims the diff.
- **In the browser:** a screen. Demo it first (on the iPhone for intake), then walk through its state and data flow rather than its markup. Large screens are reviewed one part at a time.

| Task | Depth | Focus |
|---|---|---|
| 1. Dev services and backend skeleton | Summary | How config works, including the `APP_ENV=production` checks; the test database fixture; the health check |
| 2. Database models and first migration | Walk-through | The data model: columns vs `form_data`; tests running on the migrations |
| 3. Anonymous sessions and the current user | Walk-through | Security: cookies, token hashing, the origin check, role guards |
| 4. Photo storage and upload URLs | Walk-through | The upload flow: pre-signed POST, `uploads/` → `claims/`; bucket setup |
| 5. Export filename rules | Walk-through | The naming rules Kim relies on |
| 6. Claim submission, listing and search | Walk-through | Who can see what; how photo keys are checked at submit |
| 7. Photos on submitted claims, reviewer edits and export | Walk-through | Edit permissions; how the zip is built |
| 8. Chat thread and unread markers | Walk-through | How unread is computed |
| 9. Reviewer email on new claims | Summary | What the email contains; why a failure never blocks submit |
| 10. VIN decode lookup | Summary | Calling vPIC and handling its failures |
| 11. Frontend skeleton, themes, role picker and profile | Summary | How the frontend calls the API and checks the session |
| 12. OCR and VIN helpers | Summary | How `extractVin` picks a candidate |
| 13. Intake draft and photo upload pipeline | Walk-through | State that survives a reload, mid-upload too |
| 14. Intake screens | In the browser | One phase at a time |
| 15. Claims list | In the browser | Unread markers and search |
| 16. Claim detail, and the end-to-end check | In the browser | One panel at a time: fields, photos, chat, export |
| 17. Production containers | Walk-through | `nginx.conf`, the backend entrypoint, and what's reachable from outside |

---

## File Structure

```
.gitignore  .env.example  docker-compose.yml  docker/postgres-init/01-test-db.sql  README.md
backend/
  pyproject.toml  uv.lock  .python-version  alembic.ini  alembic/env.py  alembic/versions/0001_initial.py
  Dockerfile  .dockerignore  docker-entrypoint.sh      (Task 17)
  app/
    config.py            Settings
    db.py                Base, session factory, get_db
    main.py              create_app(), get_settings, module-level app
    models.py            ORM models and enums
    auth.py              sessions, current-user dependencies, /api/session, /api/me, Origin check
    storage.py           PhotoStorage (S3), build_storage, get_storage
    setup_bucket.py      ensure_bucket and the `python -m app.setup_bucket` command
    uploads.py           POST /api/uploads
    claims/schemas.py    request/response models, US state codes, VIN rule
    claims/access.py     get_visible_claim
    claims/routes.py     create/list/get/patch claims, intake form options
    photos/labels.py     DamageLabel, the fixed list of damage photo descriptions
    photos/naming.py     export filename rules
    photos/attach.py     attach_photos (validate keys, move objects, create rows)
    photos/routes.py     list/add/patch photos, export zip
    conversations.py     chat thread and mark-read routes
    unread.py            unread_claim_ids
    notifications.py     reviewer email
    vin_decode.py        NHTSA vPIC lookup and route
  tests/conftest.py, tests/test_*.py
frontend/
  vite.config.ts  components.json  package-lock.json  src/main.tsx  src/App.tsx  src/index.css
  Dockerfile  .dockerignore  nginx.conf                (Task 17)
  src/components/ui/     shadcn components (generated)
  src/components/        NavBar.tsx TestModeBanner.tsx ThemeToggle.tsx PhotoSlot.tsx
  src/theme/             ThemeProvider.tsx
  src/api/               client.ts types.ts
  src/session/           useMe.ts RequireUser.tsx RolePickerPage.tsx ProfilePage.tsx
  src/lib/               utils.ts (shadcn) vin.ts usStates.ts
  src/ocr/               extract.ts tesseract.ts
  src/photos/            image.ts upload.ts
  src/intake/            draft.ts useIntakeDraft.ts validate.ts IntakePage.tsx CustomerVehicleStep.tsx PhotosStep.tsx
  src/review/            ClaimsListPage.tsx ClaimDetailPage.tsx ClaimFields.tsx PhotoGallery.tsx AddPhotos.tsx ChatThread.tsx
  src/test/              setup.ts render.tsx fixtures.ts
```

---

### Task 1: Dev services and backend skeleton

**Files:**
- Create: `.env.example`, `docker-compose.yml`, `docker/postgres-init/01-test-db.sql`, `README.md`.
- Already in the repo: `.gitignore` and `CLAUDE.md`. Check `.gitignore` matches Step 1 and leave `CLAUDE.md` as is.
- Create: `backend/pyproject.toml`, `backend/uv.lock` (generated), `backend/.python-version`, `backend/app/__init__.py`, `backend/app/config.py`, `backend/app/db.py`, `backend/app/main.py`.
- Test: `backend/tests/conftest.py`, `backend/tests/test_health.py`, `backend/tests/test_config.py`.

**Interfaces:**
- **Produces `class Settings(BaseSettings)`** in `app/config.py`. It reads `.env`. Fields and defaults:
  - `APP_ENV: Literal["development", "production"]="development"`
  - `DATABASE_URL="postgresql+psycopg://warranty:warranty@localhost:5432/warranty"`
  - `SESSION_COOKIE_SECURE=False`, `SESSION_TTL_DAYS=365`
  - `ALLOWED_ORIGINS: list[str]=["http://localhost:5173"]`, `APP_BASE_URL="http://localhost:5173"`
  - `S3_ENDPOINT_URL: str | None="http://localhost:9000"`, `S3_REGION="us-east-1"`, `S3_BUCKET="warranty-photos"`, `S3_ACCESS_KEY_ID="dev-access-key"`, `S3_SECRET_ACCESS_KEY="dev-secret-key"`, `MAX_UPLOAD_BYTES=30_000_000`
  - `SMTP_HOST="localhost"`, `SMTP_PORT=1025`, `SMTP_USERNAME: str | None=None`, `SMTP_PASSWORD: str | None=None`, `SMTP_STARTTLS=False`, `MAIL_FROM="warranty-app@localhost"`
  - `VPIC_BASE_URL="https://vpic.nhtsa.dot.gov/api"`
- **Production checks:** a `model_validator(mode="after")` on `Settings`. When `APP_ENV == "production"`, it collects every problem below and raises one `ValueError` naming each offending setting:
  - `SESSION_COOKIE_SECURE` is false.
  - `APP_BASE_URL` doesn't start with `https://`, or any `ALLOWED_ORIGINS` entry doesn't.
  - `S3_ACCESS_KEY_ID` is `dev-access-key` or `S3_SECRET_ACCESS_KEY` is `dev-secret-key`.
  - The `DATABASE_URL` password (read with `sqlalchemy.engine.make_url`) is `warranty`.

  In development it checks nothing.
- **Produces in `app/db.py`:**
  - `class Base(DeclarativeBase)`
  - `make_session_factory(url: str) -> sessionmaker[Session]`
  - `get_db(request: Request) -> Iterator[Session]`, which yields from `request.app.state.session_factory`.
- **Produces in `app/main.py`:**
  - `create_app(settings: Settings | None = None) -> FastAPI`, which sets `app.state.settings` and `app.state.session_factory`.
  - `GET /api/health`: runs `SELECT 1` through `get_db`. Returns 200 `{"status": "ok"}`, or 503 `{"status": "unavailable"}` on any `SQLAlchemyError`.
  - `get_settings(request: Request) -> Settings`
  - Module-level `app = create_app()`.
- **Produces fixtures in `tests/conftest.py`:**
  - `settings`, session-scoped:
    - `DATABASE_URL` from the `TEST_DATABASE_URL` environment variable, defaulting to `postgresql+psycopg://warranty:warranty@localhost:5432/warranty_test`.
    - `S3_ENDPOINT_URL=None`, `S3_BUCKET="test-bucket"`, `S3_ACCESS_KEY_ID="testing"`, `S3_SECRET_ACCESS_KEY="testing"`, `APP_BASE_URL="http://app.test"`, `SMTP_USERNAME=None`.
  - `engine`, session-scoped: `create_engine(settings.DATABASE_URL)`, disposed at the end. Task 2 adds building the schema from the migrations.
  - `db`: each test runs inside one connection-level transaction that is rolled back afterwards, using `Session(bind=connection, join_transaction_mode="create_savepoint")`.
  - `app`: `create_app(settings)`, with `get_db` overridden to yield `db` and `app.state.session_factory` set to return `db` wrapped so that `close()` does nothing.
    - **Changed 2026-11-23 (design §17):** the override opens a savepoint per request (`db.begin_nested()`) and rolls it back when the request ends, unless the route committed. This matches production, where `close()` throws away uncommitted work.
  - `client`: `TestClient(app)`.

- [ ] **Step 1: Add dev services and repo files**
  - **`.gitignore`** (already exists; confirm it lists): `.env`, `*.pdf`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `node_modules/`, `dist/`, `coverage/`.
  - **`docker-compose.yml`:**
    - `postgres`: image `postgres:18`; `POSTGRES_USER`, `POSTGRES_PASSWORD` and `POSTGRES_DB` all `warranty`; port 5432; a named volume mounted at `/var/lib/postgresql` (the Postgres 18 image's data location); mounts `./docker/postgres-init` at `/docker-entrypoint-initdb.d`. `01-test-db.sql` contains `CREATE DATABASE warranty_test;`. A healthcheck runs `pg_isready -U warranty`, which Task 17's backend waits on.
    - `seaweedfs`: image `chrislusf/seaweedfs:4.54`, command `server -dir=/data -s3 -s3.config=/etc/seaweedfs/s3.json`, host port 9000 → container 8333, a named volume, and `./docker/seaweedfs` mounted read-only. `docker/seaweedfs/s3.json` holds one identity with keys `dev-access-key` / `dev-secret-key`. (MinIO's official images were withdrawn; see design §3.)
    - `mailpit`: image `axllent/mailpit`, ports 1025 (SMTP) and 8025 (web).
    - No bucket-setup service: Task 4's `python -m app.setup_bucket` creates the bucket.
  - **`.env.example`:** every `Settings` field with its default. A comment marks the ones production must change: `APP_ENV`, `SESSION_COOKIE_SECURE`, `APP_BASE_URL`, `ALLOWED_ORIGINS`, `DATABASE_URL`, the S3 settings, the SMTP settings and `MAIL_FROM`.

- [ ] **Step 2: Write `backend/pyproject.toml` and set up the environment with `uv`**
  - `requires-python = ">=3.14"`, and `backend/.python-version` containing `3.14`.
  - Dependencies: `fastapi>=0.115`, `uvicorn[standard]>=0.32`, `sqlalchemy>=2.0.36`, `psycopg[binary]>=3.2`, `alembic>=1.14`, `pydantic>=2.9`, `pydantic-settings>=2.6`, `email-validator>=2.2`, `boto3>=1.35`, `httpx>=0.27`, `tzdata>=2024.2`.
  - A `[dependency-groups]` `dev` group: `pytest>=8.3`, `moto[s3]>=5.0`.
  - Add `[tool.pytest.ini_options] testpaths = ["tests"]`.
  - Run: `docker compose up -d`, then in `backend/`: `uv sync`. It creates `.venv` on Python 3.14, installs both groups and writes `uv.lock`.

- [ ] **Step 3: Write the failing test**

```python
# backend/tests/test_health.py
from fastapi.testclient import TestClient
from app.main import create_app

def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_health_reports_database_down(settings):
    down = settings.model_copy(update={"DATABASE_URL": "postgresql+psycopg://warranty:warranty@127.0.0.1:1/warranty"})
    response = TestClient(create_app(down)).get("/api/health")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
```

```python
# backend/tests/test_config.py
import pytest
from pydantic import ValidationError
from app.config import Settings

SAFE = dict(APP_ENV="production", SESSION_COOKIE_SECURE=True,
            APP_BASE_URL="https://claims.example.com", ALLOWED_ORIGINS=["https://claims.example.com"],
            DATABASE_URL="postgresql+psycopg://warranty:s3cret-db@db.example.com:5432/warranty",
            S3_ACCESS_KEY_ID="AKEXAMPLE", S3_SECRET_ACCESS_KEY="example-secret")

def test_development_accepts_dev_defaults():
    assert Settings(_env_file=None).APP_ENV == "development"

def test_production_accepts_safe_settings():
    assert Settings(_env_file=None, **SAFE).APP_ENV == "production"

def test_production_rejects_dev_defaults_and_names_each_problem():
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None, APP_ENV="production")
    message = str(exc.value)
    for name in ["SESSION_COOKIE_SECURE", "APP_BASE_URL", "ALLOWED_ORIGINS",
                 "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY", "DATABASE_URL"]:
        assert name in message

@pytest.mark.parametrize("override", [
    {"SESSION_COOKIE_SECURE": False},
    {"ALLOWED_ORIGINS": ["https://claims.example.com", "http://192.168.1.50:5173"]},
    {"S3_SECRET_ACCESS_KEY": "dev-secret-key"},
    {"DATABASE_URL": "postgresql+psycopg://warranty:warranty@db.example.com:5432/warranty"},
])
def test_production_rejects_each_unsafe_setting(override):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{**SAFE, **override})
```

- [ ] **Step 4: Run it to see it fail**

Run: `cd backend && uv run pytest tests/test_health.py tests/test_config.py -v`
Expected: errors importing `app.main` and `app.config`.

- [ ] **Step 5: Implement `Settings` (with the production checks), `db.py`, `create_app` with `GET /api/health`, and the conftest fixtures**, as described under Interfaces.

- [ ] **Step 6: Run it to see it pass**

Run: `uv run pytest tests/test_health.py tests/test_config.py -v`
Expected: all pass.

- [ ] **Step 7: Write `README.md`**
  - **Dev setup:**
    - `docker compose up -d`.
    - In `backend/`: `uv sync` (installs `uv`-managed Python 3.14 if needed), then `uv run uvicorn app.main:app --reload --port 8000`.
    - Tests: `uv run pytest`.
    - `npm run dev` (from Task 11).
    - Mailpit is at `http://localhost:8025`. SeaweedFS serves S3 at `http://localhost:9000`.
  - **"Testing on your iPhone" section:**
    - Find the laptop's LAN IP.
    - In `backend/.env`, set `APP_BASE_URL=http://<LAN-IP>:5173`, `ALLOWED_ORIGINS=["http://<LAN-IP>:5173","http://localhost:5173"]` and `S3_ENDPOINT_URL=http://<LAN-IP>:9000`.
    - Allow ports 5173 and 9000 through the laptop's firewall.
    - On the phone, open `http://<LAN-IP>:5173`.

- [ ] **Step 8: Commit**

```bash
git add .env.example docker-compose.yml docker README.md backend
git commit -m "chore: add dev services and backend skeleton"
```

---

### Task 2: Database models and first migration

**Files:**
- Create: `backend/app/models.py`, `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/versions/0001_initial.py`.
- Modify: `backend/tests/conftest.py`. The `engine` fixture builds the schema from the migrations.
- Test: `backend/tests/test_models.py`, `backend/tests/test_migrations.py`.

**Interfaces:**
- **Consumes:** `Base` (Task 1).
- **Produces in `app/models.py`:**
  - **Enums:** `class Role(StrEnum)` with `tech` and `reviewer`; `class ClaimStatus(StrEnum)` with `submitted`, `approved` and `closed`; `class PhotoKind(StrEnum)` with `vin`, `mileage` and `damage`. All are stored as strings (`Enum(..., native_enum=False, length=20)`).
  - **`utcnow() -> datetime`.** Every `created_at` is `DateTime(timezone=True)` with default `utcnow`.
  - **`User`** (table `users`): `id`, `name: str(100)`, `role: Role`, `email: str(254) | None`, `external_id: str(255) | None` (unique), `created_at`.
  - **`AuthSession`** (table `sessions`): `id`, `user_id` (FK), `user`, `token_hash: str(64)` (unique), `created_at`, `expires_at`.
  - **`Claim`** (table `claims`):
    - `id`, `owner_id` (FK to users), `owner`, `status: ClaimStatus = submitted`.
    - `warranty_company: str(120)`, `customer_first_name: str(100)`, `customer_last_name: str(100)`.
    - `vin: str(17)` (indexed), `claim_number: str(64) | None`, `submission_tz: str(64)`.
    - `form_data: dict` (JSONB, default `{}`), `created_at`, and `updated_at` (`onupdate=utcnow`).
    - Relationships `photos` and `messages`, both ordered by `id`.
  - **`Photo`** (table `photos`): `id`, `claim_id` (FK), `claim`, `kind: PhotoKind`, `storage_key: str(255)` (unique), `content_type: str(50)`, `original_filename: str(255) | None`, `description: str(200) | None`, `excluded: bool = False`, `added_by_id` (FK to users), `added_by`, `created_at`.
  - **`ChatMessage`** (table `chat_messages`): `id`, `claim_id` (FK), `sender_id` (FK), `sender`, `contents: Text`, `created_at`.
  - **`ClaimRead`** (table `claim_reads`): primary key (`user_id`, `claim_id`), `last_message_id: int = 0`, `last_photo_id: int = 0`.
- **Alembic wiring:**
  - `alembic.ini` has `script_location = %(here)s/alembic` and an empty `sqlalchemy.url`.
  - `env.py` uses `config.get_main_option("sqlalchemy.url") or Settings().DATABASE_URL`, imports `app.models`, and sets `target_metadata = Base.metadata`.
- **Changes the `engine` fixture:** after creating the engine, it runs `DROP SCHEMA public CASCADE; CREATE SCHEMA public`, then `alembic.command.upgrade(cfg, "head")`. `cfg` is a `Config` for `backend/alembic.ini`, found relative to `conftest.py`, with `sqlalchemy.url` set to the test URL (`%` escaped as `%%`).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_models.py
import pytest
from sqlalchemy.exc import IntegrityError
from app.models import Claim, ClaimRead, ClaimStatus, Photo, PhotoKind, Role, User

def make_claim(db):
    tech = User(name="Tess Tech", role=Role.tech)
    claim = Claim(owner=tech, warranty_company="Assurant", customer_first_name="Jane",
                  customer_last_name="Smith", vin="1M8GDM9AXKP042788",
                  submission_tz="America/New_York",
                  form_data={"customer_zip": "27519", "vehicle_year": 2024})
    db.add(claim)
    db.flush()
    return claim

def test_claim_defaults_and_form_data_round_trip(db):
    claim = make_claim(db)
    db.expire_all()
    loaded = db.get(Claim, claim.id)
    assert loaded.status == ClaimStatus.submitted
    assert loaded.form_data == {"customer_zip": "27519", "vehicle_year": 2024}
    assert loaded.created_at.tzinfo is not None
    assert loaded.claim_number is None

def test_photo_storage_key_is_unique(db):
    claim = make_claim(db)
    for _ in range(2):
        db.add(Photo(claim=claim, kind=PhotoKind.damage, storage_key="claims/1/a.jpg",
                     content_type="image/jpeg", description="Wheel.RF", added_by=claim.owner))
    with pytest.raises(IntegrityError):
        db.flush()

def test_one_read_state_per_user_and_claim(db):
    claim = make_claim(db)
    db.add_all([ClaimRead(user_id=claim.owner_id, claim_id=claim.id),
                ClaimRead(user_id=claim.owner_id, claim_id=claim.id)])
    with pytest.raises(IntegrityError):
        db.flush()
```

```python
# backend/tests/test_migrations.py
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
import app.models  # noqa: F401
from app.db import Base

def test_migrations_match_models(engine):
    with engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_models.py tests/test_migrations.py -v`
Expected: errors importing `app.models`.

- [ ] **Step 3: Implement `app/models.py` per Interfaces.**

- [ ] **Step 4: Create the first migration and wire the tests to it**
  - `uv run alembic init alembic`, then set up `alembic.ini` and `env.py` per Interfaces.
  - `uv run alembic revision --autogenerate -m "initial"` against the empty dev database, then rename the file to `0001_initial.py`.
  - Check that it creates the six tables, the unique constraints and the `vin` index.
  - Change the `engine` fixture per Interfaces.

- [ ] **Step 5: Run them to see them pass**

Run: `uv run pytest -v`
Expected: all pass, including `test_migrations_match_models`.

- [ ] **Step 6: Bring the dev database up to date**

Run: `uv run alembic upgrade head && uv run alembic check`
Expected: `No new upgrade operations detected.`

- [ ] **Step 7: Commit**

```bash
git add backend/app/models.py backend/alembic.ini backend/alembic backend/tests
git commit -m "feat: add database models and initial migration"
```

---

### Task 3: Anonymous sessions and the current user

**Files:**
- Create: `backend/app/auth.py`.
- Modify: `backend/app/main.py` (router and middleware) and `backend/tests/conftest.py` (fixtures).
- Test: `backend/tests/test_auth.py`.

**Interfaces:**
- **Consumes:** `User`, `AuthSession`, `Role` and `utcnow` (Task 2); `get_db` and `get_settings` (Task 1).
- **Produces in `app/auth.py`:**
  - **Tokens:** `hash_token(token: str) -> str` (SHA-256 hex). `start_session(db: Session, user: User, settings: Settings) -> str` creates the session row and returns the raw token from `secrets.token_urlsafe(32)`. `set_session_cookie(response: Response, token: str, settings: Settings) -> None`.
  - **`get_current_user(request, response, db, settings) -> User`:**
    - 401 `{"detail": "Not signed in"}` when the cookie is missing, unknown or expired.
    - Renews `expires_at` and re-sets the cookie when the expiry is more than one day short of a full TTL.
  - **Role guards:** `require_reviewer(user = Depends(get_current_user)) -> User` and `require_tech(...) -> User`, both returning 403 on the wrong role.
  - **`class OriginCheckMiddleware`:** 403 `{"detail": "Origin not allowed"}`.
  - **`router`:**
    - `POST /api/session`, body `SessionCreate{name: str 1–100 stripped, role: Role, email: EmailStr | None = None}`. Returns 201 `MeOut` and sets the cookie.
    - `DELETE /api/session`: deletes the session row, clears the cookie, returns 204.
    - `GET /api/me`: returns `MeOut{id, name, role, email}`.
    - `PATCH /api/me`, body `MeUpdate{name: str 1–100 | None, email: EmailStr | None}` (only fields that are sent are applied). Returns `MeOut`.
- **Produces fixtures:**
  - `make_user(role=Role.tech, name="Tess Tech", email=None) -> User`.
  - `client_for(user) -> TestClient`: a new `TestClient(app)` with a cookie from `start_session`.
  - `tech`; `reviewer` (email `kim@example.com`); `tech_client`; `reviewer_client`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_auth.py
import hashlib
from datetime import timedelta
from fastapi import Depends
from app.auth import require_reviewer
from app.models import AuthSession, utcnow

def test_role_picker_creates_user_and_session(client):
    r = client.post("/api/session", json={"name": "Tess Tech", "role": "tech"})
    assert r.status_code == 201
    assert r.json()["role"] == "tech" and r.json()["email"] is None
    assert client.get("/api/me").json()["name"] == "Tess Tech"

def test_session_cookie_flags(client):
    cookie = client.post("/api/session", json={"name": "Tess", "role": "tech"}).headers["set-cookie"]
    assert "warranty_session=" in cookie and "HttpOnly" in cookie
    assert "Max-Age=31536000" in cookie and "samesite=lax" in cookie.lower()

def test_reviewer_with_email(client):
    r = client.post("/api/session", json={"name": "Kim", "role": "reviewer", "email": "kim@example.com"})
    assert r.status_code == 201 and r.json()["email"] == "kim@example.com"

def test_bad_email_and_blank_name_rejected(client):
    assert client.post("/api/session", json={"name": "Kim", "role": "reviewer", "email": "nope"}).status_code == 422
    assert client.post("/api/session", json={"name": "  ", "role": "tech"}).status_code == 422

def test_token_stored_only_as_hash(client, db):
    client.post("/api/session", json={"name": "Tess", "role": "tech"})
    token = client.cookies["warranty_session"]
    assert db.query(AuthSession).one().token_hash == hashlib.sha256(token.encode()).hexdigest()

def test_me_requires_a_known_session(client):
    assert client.get("/api/me").status_code == 401
    client.cookies.set("warranty_session", "made-up")
    assert client.get("/api/me").status_code == 401

def test_expired_session_rejected(db, tech, client_for):
    c = client_for(tech)
    db.query(AuthSession).update({"expires_at": utcnow() - timedelta(minutes=1)})
    assert c.get("/api/me").status_code == 401

def test_session_renewed_after_a_day(db, tech, client_for):
    c = client_for(tech)
    db.query(AuthSession).update({"expires_at": utcnow() + timedelta(days=300)})
    assert "warranty_session=" in c.get("/api/me").headers.get("set-cookie", "")
    assert db.query(AuthSession).one().expires_at > utcnow() + timedelta(days=364)

def test_update_me(tech_client):
    r = tech_client.patch("/api/me", json={"name": "Tess T", "email": "tess@example.com"})
    assert (r.json()["name"], r.json()["email"]) == ("Tess T", "tess@example.com")

def test_end_session(tech_client):
    assert tech_client.delete("/api/session").status_code == 204
    assert tech_client.get("/api/me").status_code == 401

def test_role_guard(app, tech_client, reviewer_client):
    app.add_api_route("/api/test-reviewer-only", lambda user=Depends(require_reviewer): {"ok": True})
    assert tech_client.get("/api/test-reviewer-only").status_code == 403
    assert reviewer_client.get("/api/test-reviewer-only").status_code == 200

def test_cross_origin_writes_rejected(client):
    body = {"name": "Tess", "role": "tech"}
    assert client.post("/api/session", json=body, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/session", json=body, headers={"Origin": "http://localhost:5173"}).status_code == 201
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_auth.py -v`
Expected: an error importing `app.auth`.

- [ ] **Step 3: Implement `app/auth.py` and the fixtures per Interfaces.** Include the router and add `OriginCheckMiddleware` in `create_app`.

- [ ] **Step 4: Run them to see them pass**

Run: `uv run pytest -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app backend/tests
git commit -m "feat: anonymous sessions with role picker and current-user checks"
```

---

### Task 4: Photo storage and upload URLs

**Files:**
- Create: `backend/app/storage.py`, `backend/app/uploads.py`, `backend/app/setup_bucket.py`.
- Modify: `backend/app/main.py` (router; `app.state.storage = build_storage(settings)`), `backend/tests/conftest.py` (fixtures) and `README.md` (dev setup step).
- Test: `backend/tests/test_storage.py`, `backend/tests/test_uploads.py`, `backend/tests/test_setup_bucket.py`.

**Interfaces:**
- **Consumes:** `get_current_user` (Task 3), `Settings`.
- **Produces in `app/storage.py`:**
  - `@dataclass PresignedUpload(url: str, fields: dict[str, str])` and `@dataclass ObjectInfo(content_type: str, size: int)`.
  - **`class PhotoStorage(client, bucket: str)`**, with public attributes `client` and `bucket`:
    - `presign_upload(key: str, content_type: str, max_bytes: int, expires_in: int = 900) -> PresignedUpload`. A pre-signed POST whose conditions are the exact `Content-Type` and `content-length-range` from 1 to `max_bytes`.
    - `head(key: str) -> ObjectInfo | None`.
    - `promote(upload_key: str, claim_id: int) -> str`. Server-side copy to `claims/{claim_id}/{basename}`, delete the source, return the new key.
    - `presign_download(key: str, download_name: str | None = None, expires_in: int = 900) -> str`. When `download_name` is given, adds `ResponseContentDisposition='attachment; filename="<name>"'`.
    - `iter_object(key: str, chunk_size: int = 1_048_576) -> Iterator[bytes]`.
  - **`build_storage(settings: Settings) -> PhotoStorage`:** a boto3 client with `Config(signature_version="s3v4", s3={"addressing_style": "path"})`, plus endpoint, region and keys from settings.
  - **`get_storage(request: Request) -> PhotoStorage`.**
- **Produces in `app/setup_bucket.py`:**
  - **`ensure_bucket(storage: PhotoStorage, region: str, allowed_origins: list[str]) -> None`.** Safe to run repeatedly:
    - If `head_bucket` raises a 404 `ClientError`, creates the bucket. It passes `CreateBucketConfiguration={"LocationConstraint": region}` unless `region == "us-east-1"`.
    - Puts the lifecycle configuration: one rule, `ID="expire-uploads"`, `Filter={"Prefix": "uploads/"}`, `Status="Enabled"`, `Expiration={"Days": 7}`.
    - Puts the CORS configuration: one rule with `AllowedOrigins=allowed_origins`, `AllowedMethods=["GET", "POST"]`, `AllowedHeaders=["*"]`, `ExposeHeaders=["ETag"]` and `MaxAgeSeconds=3000`. If that raises a `ClientError` with code `NotImplemented` (a store without per-bucket CORS), it logs a warning and returns normally.
  - **`main() -> None`**, run by `python -m app.setup_bucket`: builds `Settings()` and calls `ensure_bucket(build_storage(settings), settings.S3_REGION, settings.ALLOWED_ORIGINS)`.
- **Produces in `app/uploads.py`:** `POST /api/uploads`, any signed-in user.
  - Body: `UploadRequest{content_type: Literal["image/jpeg", "image/png"], filename: str 1–255}`.
  - Returns 201 `UploadOut{key, url, fields}`.
  - Key: `uploads/{user.id}/{uuid4().hex}.jpg|png`.
- **Produces fixtures:**
  - `storage`: inside `moto.mock_aws()`, `PhotoStorage(boto3.client("s3", region_name="us-east-1"), "test-bucket")` with the bucket created and `get_storage` overridden.
  - `put_upload(user, content_type="image/jpeg", body=b"fake-jpeg-bytes") -> str`: puts an object at a fresh `uploads/{user.id}/{uuid}.jpg` key and returns the key.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_uploads.py
def test_upload_url_for_jpeg(tech_client, tech, storage):
    r = tech_client.post("/api/uploads", json={"content_type": "image/jpeg", "filename": "IMG_0001.jpg"})
    assert r.status_code == 201
    body = r.json()
    assert body["key"].startswith(f"uploads/{tech.id}/") and body["key"].endswith(".jpg")
    assert body["fields"]["Content-Type"] == "image/jpeg" and "policy" in body["fields"]

def test_png_gets_png_extension(tech_client, storage):
    r = tech_client.post("/api/uploads", json={"content_type": "image/png", "filename": "a.png"})
    assert r.json()["key"].endswith(".png")

def test_heic_rejected(tech_client, storage):
    assert tech_client.post("/api/uploads", json={"content_type": "image/heic", "filename": "a.heic"}).status_code == 422

def test_upload_requires_session(client, storage):
    assert client.post("/api/uploads", json={"content_type": "image/jpeg", "filename": "a.jpg"}).status_code == 401
```

```python
# backend/tests/test_storage.py
from app.config import Settings
from app.storage import build_storage

def test_presigned_urls_use_configured_endpoint():
    s = build_storage(Settings(S3_ENDPOINT_URL="http://192.168.1.50:9000", S3_BUCKET="warranty-photos"))
    assert s.presign_upload("uploads/1/a.jpg", "image/jpeg", 1000).url.startswith("http://192.168.1.50:9000/warranty-photos")
    assert s.presign_download("claims/1/a.jpg").startswith("http://192.168.1.50:9000/warranty-photos/claims/1/a.jpg")

def test_promote_moves_object(storage):
    storage.client.put_object(Bucket="test-bucket", Key="uploads/1/abc.jpg", Body=b"x", ContentType="image/jpeg")
    new_key = storage.promote("uploads/1/abc.jpg", claim_id=7)
    assert new_key == "claims/7/abc.jpg"
    assert storage.head(new_key).content_type == "image/jpeg"
    assert storage.head("uploads/1/abc.jpg") is None

def test_download_url_names_the_file(storage):
    storage.client.put_object(Bucket="test-bucket", Key="claims/7/abc.jpg", Body=b"x")
    url = storage.presign_download("claims/7/abc.jpg", download_name="ASSURANT.KP042788.SMITH.VIN.11.26.jpg")
    assert "response-content-disposition=attachment" in url
```

```python
# backend/tests/test_setup_bucket.py
import boto3, pytest
from botocore.exceptions import ClientError
from moto import mock_aws
from app.setup_bucket import ensure_bucket
from app.storage import PhotoStorage

ORIGINS = ["http://192.168.1.50:5173"]

@pytest.fixture
def empty_storage():
    with mock_aws():
        yield PhotoStorage(boto3.client("s3", region_name="us-east-1"), "fresh-bucket")

def test_creates_bucket_with_upload_expiry_and_cors(empty_storage):
    ensure_bucket(empty_storage, "us-east-1", ORIGINS)
    rules = empty_storage.client.get_bucket_lifecycle_configuration(Bucket="fresh-bucket")["Rules"]
    assert [(r["Filter"]["Prefix"], r["Expiration"]["Days"], r["Status"]) for r in rules] == [("uploads/", 7, "Enabled")]
    cors = empty_storage.client.get_bucket_cors(Bucket="fresh-bucket")["CORSRules"]
    assert cors[0]["AllowedOrigins"] == ORIGINS and set(cors[0]["AllowedMethods"]) == {"GET", "POST"}

def test_running_twice_is_safe(empty_storage):
    ensure_bucket(empty_storage, "us-east-1", ORIGINS)
    ensure_bucket(empty_storage, "us-east-1", ORIGINS)
    assert len(empty_storage.client.get_bucket_lifecycle_configuration(Bucket="fresh-bucket")["Rules"]) == 1

def test_store_without_bucket_cors_still_gets_lifecycle(empty_storage, monkeypatch):
    def not_implemented(**kwargs):
        raise ClientError({"Error": {"Code": "NotImplemented", "Message": "x"}}, "PutBucketCors")
    monkeypatch.setattr(empty_storage.client, "put_bucket_cors", not_implemented)
    ensure_bucket(empty_storage, "us-east-1", ORIGINS)
    assert empty_storage.client.get_bucket_lifecycle_configuration(Bucket="fresh-bucket")["Rules"]
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_storage.py tests/test_uploads.py tests/test_setup_bucket.py -v`
Expected: errors importing `app.storage` and `app.setup_bucket`.

- [ ] **Step 3: Implement `storage.py`, `uploads.py`, `setup_bucket.py` and the fixtures per Interfaces.**

- [ ] **Step 4: Run them to see them pass**

Run: `uv run pytest -v`
Expected: all pass.

- [ ] **Step 5: Set up the dev bucket against SeaweedFS**
  - Run: `uv run python -m app.setup_bucket`, twice.
  - Expected: both runs exit 0 without CORS warnings, and `uv run python -c "from app.config import Settings; from app.storage import build_storage; s = build_storage(Settings()); print(s.client.get_bucket_lifecycle_configuration(Bucket=s.bucket)['Rules'])"` prints the `uploads/` 7-day rule.
  - Add the command to the README's dev setup, after `uv sync`: "run once, and again whenever `ALLOWED_ORIGINS` changes."

- [ ] **Step 6: Commit**

```bash
git add backend/app backend/tests README.md
git commit -m "feat: pre-signed photo uploads to S3-compatible storage"
```

---

### Task 5: Export filename rules

**Changed 2026-11-23 (design §8, §12), after this task was built:** damage descriptions come from a fixed list, `DamageLabel` in `app/photos/labels.py`. `description_segment` now only turns spaces into dots. The cleanup of typed text, the `Damage` fallback and the case-insensitive comparison are removed, and `test_every_damage_label_is_filename_safe` checks the list instead. The steps below describe Task 5 as first built.

**Files:**
- Create: `backend/app/photos/__init__.py`, `backend/app/photos/naming.py`.
- Test: `backend/tests/test_naming.py`.

**Interfaces:**
- **Consumes:** `Claim`, `Photo` and `PhotoKind` (Task 2).
- **Produces in `app/photos/naming.py`:**
  - `upper_segment(value: str) -> str`
  - `description_segment(value: str) -> str`
  - `submission_month_year(created_at: datetime, tz_name: str) -> tuple[str, str]`
  - `export_filename(*, warranty_company: str, vin: str, last_name: str, description: str, created_at: datetime, tz_name: str, content_type: str) -> str`
  - `export_filenames(claim: Claim) -> dict[int, str]`: photo id → filename. Excluded photos are left out.
  - `zip_filename(claim: Claim) -> str`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_naming.py
from datetime import UTC, datetime
import pytest
from app.models import Claim, Photo, PhotoKind
from app.photos.naming import (description_segment, export_filename, export_filenames,
                               submission_month_year, upper_segment, zip_filename)

NOV_13 = datetime(2026, 11, 13, 15, 0, tzinfo=UTC)

def test_export_filename_matches_convention():
    assert export_filename(warranty_company="Assurant", vin="1M8GDM9AXKP042788", last_name="Smith",
                           description="Wheel.RF", created_at=NOV_13, tz_name="America/New_York",
                           content_type="image/jpeg") == "ASSURANT.KP042788.SMITH.Wheel.RF.11.26.jpg"

def test_png_extension():
    assert export_filename(warranty_company="Assurant", vin="1M8GDM9AXKP042788", last_name="Smith",
                           description="VIN", created_at=NOV_13, tz_name="America/New_York",
                           content_type="image/png").endswith(".VIN.11.26.png")

@pytest.mark.parametrize("raw, expected", [
    ("de la Cruz", "DELACRUZ"), ("Muñoz", "MUNOZ"), ("O'Brien", "OBRIEN"),
    ("Smith-Jones", "SMITH-JONES"), ("CNA National", "CNANATIONAL"), ("李", "UNKNOWN")])
def test_upper_segment(raw, expected):
    assert upper_segment(raw) == expected

@pytest.mark.parametrize("raw, expected", [
    (" Wheel RF ", "Wheel.RF"), ("PDR.LQP", "PDR.LQP"), ("door ding / LF", "door.ding.LF")])
def test_description_segment(raw, expected):
    assert description_segment(raw) == expected

@pytest.mark.parametrize("utc, tz, expected", [
    (datetime(2026, 12, 1, 3, 30, tzinfo=UTC), "America/New_York", ("11", "26")),
    (datetime(2026, 12, 1, 3, 30, tzinfo=UTC), "America/Los_Angeles", ("11", "26")),
    (datetime(2026, 12, 1, 3, 30, tzinfo=UTC), "UTC", ("12", "26")),
    (datetime(2027, 1, 1, 4, 59, tzinfo=UTC), "America/New_York", ("12", "26"))])
def test_month_follows_submission_time_zone(utc, tz, expected):
    assert submission_month_year(utc, tz) == expected

def build_claim(*damage, excluded=()):
    claim = Claim(id=1, warranty_company="Assurant", customer_last_name="Smith",
                  vin="1M8GDM9AXKP042788", created_at=NOV_13, submission_tz="America/New_York")
    photos = [Photo(id=20, kind=PhotoKind.mileage, content_type="image/jpeg", excluded=False),
              Photo(id=10, kind=PhotoKind.vin, content_type="image/jpeg", excluded=False)]
    for photo_id, desc in enumerate(damage, start=11):
        photos.append(Photo(id=photo_id, kind=PhotoKind.damage, description=desc,
                            content_type="image/jpeg", excluded=photo_id in excluded))
    claim.photos = photos
    return claim

def test_export_filenames_defaults_dedupes_and_skips_excluded():
    assert export_filenames(build_claim("Wheel.RF", "wheel.rf", "PDR.LQP", excluded={13})) == {
        10: "ASSURANT.KP042788.SMITH.VIN.11.26.jpg",
        20: "ASSURANT.KP042788.SMITH.Mileage.11.26.jpg",
        11: "ASSURANT.KP042788.SMITH.Wheel.RF.11.26.jpg",
        12: "ASSURANT.KP042788.SMITH.wheel.rf-2.11.26.jpg"}

def test_zip_filename():
    assert zip_filename(build_claim("Wheel.RF")) == "ASSURANT.KP042788.SMITH.11.26.zip"
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_naming.py -v`
Expected: an error importing `app.photos.naming`.

- [ ] **Step 3: Implement `app/photos/naming.py` with these rules:**
  - **`upper_segment`:** NFKD-normalize and drop non-ASCII characters, uppercase, keep only `A–Z 0–9 -`. If nothing is left, return `UNKNOWN`.
  - **`description_segment`:**
    - NFKD-normalize to ASCII and trim.
    - Replace runs of whitespace with `.`.
    - Drop characters outside `A–Z a–z 0–9 . _ -`.
    - Collapse repeated dots.
    - Strip leading and trailing `.`, `-` and `_`.
  - **`submission_month_year`:** convert to `ZoneInfo(tz_name)`, then return two-digit month and two-digit year.
  - **Extension:** `image/jpeg` gives `jpg`; `image/png` gives `png`.
  - **`export_filenames`:**
    - Order VIN photos, then mileage, then damage, each by id. Skip excluded photos.
    - VIN photos use the description `VIN`; mileage photos use `Mileage`.
    - Compare descriptions case-insensitively. The second occurrence gets `-2` appended to its description segment, the third `-3`.
  - **`zip_filename`:** `{COMPANY}.{VIN8}.{LAST}.{MM}.{YY}.zip`.

- [ ] **Step 4: Run them to see them pass**

Run: `uv run pytest tests/test_naming.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/photos backend/tests/test_naming.py
git commit -m "feat: export filename rules"
```

---

### Task 6: Claim submission, listing and search

**Files:**
- Create: `backend/app/claims/__init__.py`, `backend/app/claims/schemas.py`, `backend/app/claims/access.py`, `backend/app/claims/routes.py`, `backend/app/photos/attach.py`.
- Modify: `backend/app/main.py` (router) and `backend/tests/conftest.py` (fixtures).
- Test: `backend/tests/test_claims_create.py`, `backend/tests/test_claims_list.py`.

**Interfaces:**
- **Consumes:** the models (Task 2), `get_current_user` and `require_tech` (Task 3), and `PhotoStorage.head`/`promote` with `get_storage` (Task 4).
- **Produces in `app/claims/schemas.py`:**
  - `US_STATE_CODES: frozenset[str]`: the 50 states plus `DC`.
  - `VIN_PATTERN = r"^[A-HJ-NPR-Z0-9]{17}$"`.
  - **`ClaimFormData`**, with `extra="forbid"`; optional strings that are blank become `None`:
    - `customer_phone: str`: strip non-digits, then exactly 10 digits.
      - **Changed 2026-11-23 (design §7):** 11 digits starting with 1 lose the 1 first, so "+1 (608) 555-0134" is stored as `6085550134`.
    - `customer_address: str` (1–200), `customer_city: str` (1–100).
    - `customer_state: str`: uppercased, must be in `US_STATE_CODES`.
    - `customer_zip: str`: exactly 5 digits.
    - `vehicle_year: int`: from 1900 to the current year + 2.
    - `vehicle_make: str` (1–60), `vehicle_model: str` (1–60).
    - `mileage: int | None` (0–2,000,000), `contract_number: str | None` (≤ 64).
  - **`PhotoRef{key: str, kind: PhotoKind, description: DamageLabel | None, original_filename: str | None (≤ 255)}`.**
  - **Changed 2026-11-23 (design §4, §8):** `DamageLabel` and `DAMAGE_LABELS` come from `app/photos/labels.py`, added with the naming cleanup after Task 5. `DamageLabel = Literal["Wheel RF", "Wheel LF", "Wheel LR", "Wheel RR"]` is a placeholder list, and `DAMAGE_LABELS = get_args(DamageLabel)`. A description that isn't on the list is a 422. The `photos.description` column stays plain text.
  - **`ClaimCreate`:**
    - Fields: `warranty_company` (1–120); `customer_first_name` and `customer_last_name` (1–100); `vin` (stripped, uppercased, must match `VIN_PATTERN`); `claim_number: str | None` (≤ 64); `submission_tz: str` (must load as a `ZoneInfo`); `form_data: ClaimFormData`; `photos: list[PhotoRef]` (2–60).
    - A model validator requires exactly one `vin` photo, at most one `mileage` photo, at least one `damage` photo, and a non-blank description on every damage photo.
  - **Responses:**
    - `UserBrief{id, name, role}`.
    - `ClaimSummary{id, status, created_at, warranty_company, customer_first_name, customer_last_name, vin, claim_number, owner: UserBrief}`.
    - `ClaimDetail(ClaimSummary){form_data: dict, submission_tz, updated_at}`.
    - `ClaimPage{items: list[ClaimSummary], total, page, limit}`.
    - `FormOptions{damage_labels: list[str], warranty_companies: list[str]}`.
- **Produces `get_visible_claim(claim_id: int, user: User, db: Session) -> Claim`** in `app/claims/access.py`. Returns 404 `{"detail": "Claim not found"}` when the claim is missing, or when the user is a tech who doesn't own it.
- **Produces `attach_photos(db: Session, storage: PhotoStorage, claim: Claim, refs: list[PhotoRef], user: User) -> list[Photo]`** in `app/photos/attach.py`:
  - First checks every key, before moving anything. Each key must start with `uploads/{user.id}/` and exist (`storage.head`). Otherwise it returns 422 `{"detail": "Photo upload not found"}`.
  - **Changed 2026-11-23 (design §8):** "starts with" becomes the exact shape the upload route hands out, `uploads/{user.id}/{32 hex}.{an extension from EXTENSIONS}`. The shape is checked before `storage.head`, so storage is never asked about a key like `uploads/1/../2/….jpg`.
  - Then promotes each object and creates the `Photo` rows. `content_type` comes from `head`; `added_by` is the user.
  - **Changed 2026-11-20 (design §8, "Copy now, delete later"):** `attach_photos` only copies. The route deletes the `uploads/` originals after `db.commit()` succeeds, and a failed delete doesn't fail the request. `PhotoStorage.promote` splits into a copy step and a delete step; the method names are settled during Task 6.
- **Produces routes in `app/claims/routes.py`:**
  - `POST /api/claims` (`require_tech`): 201 `ClaimDetail`.
  - `GET /api/claims?q=&status=&page=1&limit=25` (limit at most 100): a `ClaimPage` sorted by `created_at` then `id`, newest first.
  - `GET /api/claims/{id}`: `ClaimDetail`.
  - `GET /api/options` (any signed-in user): `FormOptions`. `damage_labels` is `DAMAGE_LABELS`. `warranty_companies` is every name used on a claim, from `warranty_company_names(db)`; names that differ only in case appear once, using the earliest spelling. Most used first, ties alphabetical ignoring case (owner's decision, 2026-11-23). There's no `q` and no cap: the phone filters the list as the tech types.
  - **Changed 2026-11-23 (design §4, §14):** this replaces `GET /api/warranty-companies?q=` (at most 10 matches).
- **Produces fixtures:**
  - `claim_payload(user) -> dict`: a valid `ClaimCreate` with fresh uploads. It has a VIN photo and one damage photo described `Wheel RF`, in that order. Values:
    - Customer: Jane Smith, phone `(608) 555-0134`, `100 Main St`, Cary, `NC`, `27519`.
    - Vehicle: 2024 Honda Civic.
    - `Assurant`, VIN `1M8GDM9AXKP042788`, `America/New_York`.
  - `make_claim(owner: User, **overrides) -> Claim`: posts `claim_payload(owner)`, with top-level overrides merged in, as that owner. Returns the `Claim` from `db`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_claims_create.py
import pytest
from app.models import Claim, Photo

def test_tech_submits_claim(tech_client, claim_payload, tech, storage, db):
    payload = claim_payload(tech)
    payload["vin"] = " 1m8gdm9axkp042788 "
    r = tech_client.post("/api/claims", json=payload)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "submitted" and body["vin"] == "1M8GDM9AXKP042788"
    assert body["form_data"]["customer_phone"] == "6085550134"
    assert body["owner"]["id"] == tech.id
    photos = db.query(Photo).filter_by(claim_id=body["id"]).all()
    assert {p.kind for p in photos} == {"vin", "damage"}
    assert all(p.storage_key.startswith(f"claims/{body['id']}/") for p in photos)
    assert storage.head(payload["photos"][0]["key"]) is None

def test_reviewer_cannot_submit(reviewer_client, claim_payload, reviewer):
    assert reviewer_client.post("/api/claims", json=claim_payload(reviewer)).status_code == 403

@pytest.mark.parametrize("field, value", [
    ("vin", "1M8GDM9AXKPO42788"), ("vin", "1M8GDM9AXKP04278"),
    ("warranty_company", ""), ("submission_tz", "Mars/Olympus")])
def test_top_level_validation(tech_client, claim_payload, tech, field, value):
    payload = claim_payload(tech)
    payload[field] = value
    assert tech_client.post("/api/claims", json=payload).status_code == 422

@pytest.mark.parametrize("field, value", [
    ("customer_zip", "2751"), ("customer_state", "XX"), ("customer_phone", "608555013"),
    ("vehicle_year", 1899), ("customer_city", "")])
def test_form_validation(tech_client, claim_payload, tech, field, value):
    payload = claim_payload(tech)
    payload["form_data"][field] = value
    assert tech_client.post("/api/claims", json=payload).status_code == 422

def test_photo_rules(tech_client, claim_payload, tech, put_upload):
    def post(photos):
        payload = claim_payload(tech)
        payload["photos"] = photos
        return tech_client.post("/api/claims", json=payload).status_code
    vin = lambda: {"key": put_upload(tech), "kind": "vin"}
    damage = lambda d="Wheel RF": {"key": put_upload(tech), "kind": "damage", "description": d}
    mileage = lambda: {"key": put_upload(tech), "kind": "mileage"}
    assert post([damage(), damage()]) == 422                  # no VIN photo
    assert post([vin(), vin(), damage()]) == 422              # two VIN photos
    assert post([vin(), mileage()]) == 422                    # no damage photo
    assert post([vin(), damage("  ")]) == 422                 # blank description
    assert post([vin(), damage("Door LF")]) == 422            # not a damage label
    assert post([vin(), mileage(), mileage(), damage()]) == 422
    assert post([vin(), mileage(), damage()]) == 201

def test_forged_or_reused_photo_keys_rejected(tech_client, claim_payload, tech, make_user, put_upload, storage, db):
    other = make_user(name="Other Tech")
    first = claim_payload(tech)
    assert tech_client.post("/api/claims", json=first).status_code == 201
    for bad_key in [put_upload(other), f"uploads/{tech.id}/never-uploaded.jpg", first["photos"][0]["key"]]:
        payload = claim_payload(tech)
        payload["photos"][1]["key"] = bad_key
        assert tech_client.post("/api/claims", json=payload).status_code == 422
        assert storage.head(payload["photos"][0]["key"]) is not None   # nothing was moved
    assert db.query(Claim).count() == 1
```

```python
# backend/tests/test_claims_list.py
from app.models import ClaimStatus
from app.photos.labels import DAMAGE_LABELS

def ids(response):
    return [c["id"] for c in response.json()["items"]]

def test_tech_sees_only_own_claims_reviewer_sees_all(tech, tech_client, reviewer_client, make_user, make_claim):
    mine, other = make_claim(tech), make_claim(make_user(name="Other Tech"))
    assert ids(tech_client.get("/api/claims")) == [mine.id]
    assert set(ids(reviewer_client.get("/api/claims"))) == {mine.id, other.id}

def test_tech_gets_404_for_someone_elses_claim(tech_client, reviewer_client, make_user, make_claim):
    other = make_claim(make_user(name="Other Tech"))
    assert tech_client.get(f"/api/claims/{other.id}").status_code == 404
    assert reviewer_client.get(f"/api/claims/{other.id}").status_code == 200

def test_search_matches_name_vin_and_claim_number(tech, reviewer_client, make_claim):
    a = make_claim(tech, claim_number="AUTH-51")
    b = make_claim(tech, customer_first_name="Raj", customer_last_name="Patel", vin="11111111111111111")
    for q, expected in [("smith", [a.id]), ("jane smith", [a.id]), ("042788", [a.id]),
                        ("auth-51", [a.id]), ("patel", [b.id])]:
        assert ids(reviewer_client.get("/api/claims", params={"q": q})) == expected

def test_status_filter(tech, reviewer_client, make_claim, db):
    make_claim(tech)
    b = make_claim(tech)
    b.status = ClaimStatus.approved
    db.flush()
    assert ids(reviewer_client.get("/api/claims", params={"status": "approved"})) == [b.id]

def test_pagination_newest_first(tech, reviewer_client, make_claim):
    c1, c2, c3 = make_claim(tech), make_claim(tech), make_claim(tech)
    page1 = reviewer_client.get("/api/claims", params={"limit": 2, "page": 1}).json()
    page2 = reviewer_client.get("/api/claims", params={"limit": 2, "page": 2}).json()
    assert [c["id"] for c in page1["items"]] == [c3.id, c2.id] and page1["total"] == 3
    assert [c["id"] for c in page2["items"]] == [c1.id]

def test_form_options(tech, tech_client, make_claim):
    for name in ["Assurant", "assurant", "CNA National"]:
        make_claim(tech, warranty_company=name)
    body = tech_client.get("/api/options").json()
    assert body["damage_labels"] == list(DAMAGE_LABELS)
    assert sorted(body["warranty_companies"]) == ["Assurant", "CNA National"]
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_claims_create.py tests/test_claims_list.py -v`
Expected: FAIL, with 404s on `/api/claims` or a missing `claim_payload` fixture.

- [ ] **Step 3: Implement the schemas, `get_visible_claim`, `attach_photos`, `warranty_company_names`, the routes and the fixtures per Interfaces.**
  - **Search:** `q` matches with case-insensitive `ILIKE %q%` against the first name, the last name, `first || ' ' || last`, the VIN and the claim number. Escape `%` and `_` in `q`.
  - **Submit order:** create the claim, flush to get its id, then call `attach_photos`.

- [ ] **Step 4: Run them to see them pass**

Run: `uv run pytest -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app backend/tests
git commit -m "feat: claim submission, listing and search"
```

---

### Task 7: Photos on submitted claims, reviewer edits and export

**Changed 2026-11-23 (design §4, §8): damage descriptions come from `DamageLabel`.** `PhotoUpdate.description` and the add-photos body use `DamageLabel | None`, so a value off the list is a 422. When this task opens, the test values below that aren't labels (`Door.LF`, `Hood`, `PDR.LQP`, `wheel.rf`, `Wheel.RF`) change to labels, and the export test's two same-wheel photos replace its case-insensitive duplicate.

**Files:**
- Create: `backend/app/photos/routes.py`.
- Modify: `backend/app/claims/schemas.py`, `backend/app/claims/routes.py`, `backend/app/main.py`.
- Test: `backend/tests/test_claim_edits.py`, `backend/tests/test_photos.py`.

**Interfaces:**
- **Consumes:** `get_visible_claim` and `attach_photos` (Task 6); `export_filenames` and `zip_filename` (Task 5); `presign_download` and `iter_object` (Task 4); `require_reviewer` and `require_tech` (Task 3).
- **Produces `PATCH /api/claims/{id}`** (`require_reviewer`) with body `ClaimUpdate`. Returns `ClaimDetail`.
  - Every field is optional, with the same rules as `ClaimCreate`.
  - `claim_number` may be set to null; null is rejected for every other field.
  - `status: ClaimStatus`.
  - `form_data: ClaimFormData` replaces the whole object.
- **Produces `PhotoOut{id, kind, description, excluded, original_filename, added_by: UserBrief, created_at, url, export_filename: str | None}`.** `url` comes from `presign_download(key)`. `export_filename` is `None` when the photo is excluded.
- **Produces `GET /api/claims/{id}/photos`:** `list[PhotoOut]`, ordered VIN, then mileage, then damage, each by id.
- **Produces `POST /api/claims/{id}/photos`** with body `PhotoAdd{photos: list[PhotoRef] (1–30)}`. Returns 201 with `list[PhotoOut]` of just the new photos.
  - Only the owning tech can add. Reviewers get 403; other techs get 404.
  - 409 `{"detail": "Claim is closed"}` when the claim is closed.
  - 422 for a `vin` photo, for a `mileage` photo when the claim already has one or more than one is sent, and for a blank damage description.
- **Produces `PATCH /api/claims/{id}/photos/{photo_id}`** (`require_reviewer`) with body `PhotoUpdate{description: str | None, excluded: bool | None}`. Returns `PhotoOut`. A blank description on a damage photo is a 422.
- **Produces `GET /api/claims/{id}/photos/export`:**
  - An `application/zip` stream with `Content-Disposition: attachment; filename="<zip_filename>"`.
  - Entries are named by `export_filenames` and stored uncompressed (`ZIP_STORED`). The zip is built in a `SpooledTemporaryFile`.
  - 409 `{"detail": "No photos to export"}` when every photo is excluded.
  - **Changed 2026-11-23 (design §12):** `require_reviewer`, so a tech gets 403. Add a test for it.

**Also decided 2026-11-23, when this task opened:**
- `ClaimUpdate` has no `submission_tz` field, so sending one is a 422 (design §12).
- The same key twice in one add-photos request gets 422 "Duplicate photo key" (design §8).
- An explicit `null` in `PhotoUpdate` is a 422, as in `ClaimUpdate`.
- A description on a VIN or mileage photo is a 422 on submit, on add-photos and in the photo edit (design §12).
- `iter_object` was in Task 4's interface but never built, so it's added here, with a test.
- Where the photo rules live (design §8): the label rules on `PhotoRef`, replacing `ClaimCreate`'s damage-label check. The request-only rules go in a `PhotoAdd` model validator, and the closed and existing-mileage rules in a function the add route calls.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_claim_edits.py
import pytest

def test_reviewer_updates_claim(tech, reviewer_client, make_claim):
    claim = make_claim(tech)
    r = reviewer_client.patch(f"/api/claims/{claim.id}", json={
        "claim_number": "AUTH-51", "status": "approved", "warranty_company": "CNA National"})
    assert r.status_code == 200
    assert (r.json()["claim_number"], r.json()["status"], r.json()["warranty_company"]) == ("AUTH-51", "approved", "CNA National")

def test_claim_number_can_be_cleared(tech, reviewer_client, make_claim):
    claim = make_claim(tech, claim_number="AUTH-51")
    assert reviewer_client.patch(f"/api/claims/{claim.id}", json={"claim_number": None}).json()["claim_number"] is None

def test_form_data_replaced_and_validated(tech, reviewer_client, make_claim, claim_payload):
    claim = make_claim(tech)
    form = claim_payload(tech)["form_data"] | {"contract_number": "C-77"}
    assert reviewer_client.patch(f"/api/claims/{claim.id}", json={"form_data": form}).json()["form_data"]["contract_number"] == "C-77"
    assert reviewer_client.patch(f"/api/claims/{claim.id}", json={"form_data": form | {"customer_zip": "1"}}).status_code == 422

@pytest.mark.parametrize("body", [{"vin": "BAD"}, {"warranty_company": ""}, {"customer_last_name": None}])
def test_patch_rejects_invalid_values(tech, reviewer_client, make_claim, body):
    assert reviewer_client.patch(f"/api/claims/{make_claim(tech).id}", json=body).status_code == 422

def test_tech_cannot_edit_after_submission(tech, tech_client, make_claim):
    assert tech_client.patch(f"/api/claims/{make_claim(tech).id}", json={"claim_number": "X"}).status_code == 403
```

```python
# backend/tests/test_photos.py
import io
import zipfile
from datetime import UTC, datetime
import pytest
from app.models import ClaimStatus

NOV_13 = datetime(2026, 11, 13, 15, 0, tzinfo=UTC)

@pytest.fixture
def claim(tech, make_claim, db):
    c = make_claim(tech)              # VIN photo, then damage "Wheel.RF"
    c.created_at = NOV_13
    db.flush()
    return c

def test_list_photos_with_urls_and_export_names(reviewer_client, claim):
    photos = reviewer_client.get(f"/api/claims/{claim.id}/photos").json()
    assert [p["kind"] for p in photos] == ["vin", "damage"]
    assert photos[1]["export_filename"] == "ASSURANT.KP042788.SMITH.Wheel.RF.11.26.jpg"
    assert all("claims/" in p["url"] for p in photos)

def test_reviewer_edits_description_and_excludes(reviewer_client, claim):
    damage = claim.photos[1]
    r = reviewer_client.patch(f"/api/claims/{claim.id}/photos/{damage.id}", json={"description": "Wheel RR", "excluded": True})
    assert (r.json()["description"], r.json()["excluded"], r.json()["export_filename"]) == ("Wheel RR", True, None)

def test_damage_description_cannot_be_blanked(reviewer_client, claim):
    assert reviewer_client.patch(f"/api/claims/{claim.id}/photos/{claim.photos[1].id}", json={"description": " "}).status_code == 422

def test_tech_cannot_edit_photos(tech_client, claim):
    assert tech_client.patch(f"/api/claims/{claim.id}/photos/{claim.photos[1].id}", json={"excluded": True}).status_code == 403

def test_owner_adds_damage_and_missing_mileage(tech, tech_client, claim, put_upload):
    r = tech_client.post(f"/api/claims/{claim.id}/photos", json={"photos": [
        {"key": put_upload(tech), "kind": "damage", "description": "Door.LF"},
        {"key": put_upload(tech), "kind": "mileage"}]})
    assert r.status_code == 201 and {p["kind"] for p in r.json()} == {"damage", "mileage"}
    again = tech_client.post(f"/api/claims/{claim.id}/photos", json={"photos": [{"key": put_upload(tech), "kind": "mileage"}]})
    assert again.status_code == 422

def test_cannot_add_vin_photo(tech, tech_client, claim, put_upload):
    r = tech_client.post(f"/api/claims/{claim.id}/photos", json={"photos": [{"key": put_upload(tech), "kind": "vin"}]})
    assert r.status_code == 422

def test_add_photo_permissions(tech, claim, put_upload, reviewer, reviewer_client, make_user, client_for, db):
    body = lambda u: {"photos": [{"key": put_upload(u), "kind": "damage", "description": "Hood"}]}
    other = make_user(name="Other Tech")
    assert client_for(other).post(f"/api/claims/{claim.id}/photos", json=body(other)).status_code == 404
    assert reviewer_client.post(f"/api/claims/{claim.id}/photos", json=body(reviewer)).status_code == 403
    claim.status = ClaimStatus.closed
    db.flush()
    assert client_for(tech).post(f"/api/claims/{claim.id}/photos", json=body(tech)).status_code == 409

def test_export_zip(tech, tech_client, reviewer_client, claim, put_upload):
    tech_client.post(f"/api/claims/{claim.id}/photos", json={"photos": [
        {"key": put_upload(tech, body=b"second"), "kind": "damage", "description": "wheel.rf"},
        {"key": put_upload(tech, body=b"third"), "kind": "damage", "description": "PDR.LQP"}]})
    pdr = next(p for p in reviewer_client.get(f"/api/claims/{claim.id}/photos").json() if p["description"] == "PDR.LQP")
    reviewer_client.patch(f"/api/claims/{claim.id}/photos/{pdr['id']}", json={"excluded": True})
    r = reviewer_client.get(f"/api/claims/{claim.id}/photos/export")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    assert 'filename="ASSURANT.KP042788.SMITH.11.26.zip"' in r.headers["content-disposition"]
    archive = zipfile.ZipFile(io.BytesIO(r.content))
    assert archive.namelist() == ["ASSURANT.KP042788.SMITH.VIN.11.26.jpg",
                                  "ASSURANT.KP042788.SMITH.Wheel.RF.11.26.jpg",
                                  "ASSURANT.KP042788.SMITH.wheel.rf-2.11.26.jpg"]
    assert archive.read("ASSURANT.KP042788.SMITH.wheel.rf-2.11.26.jpg") == b"second"

def test_export_refused_when_everything_excluded(reviewer_client, claim):
    for p in claim.photos:
        reviewer_client.patch(f"/api/claims/{claim.id}/photos/{p.id}", json={"excluded": True})
    assert reviewer_client.get(f"/api/claims/{claim.id}/photos/export").status_code == 409
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_claim_edits.py tests/test_photos.py -v`
Expected: FAIL with 405 or 404 on the new routes.

- [ ] **Step 3: Implement `ClaimUpdate`, `PhotoOut`, `PhotoAdd`, `PhotoUpdate`, the PATCH route and `app/photos/routes.py` per Interfaces.**

- [ ] **Step 4: Run them to see them pass**

Run: `uv run pytest -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app backend/tests
git commit -m "feat: reviewer edits, added photos and zip export"
```

---

### Task 8: Chat thread and unread markers

**Changed 2026-11-23 (design §8):** the damage description `Hood` in the tests below changes to a label from `DamageLabel`, such as `Wheel LF`.

**Files:**
- Create: `backend/app/conversations.py`, `backend/app/unread.py`.
- Modify: `backend/app/claims/schemas.py` (add `unread: bool` to `ClaimSummary` and `ClaimDetail`), `backend/app/claims/routes.py`, `backend/app/main.py`.
- Test: `backend/tests/test_conversations.py`, `backend/tests/test_unread.py`.

**Interfaces:**
- **Consumes:** `get_visible_claim` (Task 6), `ChatMessage` and `ClaimRead` (Task 2).
- **Produces message schemas:** `MessageIn{contents: str}` (1–4000 characters after stripping) and `MessageOut{id, contents, created_at, sender: UserBrief}`.
- **Produces routes:**
  - `GET /api/claims/{id}/conversations?after_id=0`: `list[MessageOut]` with `id > after_id`, ascending.
  - `POST /api/claims/{id}/conversations`: 201 `MessageOut`. Open to the owning tech and any reviewer; other techs get 404.
  - `POST /api/claims/{id}/read`: 204. Upserts the user's `ClaimRead`, setting `last_message_id` to the claim's newest message id (0 if none) and `last_photo_id` to its newest photo id (0 if none).
- **Produces `unread_claim_ids(db: Session, user: User, claim_ids: Sequence[int]) -> set[int]`:**
  - **For a tech:** the claim has a message with `id > last_message_id` that someone else sent.
  - **For a reviewer:** any of these is true:
    - the reviewer has no `ClaimRead` row for the claim;
    - the claim owner has sent a message with `id > last_message_id`;
    - the claim owner has added a photo with `id > last_photo_id`.
- **List and detail responses** fill in `unread` from `unread_claim_ids`. **Changed 2026-11-24 (design §10):** so do the `POST /claims` and `PATCH /claims/{id}` responses, through one helper shared by all three `ClaimDetail` routes.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_conversations.py
import pytest

def test_tech_and_reviewer_exchange_messages(tech, tech_client, reviewer_client, make_claim):
    claim = make_claim(tech)
    assert tech_client.post(f"/api/claims/{claim.id}/conversations", json={"contents": "RF photos attached"}).status_code == 201
    reviewer_client.post(f"/api/claims/{claim.id}/conversations", json={"contents": "Need a closer shot"})
    thread = tech_client.get(f"/api/claims/{claim.id}/conversations").json()
    assert [(m["sender"]["role"], m["contents"]) for m in thread] == [
        ("tech", "RF photos attached"), ("reviewer", "Need a closer shot")]

def test_after_id_returns_only_newer(tech, tech_client, make_claim):
    claim = make_claim(tech)
    first = tech_client.post(f"/api/claims/{claim.id}/conversations", json={"contents": "one"}).json()
    tech_client.post(f"/api/claims/{claim.id}/conversations", json={"contents": "two"})
    newer = tech_client.get(f"/api/claims/{claim.id}/conversations", params={"after_id": first["id"]}).json()
    assert [m["contents"] for m in newer] == ["two"]

@pytest.mark.parametrize("contents", ["   ", "x" * 4001])
def test_message_length_rules(tech, tech_client, make_claim, contents):
    r = tech_client.post(f"/api/claims/{make_claim(tech).id}/conversations", json={"contents": contents})
    assert r.status_code == 422

def test_other_tech_cannot_read_or_post(tech, make_claim, make_user, client_for):
    claim = make_claim(tech)
    other = client_for(make_user(name="Other Tech"))
    assert other.get(f"/api/claims/{claim.id}/conversations").status_code == 404
    assert other.post(f"/api/claims/{claim.id}/conversations", json={"contents": "hi"}).status_code == 404
```

```python
# backend/tests/test_unread.py
from app.models import Role

def unread(client, claim_id):
    return next(c["unread"] for c in client.get("/api/claims").json()["items"] if c["id"] == claim_id)

def say(client, claim, text="hi"):
    client.post(f"/api/claims/{claim.id}/conversations", json={"contents": text})

def test_new_claim_unread_for_reviewer_until_opened(tech, tech_client, reviewer_client, make_claim):
    claim = make_claim(tech)
    assert unread(reviewer_client, claim.id) is True
    assert unread(tech_client, claim.id) is False
    reviewer_client.post(f"/api/claims/{claim.id}/read")
    assert unread(reviewer_client, claim.id) is False

def test_reviewer_message_marks_unread_for_tech(tech, tech_client, reviewer_client, make_claim):
    claim = make_claim(tech)
    say(tech_client, claim)
    assert unread(tech_client, claim.id) is False
    say(reviewer_client, claim)
    assert unread(tech_client, claim.id) is True
    tech_client.post(f"/api/claims/{claim.id}/read")
    assert unread(tech_client, claim.id) is False

def test_tech_message_or_photo_marks_unread_for_reviewer(tech, tech_client, reviewer_client, make_claim, put_upload):
    claim = make_claim(tech)
    reviewer_client.post(f"/api/claims/{claim.id}/read")
    say(tech_client, claim)
    assert unread(reviewer_client, claim.id) is True
    reviewer_client.post(f"/api/claims/{claim.id}/read")
    tech_client.post(f"/api/claims/{claim.id}/photos", json={"photos": [
        {"key": put_upload(tech), "kind": "damage", "description": "Hood"}]})
    assert unread(reviewer_client, claim.id) is True

def test_reviewer_edits_do_not_mark_unread_for_tech(tech, tech_client, reviewer_client, make_claim):
    claim = make_claim(tech)
    reviewer_client.patch(f"/api/claims/{claim.id}", json={"status": "approved"})
    assert unread(tech_client, claim.id) is False

def test_read_state_is_per_reviewer(tech, reviewer_client, make_user, make_claim, client_for):
    claim = make_claim(tech)
    second = client_for(make_user(role=Role.reviewer, name="Second Reviewer"))
    reviewer_client.post(f"/api/claims/{claim.id}/read")
    assert unread(reviewer_client, claim.id) is False
    assert unread(second, claim.id) is True

def test_claim_detail_carries_unread(tech, reviewer_client, make_claim):
    assert reviewer_client.get(f"/api/claims/{make_claim(tech).id}").json()["unread"] is True
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_conversations.py tests/test_unread.py -v`
Expected: FAIL with 404s, or a `KeyError: 'unread'`.

- [ ] **Step 3: Implement `conversations.py`, `unread.py` and the `unread` field per Interfaces.** Compute unread for a whole list page in one query, not one query per claim.

- [ ] **Step 4: Run them to see them pass**

Run: `uv run pytest -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app backend/tests
git commit -m "feat: per-claim chat thread and unread markers"
```

---

### Task 9: Reviewer email on new claims

**Files:**
- Create: `backend/app/notifications.py`.
- Modify: `backend/app/claims/routes.py` (background task) and `backend/tests/conftest.py` (`outbox` fixture).
- Test: `backend/tests/test_notifications.py`.

**Interfaces:**
- **Consumes:** `upper_segment` (Task 5), `POST /api/claims` (Task 6), `app.state.session_factory` (Task 1).
- **Produces `build_new_claim_email(*, claim: Claim, recipient: str, settings: Settings) -> EmailMessage`:**
  - From `MAIL_FROM`, to the recipient.
  - Subject: `New warranty claim: {upper_segment(last name)} {last 8 of VIN}`.
  - Body lines:
    - `{owner name} submitted a new warranty claim.`
    - `Customer last name: {last name}`
    - `VIN (last 8): {VIN8}`
    - `Open it: {APP_BASE_URL}/claims/{id}`
- **Produces `send_email(message: EmailMessage, settings: Settings) -> None`:** `smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)` used as a context manager. Calls `starttls()` only when `SMTP_STARTTLS`, `login()` only when `SMTP_USERNAME` is set, then `send_message()`.
- **Produces `notify_reviewers_of_new_claim(claim_id: int, session_factory: Callable[[], Session], settings: Settings) -> None`:**
  - Sends one email to each reviewer who has an email address.
  - A failed send is logged with `logger.exception("Failed to send new-claim email for claim %s", claim_id)` and doesn't stop the others.
- **`POST /api/claims`** adds `notify_reviewers_of_new_claim` as a `BackgroundTasks` task, passing `request.app.state.session_factory` and the settings.
- **Produces an autouse fixture `outbox`:** a list that collects sent `EmailMessage`s, by monkeypatching `app.notifications.send_email`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_notifications.py
import smtplib
from email.message import EmailMessage
from app.config import Settings
from app.models import Role
from app.notifications import build_new_claim_email, send_email

def test_submission_emails_reviewers_with_an_email(tech, tech_client, claim_payload, reviewer, make_user, outbox):
    make_user(role=Role.reviewer, name="No Email Reviewer")
    claim_id = tech_client.post("/api/claims", json=claim_payload(tech)).json()["id"]
    assert [m["To"] for m in outbox] == ["kim@example.com"]
    assert outbox[0]["Subject"] == "New warranty claim: SMITH KP042788"
    body = outbox[0].get_content()
    assert f"http://app.test/claims/{claim_id}" in body
    for private in ["6085550134", "100 Main St", "Cary", "27519"]:
        assert private not in body

def test_link_uses_configured_base_url(tech, make_claim):
    claim = make_claim(tech)
    message = build_new_claim_email(claim=claim, recipient="kim@example.com",
                                    settings=Settings(APP_BASE_URL="http://192.168.1.50:5173"))
    assert f"http://192.168.1.50:5173/claims/{claim.id}" in message.get_content()

def test_smtp_failure_does_not_block_submission(tech, tech_client, claim_payload, reviewer, monkeypatch, caplog):
    def fail(message, settings):
        raise OSError("smtp down")
    monkeypatch.setattr("app.notifications.send_email", fail)
    assert tech_client.post("/api/claims", json=claim_payload(tech)).status_code == 201
    assert "Failed to send new-claim email" in caplog.text

def test_send_email_uses_smtp_settings(monkeypatch):
    calls = []
    class FakeSMTP:
        def __init__(self, host, port, timeout): calls.append(("connect", host, port))
        def __enter__(self): return self
        def __exit__(self, *exc): return False
        def starttls(self): calls.append(("starttls",))
        def login(self, user, password): calls.append(("login", user))
        def send_message(self, message): calls.append(("send", message["To"]))
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    message = EmailMessage()
    message["To"] = "kim@example.com"
    send_email(message, Settings(SMTP_HOST="mail.test", SMTP_PORT=1025, SMTP_STARTTLS=False, SMTP_USERNAME=None))
    assert calls == [("connect", "mail.test", 1025), ("send", "kim@example.com")]
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_notifications.py -v`
Expected: an error importing `app.notifications`.

- [ ] **Step 3: Implement `notifications.py`, the background task and the `outbox` fixture per Interfaces.**

- [ ] **Step 4: Run them to see them pass**

Run: `uv run pytest -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app backend/tests
git commit -m "feat: email reviewers when a claim is submitted"
```

---

### Task 10: VIN decode lookup

**Files:**
- Create: `backend/app/vin_decode.py`.
- Modify: `backend/app/main.py`. Include the router, create `app.state.vpic_client = httpx.Client(timeout=5)` and close it on shutdown through a FastAPI `lifespan` (`on_event` is deprecated; owner's call, 2026-11-24).
- Test: `backend/tests/test_vin_decode.py`.

**Interfaces:**
- **Consumes:** `get_current_user` (Task 3), `VIN_PATTERN` (Task 6).
- **Produces `VinDecodeOut{year: int | None, make: str | None, model: str | None}`** and `class VinDecodeError(Exception)`.
- **Produces `decode_vin(vin: str, client: httpx.Client, base_url: str) -> VinDecodeOut`:**
  - Sends `GET {base_url}/vehicles/DecodeVinValues/{vin}?format=json`.
  - Reads `Results[0]["ModelYear" | "Make" | "Model"]`. Blank values become `None`, and a non-numeric year becomes `None`.
  - Raises `VinDecodeError` on an HTTP error status, a transport error or timeout, or a bad body.
  - Logs each failure with `logger.warning("VIN lookup failed (%s)", type(exc).__name__)`: the error type only, so the VIN in vPIC's URL stays out of the logs (owner's call, 2026-11-24).
- **Produces `get_vpic_client(request: Request) -> httpx.Client`.**
- **Produces `GET /api/vin/{vin}/decode`** for any signed-in user:
  - 200 `VinDecodeOut`. An unknown VIN comes back from vPIC with blank fields, so it's 200 with all three null, not 404 (design §8).
  - 422 when the VIN fails `VIN_PATTERN`, lowercase included: the phone's `normalizeVin` cleans it first, so the route doesn't (design §8). No lookup is made.
  - 503 `{"detail": "VIN lookup unavailable"}` on `VinDecodeError`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_vin_decode.py
import httpx
import pytest
from app.vin_decode import get_vpic_client

@pytest.fixture
def vpic(app):
    state = {"requests": [], "handler": None}
    def route(request):
        state["requests"].append(request)
        return state["handler"](request)
    app.dependency_overrides[get_vpic_client] = lambda: httpx.Client(transport=httpx.MockTransport(route))
    return state

def results(**values):
    return httpx.Response(200, json={"Results": [{"ModelYear": "", "Make": "", "Model": "", **values}]})

def timeout(request):
    raise httpx.ReadTimeout("slow", request=request)

def test_decodes_year_make_model(tech_client, vpic):
    vpic["handler"] = lambda r: results(ModelYear="2024", Make="HONDA", Model="Civic")
    assert tech_client.get("/api/vin/1M8GDM9AXKP042788/decode").json() == {"year": 2024, "make": "HONDA", "model": "Civic"}
    sent = vpic["requests"][0]
    assert sent.url.path == "/api/vehicles/DecodeVinValues/1M8GDM9AXKP042788"
    assert sent.url.params["format"] == "json"

def test_blank_values_become_null(tech_client, vpic):
    vpic["handler"] = lambda r: results()
    assert tech_client.get("/api/vin/1M8GDM9AXKP042788/decode").json() == {"year": None, "make": None, "model": None}

@pytest.mark.parametrize("handler", [lambda r: httpx.Response(500), timeout])
def test_upstream_failure_is_503(tech_client, vpic, handler):
    vpic["handler"] = handler
    assert tech_client.get("/api/vin/1M8GDM9AXKP042788/decode").status_code == 503

def test_invalid_vin_rejected_without_lookup(tech_client, vpic):
    assert tech_client.get("/api/vin/ABC/decode").status_code == 422
    assert vpic["requests"] == []

def test_requires_session(client, vpic):
    assert client.get("/api/vin/1M8GDM9AXKP042788/decode").status_code == 401
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_vin_decode.py -v`
Expected: an error importing `app.vin_decode`.

- [ ] **Step 3: Implement `vin_decode.py` per Interfaces.**

- [ ] **Step 4: Run them to see them pass**

Run: `uv run pytest -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app backend/tests
git commit -m "feat: VIN year/make/model lookup through NHTSA vPIC"
```

---

### Task 11: Frontend skeleton, themes, role picker and profile

**Files:**
- Create: `frontend/`, scaffolded by Vite.
- Create or modify:
  - Root files: `frontend/vite.config.ts`, `frontend/components.json` (written by shadcn), `src/index.css`, `src/main.tsx`, `src/App.tsx`.
  - Theme: `src/theme/ThemeProvider.tsx`, `src/components/ThemeToggle.tsx`.
  - Shell: `src/components/NavBar.tsx`, `src/components/TestModeBanner.tsx`.
  - API: `src/api/client.ts`, `src/api/types.ts`.
  - Session: `src/session/useMe.ts`, `src/session/RequireUser.tsx`, `src/session/RolePickerPage.tsx`, `src/session/ProfilePage.tsx`.
  - Test helpers: `src/test/setup.ts`, `src/test/render.tsx`.
- Test: `src/api/client.test.ts`, `src/theme/ThemeProvider.test.tsx`, `src/session/RolePickerPage.test.tsx`, `src/session/RequireUser.test.tsx`, `src/session/ProfilePage.test.tsx`.

**Interfaces:**
- **Consumes:** `/api/session` and `/api/me` (Task 3).
- **Produces in `src/api/client.ts`:**
  - `class ApiError extends Error { constructor(public status: number, public detail: unknown) }`.
  - `apiFetch<T>(path: string, options?: { method?: string; json?: unknown }): Promise<T>`. It sends and receives JSON with `credentials: "same-origin"`. A 204 resolves to `undefined`. Any other non-2xx throws `ApiError` with `detail` taken from the body.
  - Session calls: `createSession(body: { name: string; role: Role; email?: string | null }): Promise<Me>`, `endSession(): Promise<void>`, `getMe(): Promise<Me>`, `updateMe(body: { name?: string; email?: string | null }): Promise<Me>`.
  - Later tasks add their endpoint functions to this file.
- **Produces in `src/api/types.ts`:** `Role = "tech" | "reviewer"` and `Me { id: number; name: string; role: Role; email: string | null }`. Later tasks add types here, in snake_case like the backend.
- **Produces `useMe()`:** a TanStack Query hook with key `["me"]` that never retries after an `ApiError` with status 401.
- **Produces `<RequireUser>`:** renders its children when signed in, and `<Navigate to="/start" replace />` on a 401.
- **Produces `ThemeProvider`, `useTheme(): { theme: "light" | "dark" | "system"; setTheme(t): void }` and `<ThemeToggle>`:**
  - The provider puts the `dark` class on `<html>` when the theme is `"dark"`, or when it's `"system"` and `matchMedia("(prefers-color-scheme: dark)")` matches.
  - The choice persists in `localStorage["warranty.theme"]`. Reading or writing storage that fails must not crash.
  - `<ThemeToggle>` is a shadcn `DropdownMenu` with Light, Dark and System, behind a button labeled "Theme".
- **Produces `<TestModeBanner>`:** a shadcn `Alert` with the exact banner text.
- **Produces `<NavBar>`:** the banner, a "Claims" link, the user's name, a "Profile" link, `ThemeToggle`, and a "Switch role" button that calls `endSession` and navigates to `/start`.
- **Produces routes in `App.tsx`:**
  - `/start` → `RolePickerPage`, which also shows the banner.
  - `/profile` → `ProfilePage`.
  - `/` → `<h1>Claims</h1>` until Task 15 replaces it.
  - Everything except `/start` sits inside `RequireUser` and `NavBar`.
- **Produces in `src/test/render.tsx`:** `renderWithProviders(ui, opts?: { route?: string; path?: string })`. It wraps `ui` in a fresh `QueryClient` (retry off), `ThemeProvider` and `MemoryRouter` at `route` (default `/`). When `path` is given, it renders `ui` at `<Route path={path}>`.
- **Produces `src/test/setup.ts`:**
  - Imports `@testing-library/jest-dom/vitest`.
  - Polyfills `window.matchMedia` (light), `ResizeObserver`, `Element.prototype.hasPointerCapture`, `Element.prototype.releasePointerCapture` and `Element.prototype.scrollIntoView` for menus and popovers.
  - In `afterEach`: `cleanup()`, `vi.clearAllMocks()`, `vi.restoreAllMocks()`, `localStorage.clear()`, and removing the `dark` class from `<html>`.

- [ ] **Step 1: Scaffold the frontend.** From the repo root:
  - `npm create vite@latest frontend -- --template react-ts`
  - `cd frontend`
  - `npm i react-router @tanstack/react-query tesseract.js`
  - `npm i -D vitest jsdom @testing-library/react @testing-library/user-event @testing-library/jest-dom`
  - Follow shadcn/ui's Vite installation guide: Tailwind via `@tailwindcss/vite`, the `@` → `src` alias in `tsconfig` and `vite.config.ts`, then `npx shadcn@latest init`.
  - **Changed 2026-11-24 (design §3):** shadcn now asks which primitives to build on. We use Base UI (`components.json` style `base-vega`), not Radix. Base UI uses a `render` prop where Radix used `asChild`, and menu items take `onClick`, not `onSelect`.
  - `npx shadcn@latest add button input label card badge table textarea select popover command alert dropdown-menu separator radio-group`.
  - In `vite.config.ts`, set `server: { host: true, port: 5173, proxy: { "/api": "http://localhost:8000" } }` and `test: { environment: "jsdom", setupFiles: "./src/test/setup.ts", globals: true }`.
  - Add the script `"test": "vitest run"`.
  - Keep `package-lock.json`. It's committed with the frontend, and Task 17's image installs from it with `npm ci`.

- [ ] **Step 2: Write the failing tests**

```ts
// src/api/client.test.ts
import { apiFetch } from "./client";

test("sends JSON and parses the response", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ id: 1 }), { status: 201, headers: { "Content-Type": "application/json" } }));
  await expect(apiFetch("/api/session", { method: "POST", json: { name: "Tess" } })).resolves.toEqual({ id: 1 });
  const [url, init] = fetchMock.mock.calls[0];
  expect(url).toBe("/api/session");
  expect(init?.body).toBe(JSON.stringify({ name: "Tess" }));
  expect(new Headers(init?.headers).get("Content-Type")).toBe("application/json");
});

test("204 resolves to undefined", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 204 }));
  await expect(apiFetch("/api/session", { method: "DELETE" })).resolves.toBeUndefined();
});

test("errors carry status and detail", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ detail: "Not signed in" }), { status: 401 }));
  await expect(apiFetch("/api/me")).rejects.toMatchObject({ status: 401, detail: "Not signed in" });
});
```

```tsx
// src/theme/ThemeProvider.test.tsx
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeToggle } from "../components/ThemeToggle";
import { renderWithProviders } from "../test/render";

test("dark theme is applied and remembered", async () => {
  renderWithProviders(<ThemeToggle />);
  await userEvent.click(screen.getByRole("button", { name: /theme/i }));
  await userEvent.click(await screen.findByRole("menuitem", { name: /dark/i }));
  expect(document.documentElement).toHaveClass("dark");
  expect(localStorage.getItem("warranty.theme")).toBe("dark");
});

test("system theme follows the device", () => {
  vi.spyOn(window, "matchMedia").mockReturnValue({ matches: true, addEventListener() {}, removeEventListener() {} } as unknown as MediaQueryList);
  renderWithProviders(<ThemeToggle />);
  expect(document.documentElement).toHaveClass("dark");
});
```

```tsx
// src/session/RolePickerPage.test.tsx
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test/render";
import RolePickerPage from "./RolePickerPage";

vi.mock("../api/client", async (orig) => ({ ...(await orig<typeof import("../api/client")>()), createSession: vi.fn() }));
import { createSession } from "../api/client";

const renderPage = () => renderWithProviders(<RolePickerPage />, { route: "/start", path: "/start" });

test("reviewer gives a notification email", async () => {
  vi.mocked(createSession).mockResolvedValue({ id: 1, name: "Kim", role: "reviewer", email: "kim@example.com" });
  renderPage();
  expect(screen.queryByLabelText(/notification email/i)).toBeNull();
  await userEvent.type(screen.getByLabelText(/your name/i), "Kim");
  // Changed 2026-11-24: Base UI gives the label two matches (a hidden input too), so query the radio by role.
  await userEvent.click(screen.getByRole("radio", { name: /reviewer/i }));
  await userEvent.type(screen.getByLabelText(/notification email/i), "kim@example.com");
  await userEvent.click(screen.getByRole("button", { name: /continue/i }));
  expect(createSession).toHaveBeenCalledWith({ name: "Kim", role: "reviewer", email: "kim@example.com" });
});

test("name is required", () => {
  renderPage();
  expect(screen.getByRole("button", { name: /continue/i })).toBeDisabled();
});

test("shows the test-mode banner", () => {
  renderPage();
  expect(screen.getByText("Test mode — don't enter real customer data")).toBeInTheDocument();
});
```

```tsx
// src/session/RequireUser.test.tsx
import { screen } from "@testing-library/react";
import { Route, Routes } from "react-router";
import { renderWithProviders } from "../test/render";
import RequireUser from "./RequireUser";

vi.mock("../api/client", async (orig) => ({ ...(await orig<typeof import("../api/client")>()), getMe: vi.fn() }));
import { ApiError, getMe } from "../api/client";

test("redirects to the role picker when not signed in", async () => {
  vi.mocked(getMe).mockRejectedValue(new ApiError(401, "Not signed in"));
  renderWithProviders(
    <Routes>
      <Route path="/" element={<RequireUser><p>secret</p></RequireUser>} />
      <Route path="/start" element={<p>pick a role</p>} />
    </Routes>);
  expect(await screen.findByText("pick a role")).toBeInTheDocument();
});
```

```tsx
// src/session/ProfilePage.test.tsx
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test/render";
import ProfilePage from "./ProfilePage";

vi.mock("../api/client", async (orig) => ({ ...(await orig<typeof import("../api/client")>()), getMe: vi.fn(), updateMe: vi.fn() }));
import { getMe, updateMe } from "../api/client";

test("reviewer changes their notification email", async () => {
  vi.mocked(getMe).mockResolvedValue({ id: 1, name: "Kim", role: "reviewer", email: "kim@example.com" });
  vi.mocked(updateMe).mockResolvedValue({ id: 1, name: "Kim", role: "reviewer", email: "kim.new@example.com" });
  renderWithProviders(<ProfilePage />);
  const email = await screen.findByLabelText(/notification email/i);
  await userEvent.clear(email);
  await userEvent.type(email, "kim.new@example.com");
  await userEvent.click(screen.getByRole("button", { name: /save/i }));
  expect(updateMe).toHaveBeenCalledWith({ name: "Kim", email: "kim.new@example.com" });
});
```

- [ ] **Step 3: Run them to see them fail**

Run: `npm test`
Expected: failures for the missing modules.

- [ ] **Step 4: Implement everything per Interfaces.**
  - **Role picker:** labels are "Your name", radio buttons "Tech" and "Reviewer", "Notification email" (shown only for Reviewer, optional), and a "Continue" button. On success, set `["me"]` in the query cache and navigate to `/`.
  - **Profile page:** "Name" and "Notification email" (reviewers only), plus a "Save" button.
  - **Decided 2026-11-24 (design §5, §6):**
    - An empty email box sends `null`. A tech's profile sends only the name.
    - A 422 from the role picker or the profile page shows a red `Alert` with the message above the button.
    - "Switch role" calls `endSession`, clears the query cache, then navigates to `/start`.
    - `RequireUser` redirects only on a 401. Any other failure shows "Can't reach the server" with a Retry button.
    - `useMe` never retries any 4xx `ApiError`, not just a 401: the same request gets the same answer (owner's call). A 5xx or a network failure is retried up to 3 times.
    - The role picker starts with no role selected, so "Continue" needs a name and a role.
    - Unknown URLs redirect to `/`.
    - shadcn's "Vega" style (its classic look, with the Inter font).

- [ ] **Step 5: Run them to see them pass**

Run: `npm test`
Expected: all pass.

- [ ] **Step 6: Check it in the browser**
  - Start the backend and run `npm run dev`. Open `http://localhost:5173`: the role picker shows the banner.
  - Pick Tech: you land on "Claims".
  - Switch between Light, Dark and System: the whole page follows.
  - "Switch role" goes back to the picker.

- [ ] **Step 7: Commit**

```bash
git add frontend
git commit -m "feat: frontend shell with shadcn themes, role picker and profile"
```

---

### Task 12: OCR and VIN helpers

**Files:**
- Create: `src/lib/vin.ts`, `src/ocr/extract.ts`, `src/ocr/tesseract.ts`, `scripts/copy-ocr-files.mjs`.
- Modify: `package.json` (the `@tesseract.js-data/eng` dependency and the `predev`/`prebuild` scripts), the root `.gitignore` (`frontend/public/ocr/`).
- Test: `src/lib/vin.test.ts`, `src/ocr/extract.test.ts`.

**Interfaces:**
- **Produces in `src/lib/vin.ts`:**
  - `normalizeVin(raw: string): string`: trims, uppercases and removes spaces.
  - `isValidVin(vin: string): boolean`: `/^[A-HJ-NPR-Z0-9]{17}$/`.
  - `vinCheckDigitValid(vin: string): boolean`: the standard North American check digit at position 9.
    - Letter values: A1 B2 C3 D4 E5 F6 G7 H8 J1 K2 L3 M4 N5 P7 R9 S2 T3 U4 V5 W6 X7 Y8 Z9. Digits are their own value.
    - Weights: 8 7 6 5 4 3 2 10 0 9 8 7 6 5 4 3 2.
    - Take the weighted sum mod 11. A result of 10 means the check digit is `X`.
    - Returns `false`, rather than throwing, for anything that fails `isValidVin` (owner's call, 2026-11-25).
- **Produces in `src/ocr/extract.ts`:** `extractVin(text: string): string | null` and `extractMileage(text: string): number | null`.
- **Produces in `src/ocr/tesseract.ts`:** `recognizeText(image: Blob): Promise<string>`. It creates one `tesseract.js` worker (`createWorker("eng", …)`) on first use and reuses it. No unit test; Task 14 checks it by hand.
  - **The files come from the app, not the CDN** (design §8, owner's decision, 2026-11-25). `workerPath`, `corePath` and `langPath` point under `/ocr/` as absolute URLs, because the worker can't resolve a relative path.
  - If creating the worker fails, it forgets that attempt, so the next call tries again (owner's call, 2026-11-25).
  - **Found while building (2026-11-25):** tesseract.js 7.0.0's `createWorker` never settles when the language data fails to load or initialize; only an engine-load failure rejects. It does call the `errorHandler` option, so `recognizeText` wraps `createWorker` in a `new Promise` that also rejects from `errorHandler` (owner's call, option A). The rejected choice was leaving it, which would leave OCR hung until a reload. A missing `/ocr/` file gets the SPA's `index.html` fallback with a 200, in Vite and in nginx alike, so this is also how a missing file shows up.
- **Produces `scripts/copy-ocr-files.mjs`** (my proposal, accepted by the owner on 2026-11-25), run by the `predev` and `prebuild` npm scripts. It copies into `public/ocr/`:
  - `tesseract.js/dist/worker.min.js`;
  - the three LSTM engine builds, `tesseract.js-core/tesseract-core{,-simd,-relaxedsimd}-lstm.wasm.js`. Tesseract.js uses its LSTM engine by default and picks one build by what the phone supports;
  - `@tesseract.js-data/eng/4.0.0_best_int/eng.traineddata.gz`.

- [ ] **Step 1: Write the failing tests**

```ts
// src/lib/vin.test.ts
import { isValidVin, normalizeVin, vinCheckDigitValid } from "./vin";

test("VIN format", () => {
  expect(isValidVin("1M8GDM9AXKP042788")).toBe(true);
  expect(isValidVin("1M8GDM9AXKP04278")).toBe(false);
  expect(isValidVin("1M8GDM9AXKPO42788")).toBe(false);
  expect(normalizeVin(" 1m8 gdm9axkp042788 ")).toBe("1M8GDM9AXKP042788");
});

test("check digit", () => {
  expect(vinCheckDigitValid("1M8GDM9AXKP042788")).toBe(true);
  expect(vinCheckDigitValid("11111111111111111")).toBe(true);
  expect(vinCheckDigitValid("WVWZZZ1JZXW000001")).toBe(false);
});
```

```ts
// src/ocr/extract.test.ts
import { extractMileage, extractVin } from "./extract";

test.each([
  ["VIN 1M8GDM9AXKP042788", "1M8GDM9AXKP042788"],
  ["vin: 1m8gdm9axkpo42788", "1M8GDM9AXKP042788"],
  ["1M8 GDM9AX KP042788", "1M8GDM9AXKP042788"],
  ["VEHICLEIDNO1M8GDM9AXKP042788", "1M8GDM9AXKP042788"],
  ["MFG 05/24 GVWR 4500\nVIN 1M8GDM9AXKP042788\nMADE IN USA", "1M8GDM9AXKP042788"],
  ["WVWZZZ1JZXW000001", "WVWZZZ1JZXW000001"],
  ["no vin here 12345", null],
  ["1M8GDM9AXKP04278", null],
])("extractVin(%j)", (text, expected) => expect(extractVin(text)).toBe(expected));

test.each([
  ["ODO 1599 mi", 1599],
  ["TRIP A 245.3  ODO 45,210", 45210],
  ["12:45 72F\n45210", 45210],
  ["CALL 6085551234", null],
  ["no digits", null],
])("extractMileage(%j)", (text, expected) => expect(extractMileage(text)).toBe(expected));
```

- [ ] **Step 2: Run them to see them fail**

Run: `npm test -- src/lib src/ocr`
Expected: failures for the missing modules.

- [ ] **Step 3: Implement `vin.ts`, `tesseract.ts` and the copy script, and implement `extract.ts` with these algorithms:**
  - **`extractVin`:**
    1. Uppercase the text and split it into lines. Split each line into tokens on runs of characters outside `A–Z 0–9`. In every token, replace `I→1`, `O→0` and `Q→0`.
    2. Return the first 17-character token with a valid check digit.
    3. Otherwise, on each line, join consecutive tokens, stopping once a join reaches 17 or more characters. A join can start at any token on the line (owner's call, 2026-11-25). Return the first exactly-17-character join with a valid check digit.
    4. Otherwise, return the first 17-character token. Non-North-American VINs have no check digit.
    5. Otherwise, slide a 17-character window across each longer token, and return the first window with a valid check digit.
    6. Otherwise, return `null`.
  - **`extractMileage`:**
    1. Collect matches of `/\d{1,3}(?:,\d{3})+|\d+/g`, remove commas and parse them.
    2. Drop values with more than 7 digits.
    3. Return the largest, or `null` if none are left.

- [ ] **Step 4: Run them to see them pass**

Run: `npm test -- src/lib src/ocr`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat: VIN and mileage extraction from OCR text"
```

---

### Task 13: Intake draft and photo upload pipeline

**Changed 2026-11-23 (design §8, §14):** damage descriptions are a searchable dropdown of `damage_labels`, not a text input, and warranty company suggestions come from `warranty_companies`, filtered on the phone. Both lists come from `GET /api/options`, which replaces `GET /api/warranty-companies`. When this task opens, its interfaces and tests change to match, and description values such as `Wheel.RF` become labels such as `Wheel RF`.

**Files:**
- Create: `src/intake/draft.ts`, `src/intake/useIntakeDraft.ts`, `src/photos/image.ts`, `src/photos/upload.ts`.
- Modify: `src/api/client.ts` (`requestUpload`) and `src/api/types.ts`.
- Test: `src/intake/draft.test.ts`, `src/photos/upload.test.ts`, `src/intake/useIntakeDraft.test.tsx`.

**Interfaces:**
- **Consumes:** `apiFetch` (Task 11) and `POST /api/uploads` (Task 4).
- **Produces in types and client:**
  - `PhotoKind = "vin" | "mileage" | "damage"`.
  - `UploadTicket { key: string; url: string; fields: Record<string, string> }`.
  - `requestUpload(body: { content_type: string; filename: string }): Promise<UploadTicket>`.
- **Produces in `src/photos/upload.ts`:**
  - `ALLOWED_PHOTO_TYPES = ["image/jpeg", "image/png"]` and `class UnsupportedPhotoError extends Error`.
  - `uploadPhoto(file: File): Promise<string>`:
    - Rejects with `UnsupportedPhotoError` before making any request when `file.type` isn't allowed.
    - Otherwise calls `requestUpload`, then POSTs a `FormData` to `ticket.url`: every `ticket.fields` entry in order, then `file` last.
    - Resolves to `ticket.key`, and throws on a non-2xx response.
- **Produces in `src/photos/image.ts`:** `makeThumbnail(file: Blob, maxSize = 200): Promise<string>` (a JPEG data URL at quality 0.7) and `downscaleForOcr(file: Blob, maxSize = 2000): Promise<Blob>`. Both use `createImageBitmap` and a canvas. They aren't unit-tested, because jsdom has no canvas.
- **Produces in `src/intake/draft.ts`:**

  ```ts
  type PhotoStatus = "uploading" | "uploaded" | "failed";
  interface DraftPhoto { localId: string; kind: PhotoKind; status: PhotoStatus; key: string | null;
    description: string; thumbnail: string; originalFilename: string; needsRepick: boolean }
  interface IntakeFields { warranty_company: string; customer_first_name: string; customer_last_name: string;
    customer_phone: string; customer_address: string; customer_city: string; customer_state: string;
    customer_zip: string; vin: string; vehicle_year: string; vehicle_make: string; vehicle_model: string;
    mileage: string; claim_number: string; contract_number: string }
  interface IntakeDraft { version: 1; step: 1 | 2; fields: IntakeFields; photos: DraftPhoto[] }
  ```

  - `emptyDraft(): IntakeDraft` (step 1, every field `""`, no photos).
  - `draftKey(userId: number): string`, which returns `warranty.intakeDraft.v1.user-${userId}`.
  - `loadDraft(userId: number): IntakeDraft | null`:
    - Returns `null` when the draft is missing, unparsable or the wrong version, and removes a bad entry.
    - Photos still `uploading` come back as `failed` with `needsRepick: true`.
  - `saveDraft(userId: number, draft: IntakeDraft): void`: swallows storage errors.
  - `clearDraft(userId: number): void`.
  - `newLocalId(): string`: a counter plus the time plus `Math.random`.
- **Produces `useIntakeDraft(userId: number)`.** It loads the draft on mount, saves it on every change, and keeps picked `File`s in memory by `localId`. It returns:
  - `draft`
  - `setField(name: keyof IntakeFields, value: string)` and `setStep(step: 1 | 2)`
  - `addPhoto(file: File, kind: PhotoKind): Promise<DraftPhoto>`: makes the thumbnail, adds the photo as `uploading`, then marks it `uploaded` with its key or `failed`. A new `vin` or `mileage` photo replaces the existing one of that kind.
  - `retryPhoto(localId: string): Promise<void>`: does nothing when the `File` is gone after a reload, because the UI asks the tech to pick again.
  - `removePhoto(localId: string)`, `setDescription(localId: string, text: string)` and `reset()`.

- [ ] **Step 1: Write the failing tests**

```ts
// src/intake/draft.test.ts
import { clearDraft, draftKey, emptyDraft, loadDraft, saveDraft, type DraftPhoto } from "./draft";

const photo = (over: Partial<DraftPhoto>): DraftPhoto => ({ localId: "a", kind: "damage", status: "uploaded",
  key: "uploads/7/a.jpg", description: "Wheel.RF", thumbnail: "data:a", originalFilename: "a.jpg", needsRepick: false, ...over });

test("round-trips per user", () => {
  const draft = { ...emptyDraft(), step: 2 as const };
  draft.fields.customer_last_name = "Smith";
  saveDraft(7, draft);
  expect(loadDraft(7)).toEqual(draft);
  expect(loadDraft(8)).toBeNull();
  clearDraft(7);
  expect(loadDraft(7)).toBeNull();
});

test("a corrupted draft is discarded", () => {
  localStorage.setItem(draftKey(7), "{not json");
  expect(loadDraft(7)).toBeNull();
  expect(localStorage.getItem(draftKey(7))).toBeNull();
});

test("a photo still uploading when the page reloaded comes back as failed", () => {
  saveDraft(7, { ...emptyDraft(), photos: [photo({}), photo({ localId: "b", status: "uploading", key: null })] });
  const [a, b] = loadDraft(7)!.photos;
  expect(a.status).toBe("uploaded");
  expect(b).toMatchObject({ status: "failed", needsRepick: true, key: null });
});

test("full storage does not throw", () => {
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new DOMException("full", "QuotaExceededError"); });
  expect(() => saveDraft(7, emptyDraft())).not.toThrow();
});
```

```ts
// src/photos/upload.test.ts
import { uploadPhoto, UnsupportedPhotoError } from "./upload";

vi.mock("../api/client", async (orig) => ({ ...(await orig<typeof import("../api/client")>()), requestUpload: vi.fn() }));
import { requestUpload } from "../api/client";

const jpeg = new File(["jpeg"], "IMG_1.jpg", { type: "image/jpeg" });

test("posts the fields, then the file, to the pre-signed URL", async () => {
  vi.mocked(requestUpload).mockResolvedValue({ key: "uploads/7/x.jpg", url: "http://192.168.1.50:9000/warranty-photos",
    fields: { key: "uploads/7/x.jpg", "Content-Type": "image/jpeg", policy: "p" } });
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 204 }));
  await expect(uploadPhoto(jpeg)).resolves.toBe("uploads/7/x.jpg");
  expect(requestUpload).toHaveBeenCalledWith({ content_type: "image/jpeg", filename: "IMG_1.jpg" });
  const [url, init] = fetchMock.mock.calls[0];
  expect(url).toBe("http://192.168.1.50:9000/warranty-photos");
  expect([...(init!.body as FormData).keys()]).toEqual(["key", "Content-Type", "policy", "file"]);
});

test("rejects HEIC before asking for a URL", async () => {
  await expect(uploadPhoto(new File(["x"], "a.heic", { type: "image/heic" }))).rejects.toBeInstanceOf(UnsupportedPhotoError);
  expect(requestUpload).not.toHaveBeenCalled();
});

test("a storage rejection fails the upload", async () => {
  vi.mocked(requestUpload).mockResolvedValue({ key: "k", url: "http://s3", fields: {} });
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("denied", { status: 403 }));
  await expect(uploadPhoto(jpeg)).rejects.toThrow();
});
```

```tsx
// src/intake/useIntakeDraft.test.tsx
import { act, renderHook } from "@testing-library/react";
import { loadDraft } from "./draft";
import { useIntakeDraft } from "./useIntakeDraft";

vi.mock("../photos/upload", () => ({ uploadPhoto: vi.fn() }));
vi.mock("../photos/image", () => ({ makeThumbnail: vi.fn(async () => "data:thumb") }));
import { uploadPhoto } from "../photos/upload";

const jpeg = (name = "a.jpg") => new File(["x"], name, { type: "image/jpeg" });

test("uploads a photo and saves it in the draft", async () => {
  vi.mocked(uploadPhoto).mockResolvedValue("uploads/7/a.jpg");
  const { result } = renderHook(() => useIntakeDraft(7));
  await act(() => result.current.addPhoto(jpeg(), "damage"));
  expect(result.current.draft.photos[0]).toMatchObject({ status: "uploaded", key: "uploads/7/a.jpg", thumbnail: "data:thumb" });
  expect(loadDraft(7)!.photos[0].key).toBe("uploads/7/a.jpg");
});

test("a failed upload can be retried", async () => {
  vi.mocked(uploadPhoto).mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce("uploads/7/a.jpg");
  const { result } = renderHook(() => useIntakeDraft(7));
  await act(() => result.current.addPhoto(jpeg(), "damage"));
  expect(result.current.draft.photos[0].status).toBe("failed");
  await act(() => result.current.retryPhoto(result.current.draft.photos[0].localId));
  expect(result.current.draft.photos[0].status).toBe("uploaded");
});

test("a new VIN photo replaces the old one", async () => {
  vi.mocked(uploadPhoto).mockResolvedValueOnce("uploads/7/1.jpg").mockResolvedValueOnce("uploads/7/2.jpg");
  const { result } = renderHook(() => useIntakeDraft(7));
  await act(() => result.current.addPhoto(jpeg("1.jpg"), "vin"));
  await act(() => result.current.addPhoto(jpeg("2.jpg"), "vin"));
  expect(result.current.draft.photos.filter((p) => p.kind === "vin").map((p) => p.key)).toEqual(["uploads/7/2.jpg"]);
});
```

- [ ] **Step 2: Run them to see them fail**

Run: `npm test -- src/intake src/photos`
Expected: failures for the missing modules.

- [ ] **Step 3: Implement everything per Interfaces.**

- [ ] **Step 4: Run them to see them pass**

Run: `npm test`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat: on-device intake draft and direct photo uploads"
```

---

### Task 14: Intake screens

**Changed 2026-11-23 (design §8, §14):** damage descriptions are a searchable dropdown of `damage_labels`, not a text input, and warranty company suggestions come from `warranty_companies`, filtered on the phone. Both lists come from `GET /api/options`, which replaces `GET /api/warranty-companies`. When this task opens, its interfaces and tests change to match, and description values such as `Wheel.RF` become labels such as `Wheel RF`.

**Files:**
- Create: `src/lib/usStates.ts`, `src/intake/validate.ts`, `src/intake/IntakePage.tsx`, `src/intake/CustomerVehicleStep.tsx`, `src/intake/PhotosStep.tsx`, `src/components/PhotoSlot.tsx`, `src/test/fixtures.ts`.
- Modify: `src/api/client.ts`, `src/api/types.ts`, `src/App.tsx` (route `/intake`, techs only; reviewers are redirected to `/`).
- Test: `src/intake/validate.test.ts`, `src/intake/IntakePage.test.tsx`.

**Interfaces:**
- **Consumes:**
  - `useIntakeDraft`, `saveDraft`, `loadDraft` and `clearDraft` (Task 13).
  - `recognizeText`, `extractVin`, `extractMileage`, `normalizeVin` and `isValidVin` (Task 12).
  - `downscaleForOcr` (Task 13), `useMe` (Task 11).
  - Backend routes `POST /api/claims` (Task 6), `GET /api/vin/{vin}/decode` (Task 10) and `GET /api/warranty-companies` (Task 6).
- **Produces in types and client:**
  - `ClaimStatus = "submitted" | "approved" | "closed"`.
  - `ClaimFormData`, `PhotoRef`, `ClaimCreate`, `UserBrief`, `ClaimDetail`, mirroring the backend schemas.
  - `createClaim(body: ClaimCreate): Promise<ClaimDetail>`.
  - `decodeVin(vin: string): Promise<{ year: number | null; make: string | null; model: string | null }>`.
  - `warrantyCompanySuggestions(q: string): Promise<string[]>`.
- **Produces in `src/lib/usStates.ts`:** `US_STATES: { code: string; name: string }[]` (50 states plus DC) and `toStateCode(input: string): string | null`, which accepts the code or the full name in any case.
- **Produces in `src/intake/validate.ts`:**
  - **`validateStep1(draft: IntakeDraft): Partial<Record<keyof IntakeFields | "vin_photo", string>>`.** Its rules mirror the backend:
    - Required fields are present. A missing one gets the message `Required`.
    - The phone has 10 digits once non-digits are removed, and the ZIP has 5 digits.
    - The year has 4 digits, from 1900 to the current year + 2.
    - `isValidVin(normalizeVin(vin))` holds, and `toStateCode` accepts the state.
    - An uploaded VIN photo exists.
  - **`validateStep2(draft: IntakeDraft): string[]`:**
    - At least one damage photo.
    - Every damage photo is uploaded and has a non-blank description.
    - No photo is uploading or failed.
    - If mileage is typed, it's digits only and at most 2,000,000.
  - **`toClaimCreate(draft: IntakeDraft, timeZone: string): ClaimCreate`:**
    - Phone becomes digits only, state becomes its code, year and mileage become numbers.
    - Blank optional fields become `null`.
    - Every uploaded photo becomes `{ key, kind, description, original_filename }`, where `description` is set only for damage photos (`null` otherwise).
- **Produces `filledDraft(fields?: Partial<IntakeFields>, opts?: { withVinPhoto?: boolean }): IntakeDraft`** in `src/test/fixtures.ts`. It builds a valid step-1 draft:
  - Fields: Assurant; Jane Smith, `(608) 555-0134`, `100 Main St`, Cary, `NC`, `27519`; VIN `1M8GDM9AXKP042788`; 2024 Honda Civic.
  - Photos: an uploaded VIN photo `uploads/7/vin.jpg` (`vin.jpg`) and an uploaded damage photo `uploads/7/d.jpg` (`d.jpg`) described `Wheel.RF`.
- **Produces `IntakePage` at `/intake`.** It's built from shadcn `Card`, `Input`, `Label`, `Button`, `Alert` and `Badge`.
  - **Step 1, "Customer & vehicle":**
    - **Warranty company:** a free-text input suggesting `warrantyCompanySuggestions` results.
    - **Customer:** First name, Last name, Phone (`inputMode="tel"`), Address, City, State, ZIP (`inputMode="numeric"`). State is a searchable shadcn combobox (`Popover` plus `Command`) over `US_STATES`.
    - **Vehicle:**
      - A "VIN photo" slot comes first. On upload, it runs `recognizeText(await downscaleForOcr(file))` and `extractVin`, and fills the VIN field if it's empty.
      - The "VIN" input uses `autoCapitalize="characters"`.
      - When the VIN becomes valid, `decodeVin` fills Year, Make and Model only where they're empty.
      - Then the Year (`inputMode="numeric"`), Make and Model inputs.
    - **Optional:** "Claim number" and "Contract number".
    - **"Next":** shows field errors, or moves to step 2.
  - **Step 2, "Photos":**
    - **Damage photos:** the input accepts several files. Each card shows the thumbnail, a "Description" input (placeholder `e.g. Wheel.RF, PDR.LQP`), its status as a `Badge`, and Retry, "Pick again" (when `needsRepick`) and Remove buttons.
    - **Mileage:** an optional "Mileage photo" slot. OCR plus `extractMileage` fills the "Mileage" input if it's empty.
    - **"Back" and "Submit":**
      - Submit is disabled until `validateStep2` returns nothing.
      - On success: `clearDraft`, invalidate `["claims"]`, navigate to `/claims/{id}`.
      - On an `ApiError`, show its detail in an `Alert`.
  - **`PhotoSlot` file inputs:** `accept="image/jpeg,image/png"`, with no `capture` attribute, so iOS offers both camera and library.
  - **OCR and VIN lookup failures are silent:** fields stay editable, and Next and Submit are never blocked by them.

- [ ] **Step 1: Write the failing tests**

```ts
// src/intake/validate.test.ts
import { filledDraft } from "../test/fixtures";
import { toStateCode } from "../lib/usStates";
import { toClaimCreate, validateStep1, validateStep2 } from "./validate";

test("step 1 rules", () => {
  expect(validateStep1(filledDraft())).toEqual({});
  const bad = filledDraft({ customer_zip: "2751", customer_phone: "608555013", vehicle_year: "26",
                            customer_state: "Carolina", vin: "1M8GDM9AXKPO42788" });
  expect(Object.keys(validateStep1(bad)).sort()).toEqual(
    ["customer_phone", "customer_state", "customer_zip", "vehicle_year", "vin"]);
  expect(validateStep1(filledDraft({}, { withVinPhoto: false }))).toHaveProperty("vin_photo");
});

test("state accepts a code or a name", () => {
  expect(toStateCode("north carolina")).toBe("NC");
  expect(toStateCode("nc")).toBe("NC");
  expect(toStateCode("Carolina")).toBeNull();
});

test("step 2 needs an uploaded, described damage photo", () => {
  const draft = filledDraft();
  expect(validateStep2(draft)).toEqual([]);
  draft.photos[1].description = " ";
  expect(validateStep2(draft)).not.toEqual([]);
});

test("payload mapping", () => {
  const payload = toClaimCreate(filledDraft({ customer_phone: "(608) 555-0134", customer_state: "North Carolina" }), "America/Chicago");
  expect(payload).toMatchObject({ vin: "1M8GDM9AXKP042788", submission_tz: "America/Chicago", claim_number: null,
    form_data: { customer_phone: "6085550134", customer_state: "NC", vehicle_year: 2024, mileage: null, contract_number: null } });
  expect(payload.photos).toEqual([
    { key: "uploads/7/vin.jpg", kind: "vin", description: null, original_filename: "vin.jpg" },
    { key: "uploads/7/d.jpg", kind: "damage", description: "Wheel.RF", original_filename: "d.jpg" }]);
});
```

```tsx
// src/intake/IntakePage.test.tsx
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { filledDraft } from "../test/fixtures";
import { renderWithProviders } from "../test/render";
import { loadDraft, saveDraft } from "./draft";
import IntakePage from "./IntakePage";

vi.mock("../api/client", async (orig) => ({ ...(await orig<typeof import("../api/client")>()),
  getMe: vi.fn(), createClaim: vi.fn(), decodeVin: vi.fn(), warrantyCompanySuggestions: vi.fn(async () => []) }));
vi.mock("../ocr/tesseract", () => ({ recognizeText: vi.fn() }));
vi.mock("../photos/image", () => ({ makeThumbnail: vi.fn(async () => "data:thumb"), downscaleForOcr: vi.fn(async (f: Blob) => f) }));
vi.mock("../photos/upload", async (orig) => ({ ...(await orig<typeof import("../photos/upload")>()), uploadPhoto: vi.fn() }));
import { ApiError, createClaim, decodeVin, getMe } from "../api/client";
import { recognizeText } from "../ocr/tesseract";
import { uploadPhoto } from "../photos/upload";

const jpeg = (name: string) => new File(["x"], name, { type: "image/jpeg" });
function renderIntake() {
  vi.mocked(getMe).mockResolvedValue({ id: 7, name: "Tess", role: "tech", email: null });
  renderWithProviders(
    <Routes>
      <Route path="/intake" element={<IntakePage />} />
      <Route path="/claims/:id" element={<p>claim page</p>} />
    </Routes>, { route: "/intake" });
}

test("VIN photo fills the VIN, then year/make/model, without overwriting typed values", async () => {
  vi.mocked(uploadPhoto).mockResolvedValue("uploads/7/vin.jpg");
  vi.mocked(recognizeText).mockResolvedValue("VIN 1M8GDM9AXKP042788");
  vi.mocked(decodeVin).mockResolvedValue({ year: 2024, make: "HONDA", model: "Civic" });
  renderIntake();
  await userEvent.type(await screen.findByLabelText(/^make/i), "Honda");
  await userEvent.upload(screen.getByLabelText(/vin photo/i), jpeg("vin.jpg"));
  expect(await screen.findByDisplayValue("1M8GDM9AXKP042788")).toBeInTheDocument();
  await waitFor(() => expect(screen.getByLabelText(/^year/i)).toHaveValue("2024"));
  expect(screen.getByLabelText(/^make/i)).toHaveValue("Honda");
  expect(screen.getByLabelText(/^model/i)).toHaveValue("Civic");
});

test("an unreadable VIN photo and a failed lookup leave the fields editable", async () => {
  vi.mocked(uploadPhoto).mockResolvedValue("uploads/7/vin.jpg");
  vi.mocked(recognizeText).mockResolvedValue("glare");
  vi.mocked(decodeVin).mockRejectedValue(new ApiError(503, "VIN lookup unavailable"));
  renderIntake();
  await userEvent.upload(await screen.findByLabelText(/vin photo/i), jpeg("vin.jpg"));
  await userEvent.type(screen.getByLabelText(/^vin$/i), "1M8GDM9AXKP042788");
  await userEvent.type(screen.getByLabelText(/^year/i), "2024");
  expect(screen.getByLabelText(/^year/i)).toHaveValue("2024");
  expect(screen.queryByText(/vin lookup unavailable/i)).toBeNull();
});

test("Next shows errors until step 1 is valid", async () => {
  renderIntake();
  await userEvent.click(await screen.findByRole("button", { name: /next/i }));
  expect(screen.getAllByText(/required/i).length).toBeGreaterThan(0);
  expect(screen.queryByRole("heading", { name: /photos/i })).toBeNull();
});

test("submits the claim and clears the draft", async () => {
  saveDraft(7, { ...filledDraft(), step: 2 });
  vi.mocked(createClaim).mockResolvedValue({ id: 42 } as Awaited<ReturnType<typeof createClaim>>);
  renderIntake();
  await userEvent.click(await screen.findByRole("button", { name: /submit/i }));
  expect(createClaim).toHaveBeenCalledWith(expect.objectContaining({
    vin: "1M8GDM9AXKP042788", submission_tz: Intl.DateTimeFormat().resolvedOptions().timeZone }));
  expect(await screen.findByText("claim page")).toBeInTheDocument();
  expect(loadDraft(7)).toBeNull();
});

test("restores step 2 with photos after a reload", async () => {
  const draft = { ...filledDraft(), step: 2 as const };
  draft.photos.push({ localId: "z", kind: "damage", status: "failed", needsRepick: true, key: null,
                      description: "Hood", thumbnail: "data:z", originalFilename: "z.jpg" });
  saveDraft(7, draft);
  renderIntake();
  expect(await screen.findByDisplayValue("Wheel.RF")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /pick again/i })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /submit/i })).toBeDisabled();
});
```

- [ ] **Step 2: Run them to see them fail**

Run: `npm test -- src/intake`
Expected: failures for the missing modules.

- [ ] **Step 3: Implement everything per Interfaces.**

- [ ] **Step 4: Run them to see them pass**

Run: `npm test`
Expected: all pass.

- [ ] **Step 5: Check it on your iPhone.** Follow the README's "Testing on your iPhone" setup, then:
  - Pick Tech and start a claim.
  - Photograph a VIN label. The VIN, year, make and model should fill in.
  - Reload the page halfway through: everything comes back.
  - Add two damage photos and submit.
  - Confirm the email in Mailpit at `http://localhost:8025`.

- [ ] **Step 6: Commit**

```bash
git add frontend/src
git commit -m "feat: two-step iPhone intake with OCR and VIN prefill"
```

---

### Task 15: Claims list

**Files:**
- Create: `src/review/ClaimsListPage.tsx`.
- Modify: `src/api/client.ts`, `src/api/types.ts`, `src/App.tsx` (`/` renders `ClaimsListPage`).
- Test: `src/review/ClaimsListPage.test.tsx`.

**Interfaces:**
- **Consumes:** `GET /api/claims` (Tasks 6 and 8) and `useMe` (Task 11).
- **Produces in types and client:**
  - `ClaimSummary` (including `unread: boolean`) and `ClaimPage`.
  - `listClaims(params: { q?: string; status?: ClaimStatus; page: number; limit?: number }): Promise<ClaimPage>`.
- **Produces `ClaimsListPage`:**
  - A shadcn `Input` labeled "Search". It's debounced by 300 ms, and a change resets to page 1.
  - A shadcn `Select` labeled "Status" with All, Submitted, Approved and Closed (default All, which sends no `status`).
  - A shadcn `Table` with one row per claim:
    - An unread dot with the accessible name "Unread".
    - Customer name, the last 8 of the VIN, warranty company, status as a `Badge`, claim number or "—", submitted date and tech name.
    - The customer name links to `/claims/{id}`.
  - "Previous" and "Next" buttons with "Page X of Y". The page size is 25.
  - A "New claim" link to `/intake`, for techs only.

- [ ] **Step 1: Write the failing tests**

```tsx
// src/review/ClaimsListPage.test.tsx
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test/render";
import ClaimsListPage from "./ClaimsListPage";

vi.mock("../api/client", async (orig) => ({ ...(await orig<typeof import("../api/client")>()), getMe: vi.fn(), listClaims: vi.fn() }));
import { getMe, listClaims } from "../api/client";

const row = (id: number, over = {}) => ({ id, status: "submitted", created_at: "2026-11-13T15:00:00Z", warranty_company: "Assurant",
  customer_first_name: "Jane", customer_last_name: "Smith", vin: "1M8GDM9AXKP042788", claim_number: null,
  owner: { id: 7, name: "Tess", role: "tech" }, unread: false, ...over });
const asRole = (role: "tech" | "reviewer") => vi.mocked(getMe).mockResolvedValue({ id: 1, name: "X", role, email: null });

test("lists claims with unread markers", async () => {
  asRole("reviewer");
  vi.mocked(listClaims).mockResolvedValue({ items: [row(1, { unread: true }), row(2, { customer_last_name: "Patel" })], total: 2, page: 1, limit: 25 });
  renderWithProviders(<ClaimsListPage />);
  expect(await screen.findAllByText("KP042788")).toHaveLength(2);
  expect(screen.getAllByLabelText("Unread")).toHaveLength(1);
  expect(screen.getByRole("link", { name: /jane smith/i })).toHaveAttribute("href", "/claims/1");
});

test("search and status filter query the API", async () => {
  asRole("reviewer");
  vi.mocked(listClaims).mockResolvedValue({ items: [], total: 0, page: 1, limit: 25 });
  renderWithProviders(<ClaimsListPage />);
  await userEvent.type(await screen.findByLabelText("Search"), "smith");
  await waitFor(() => expect(listClaims).toHaveBeenLastCalledWith(expect.objectContaining({ q: "smith", page: 1 })));
  await userEvent.click(screen.getByRole("combobox", { name: /status/i }));
  await userEvent.click(await screen.findByRole("option", { name: /approved/i }));
  await waitFor(() => expect(listClaims).toHaveBeenLastCalledWith(expect.objectContaining({ status: "approved" })));
});

test("pagination", async () => {
  asRole("reviewer");
  vi.mocked(listClaims).mockResolvedValue({ items: [row(1)], total: 30, page: 1, limit: 25 });
  renderWithProviders(<ClaimsListPage />);
  expect(await screen.findByText("Page 1 of 2")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /next/i }));
  await waitFor(() => expect(listClaims).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 })));
});

test("only techs see New claim", async () => {
  asRole("tech");
  vi.mocked(listClaims).mockResolvedValue({ items: [], total: 0, page: 1, limit: 25 });
  renderWithProviders(<ClaimsListPage />);
  expect(await screen.findByRole("link", { name: /new claim/i })).toHaveAttribute("href", "/intake");
});
```

- [ ] **Step 2: Run them to see them fail**

Run: `npm test -- src/review`
Expected: a failure for the missing module.

- [ ] **Step 3: Implement it per Interfaces.**

- [ ] **Step 4: Run them to see them pass**

Run: `npm test`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat: claims list with search, status filter and unread markers"
```

---

### Task 16: Claim detail, and the end-to-end check

**Changed 2026-11-23 (design §8, §14):** damage descriptions are a searchable dropdown of `damage_labels`, not a text input, and warranty company suggestions come from `warranty_companies`, filtered on the phone. Both lists come from `GET /api/options`, which replaces `GET /api/warranty-companies`. When this task opens, its interfaces and tests change to match, and description values such as `Wheel.RF` become labels such as `Wheel RF`.

**Files:**
- Create: `src/review/ClaimDetailPage.tsx`, `src/review/ClaimFields.tsx`, `src/review/PhotoGallery.tsx`, `src/review/AddPhotos.tsx`, `src/review/ChatThread.tsx`.
- Modify: `src/api/client.ts`, `src/api/types.ts`, `src/App.tsx` (route `/claims/:id`).
- Test: `src/review/ClaimDetailPage.test.tsx`.

**Interfaces:**
- **Consumes:**
  - Backend routes from Tasks 6–8.
  - `uploadPhoto` and `useIntakeDraft`'s photo-card pattern via `PhotoSlot` (Tasks 13–14).
  - `toClaimCreate`'s field rules and `validateStep1` messages (Task 14), reused for the reviewer form.
- **Produces in types:** `ClaimPhoto` (mirrors `PhotoOut`), `Message` (mirrors `MessageOut`) and `ClaimUpdate` (mirrors the backend's `ClaimUpdate`).
- **Produces in the client:**
  - `getClaim(id: number): Promise<ClaimDetail>` and `updateClaim(id: number, body: Partial<ClaimUpdate>): Promise<ClaimDetail>`.
  - `listPhotos(id: number): Promise<ClaimPhoto[]>`, `addPhotos(id: number, photos: PhotoRef[]): Promise<ClaimPhoto[]>` and `updatePhoto(claimId: number, photoId: number, body: { description?: string; excluded?: boolean }): Promise<ClaimPhoto>`.
  - `exportPhotosUrl(id: number): string`, which returns `/api/claims/${id}/photos/export`.
  - `listMessages(id: number, afterId = 0): Promise<Message[]>`, `postMessage(id: number, contents: string): Promise<Message>` and `markRead(id: number): Promise<void>`.
- **Produces `ClaimDetailPage` at `/claims/:id`.** The header shows the customer name, a status `Badge` and the claim number.
  - **`ClaimFields`:**
    - **Reviewers** get a form of shadcn inputs: every field, a "Status" `Select` and a "Save" button. Save sends only the fields that changed. `form_data` is sent whole if any form field changed.
    - **Techs** get a read-only list.
  - **`PhotoGallery`:** "Info photos" (the VIN photo with the VIN, the mileage photo with the mileage) and "Damage photos". For reviewers:
    - each photo has a "Description" input with its own "Save", disabled while a damage description is blank;
    - each photo has an "Exclude from export" / "Include in export" toggle;
    - excluded photos are drawn at reduced opacity with an "Excluded" `Badge`.
  - **"Download all photos" link** to `exportPhotosUrl(id)`, shown to reviewers and the owner.
  - **`AddPhotos`:**
    - Shown only to the owning tech, and only while the claim isn't closed.
    - Has a heading "Add photos". Takes damage photos with descriptions, plus an "Add mileage photo" input when the claim has no mileage photo.
    - Uses `uploadPhoto` and `PhotoSlot`, then sends them with `addPhotos`.
  - **`ChatThread`, with props `{ claimId: number; messages: Message[] }`:**
    - Shows each message with sender name, role and time.
    - A `Textarea` labeled "Message" and a "Send" button. Sending posts, clears the box and invalidates `["claim", id, "messages"]`.
  - **Polling and read state:**
    - The page owns the messages and photos queries, each with `refetchInterval: 10_000`.
    - It calls `markRead(id)` after the first load, and again whenever the newest message id or photo id on screen goes up. Each time, it then invalidates `["claims"]`.

- [ ] **Step 1: Write the failing tests**

```tsx
// src/review/ClaimDetailPage.test.tsx
import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { renderWithProviders } from "../test/render";
import ClaimDetailPage from "./ClaimDetailPage";

vi.mock("../api/client", async (orig) => ({ ...(await orig<typeof import("../api/client")>()),
  getMe: vi.fn(), getClaim: vi.fn(), updateClaim: vi.fn(), listPhotos: vi.fn(), updatePhoto: vi.fn(),
  addPhotos: vi.fn(), listMessages: vi.fn(), postMessage: vi.fn(), markRead: vi.fn(async () => undefined) }));
import * as api from "../api/client";

const claim = { id: 7, status: "submitted", created_at: "2026-11-13T15:00:00Z", updated_at: "2026-11-13T15:00:00Z",
  warranty_company: "Assurant", customer_first_name: "Jane", customer_last_name: "Smith", vin: "1M8GDM9AXKP042788",
  claim_number: null, submission_tz: "America/New_York", unread: false, owner: { id: 3, name: "Tess", role: "tech" },
  form_data: { customer_phone: "6085550134", customer_address: "100 Main St", customer_city: "Cary", customer_state: "NC",
    customer_zip: "27519", vehicle_year: 2024, vehicle_make: "Honda", vehicle_model: "Civic", mileage: null, contract_number: null } };
const photo = (id: number, over = {}) => ({ id, kind: "damage", description: "Wheel.RF", excluded: false, original_filename: "a.jpg",
  added_by: { id: 3, name: "Tess", role: "tech" }, created_at: "2026-11-13T15:00:00Z", url: `http://s3/p${id}.jpg`,
  export_filename: "ASSURANT.KP042788.SMITH.Wheel.RF.11.26.jpg", ...over });
const message = (id: number, contents: string) => ({ id, contents, created_at: "2026-11-13T15:00:00Z", sender: { id: 1, name: "Kim", role: "reviewer" } });

function renderDetail(me: { id: number; role: "tech" | "reviewer" }, over = {},
                      photos = [photo(10, { kind: "vin", description: null }), photo(11)]) {
  vi.mocked(api.getMe).mockResolvedValue({ ...me, name: "X", email: null });
  vi.mocked(api.getClaim).mockResolvedValue({ ...claim, ...over } as never);
  vi.mocked(api.listPhotos).mockResolvedValue(photos as never);
  vi.mocked(api.listMessages).mockResolvedValue([]);
  renderWithProviders(<Routes><Route path="/claims/:id" element={<ClaimDetailPage />} /></Routes>, { route: "/claims/7" });
}

test("reviewer updates status and claim number", async () => {
  vi.mocked(api.updateClaim).mockResolvedValue(claim as never);
  renderDetail({ id: 1, role: "reviewer" });
  await userEvent.click(await screen.findByRole("combobox", { name: /status/i }));
  await userEvent.click(await screen.findByRole("option", { name: /approved/i }));
  await userEvent.type(screen.getByLabelText(/claim number/i), "AUTH-51");
  await userEvent.click(screen.getByRole("button", { name: /^save$/i }));
  expect(api.updateClaim).toHaveBeenCalledWith(7, { status: "approved", claim_number: "AUTH-51" });
});

test("tech sees the claim read-only", async () => {
  renderDetail({ id: 3, role: "tech" });
  expect(await screen.findByText("Cary")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /^save$/i })).toBeNull();
  expect(screen.queryByRole("button", { name: /exclude from export/i })).toBeNull();
});

test("reviewer excludes a photo; blank damage descriptions can't be saved", async () => {
  vi.mocked(api.updatePhoto).mockResolvedValue(photo(11, { excluded: true }) as never);
  renderDetail({ id: 1, role: "reviewer" });
  await userEvent.click((await screen.findAllByRole("button", { name: /exclude from export/i }))[1]);
  expect(api.updatePhoto).toHaveBeenCalledWith(7, 11, { excluded: true });
  await userEvent.clear(screen.getByDisplayValue("Wheel.RF"));
  expect(screen.getByRole("button", { name: /save description/i })).toBeDisabled();
});

test("download link points at the export", async () => {
  renderDetail({ id: 1, role: "reviewer" });
  expect(await screen.findByRole("link", { name: /download all photos/i })).toHaveAttribute("href", "/api/claims/7/photos/export");
});

test("owner can add photos to an open claim, including a missing mileage photo", async () => {
  renderDetail({ id: 3, role: "tech" });
  expect(await screen.findByRole("heading", { name: /add photos/i })).toBeInTheDocument();
  expect(screen.getByLabelText(/add mileage photo/i)).toBeInTheDocument();
});

test("no adding photos once the claim is closed", async () => {
  renderDetail({ id: 3, role: "tech" }, { status: "closed" });
  expect(await screen.findByText("Cary")).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: /add photos/i })).toBeNull();
});

test("no mileage option when the claim already has a mileage photo", async () => {
  renderDetail({ id: 3, role: "tech" }, {}, [photo(10, { kind: "vin", description: null }), photo(12, { kind: "mileage", description: null })]);
  expect(await screen.findByRole("heading", { name: /add photos/i })).toBeInTheDocument();
  expect(screen.queryByLabelText(/add mileage photo/i)).toBeNull();
});

test("marks read on open and when a polled message arrives", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  renderDetail({ id: 1, role: "reviewer" });
  await waitFor(() => expect(api.markRead).toHaveBeenCalledTimes(1));
  vi.mocked(api.listMessages).mockResolvedValue([message(5, "Need a closer shot")]);
  await act(() => vi.advanceTimersByTimeAsync(10_000));
  expect(await screen.findByText("Need a closer shot")).toBeInTheDocument();
  await waitFor(() => expect(api.markRead).toHaveBeenCalledTimes(2));
  vi.useRealTimers();
});

test("sending a message clears the box", async () => {
  vi.mocked(api.postMessage).mockResolvedValue(message(6, "On it") as never);
  renderDetail({ id: 3, role: "tech" });
  await userEvent.type(await screen.findByLabelText("Message"), "On it");
  await userEvent.click(screen.getByRole("button", { name: /send/i }));
  expect(api.postMessage).toHaveBeenCalledWith(7, "On it");
  expect(screen.getByLabelText("Message")).toHaveValue("");
});
```

- [ ] **Step 2: Run them to see them fail**

Run: `npm test -- src/review`
Expected: failures for the missing modules.

- [ ] **Step 3: Implement everything per Interfaces.**

- [ ] **Step 4: Run the whole suite and the build**

Run: `cd backend && uv run pytest -v`, then `cd ../frontend && npm test && npm run build`
Expected: every test passes, and the build finishes without TypeScript errors.

- [ ] **Step 5: End-to-end check on the laptop and iPhone.** Use the README's iPhone setup, in both light and dark themes:
  1. On the laptop, pick Reviewer: name Kim, email `kim@example.com`. On the iPhone, pick Tech.
  2. On the phone, file a claim:
     - Take the VIN photo and check the prefill.
     - Add two damage photos both described `Wheel.RF`, plus a mileage photo.
     - Reload once mid-way, then submit.
  3. In Mailpit, check the email: subject `New warranty claim: <LASTNAME> <VIN8>`, and the link opens the claim on the laptop.
  4. On the laptop:
     - The claim is unread in the list, and opening it clears that.
     - Set Approved and a claim number, and exclude one photo.
     - Download all photos: the zip and file names follow the convention, the second photo is named `…Wheel.RF-2…`, and the excluded photo is missing.
  5. Chat both ways. The tech's list shows unread after Kim replies, and Kim's list shows unread after the tech replies or adds a photo.
  6. Close the claim: the tech can no longer add photos.

- [ ] **Step 6: Commit**

```bash
git add frontend/src
git commit -m "feat: claim detail with reviewer edits, photo export and chat"
```

---

### Task 17: Production containers

Carries out design §17's production shape: an nginx `frontend` container and a `backend` container, run locally under the Compose `app` profile. Hosting and HTTPS stay in the deployment plan.

**Files:**
- Create: `backend/Dockerfile`, `backend/.dockerignore`, `backend/docker-entrypoint.sh`, `frontend/Dockerfile`, `frontend/.dockerignore`, `frontend/nginx.conf`.
- Modify: `docker-compose.yml`, `.env.example` (adds `LAN_IP`), `README.md`, `CLAUDE.md` (Commands).
- Test: the verification steps below. No automated tests: everything this task adds is configuration, and the app behavior behind it is already tested.

**Interfaces:**
- **Consumes:** `Settings` and the production checks (Task 1), the migrations (Task 2), `python -m app.setup_bucket` (Task 4), `GET /api/health` (Task 1), the export route `GET /api/claims/{id}/photos/export` (Task 7), and `npm run build` (Task 11).
- **Backend image (`backend/Dockerfile`):**
  - Base `python:3.14-slim`. Copy the `uv` binary from `ghcr.io/astral-sh/uv:<version>`, pinned to the laptop's `uv --version`.
  - Workdir `/app`. Install with `uv sync --frozen --no-dev` (copy `pyproject.toml` and `uv.lock` first so dependency layers cache), then copy `app/`, `alembic/`, `alembic.ini` and `docker-entrypoint.sh`.
  - `ENV PATH="/app/.venv/bin:$PATH"`. Run as a non-root user. `EXPOSE 8000`.
  - `.dockerignore`: `.env`, `.venv`, `tests`, `__pycache__`, `.pytest_cache`.
- **`docker-entrypoint.sh`:** `set -e`, then `alembic upgrade head`, then `exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips="*" --workers 1`. Trusting every forwarder is safe only because the container publishes no port.
- **Frontend image (`frontend/Dockerfile`):**
  - Build stage `node:22-alpine`: `npm ci`, then `npm run build`.
  - Final stage `nginx:<stable>-alpine`, with the tag pinned at build time. It holds only `dist/` (to `/usr/share/nginx/html`) and `nginx.conf` (to `/etc/nginx/conf.d/default.conf`).
  - `.dockerignore`: `node_modules`, `dist`, `coverage`.
- **`nginx.conf`:** one `server` listening on plain HTTP port 80.
  - `location /api/`: `proxy_pass http://backend:8000;`, with `Host $host`, `X-Forwarded-For $proxy_add_x_forwarded_for` and `X-Forwarded-Proto $scheme`, plus `proxy_read_timeout 300s`.
  - `location ~ ^/api/claims/\d+/photos/export$`: the same proxy settings plus `proxy_buffering off;`, so the zip streams.
  - `location /assets/`: `Cache-Control: public, max-age=31536000, immutable`. Vite gives these files content-hashed names.
  - `location = /index.html`: `Cache-Control: no-cache`.
  - `location /`: `try_files $uri /index.html;`, so client routes like `/claims/7` load the app.
- **`docker-compose.yml`:** existing services are unchanged. These are added, all with `profiles: ["app"]`:
  - `setup-bucket`: the backend image, with `entrypoint: ["python", "-m", "app.setup_bucket"]`; depends on `seaweedfs`.
  - `backend`: builds `./backend`, with **no `ports`**. Depends on `postgres` (`service_healthy`) and `setup-bucket` (`service_completed_successfully`).
  - `frontend`: builds `./frontend`, `ports: ["8080:80"]`, depends on `backend`.
  - Environment for `backend` and `setup-bucket`:
    - `APP_ENV=development`, because this runs over plain HTTP with dev credentials.
    - `DATABASE_URL=postgresql+psycopg://warranty:warranty@postgres:5432/warranty` and `SMTP_HOST=mailpit`.
    - `APP_BASE_URL=http://${LAN_IP:?set LAN_IP in .env}:8080` and `ALLOWED_ORIGINS=["http://${LAN_IP}:8080"]`.
    - `S3_ENDPOINT_URL=http://${LAN_IP}:9000`.
  - **Why the LAN IP:** the browser and the backend container must use the same S3 address, because the address is part of a pre-signed URL's signature. `seaweedfs:8333` only works inside Docker, and `localhost` means something different inside the container. The laptop's LAN IP works from both, and from the iPhone.

- [ ] **Step 1: Write both Dockerfiles, both `.dockerignore` files, the entrypoint and `nginx.conf` per Interfaces.**

- [ ] **Step 2: Add the `app` profile to `docker-compose.yml`, and `LAN_IP=` (with a comment) to the root `.env.example`.**

- [ ] **Step 3: Build and start it**

Run: stop any dev `uvicorn` and `npm run dev`, set `LAN_IP` in the root `.env`, then `docker compose --profile app up --build -d`
Expected: `setup-bucket` exits 0, and `backend` and `frontend` are running (`docker compose --profile app ps`).

- [ ] **Step 4: Check nginx's routing and caching**

Run each against `http://<LAN-IP>:8080`:
- `curl -s .../api/health` → `{"status":"ok"}`.
- `curl -sI .../claims/7` → `200` with `Content-Type: text/html`.
- `curl -sI .../index.html` → `Cache-Control: no-cache`.
- `curl -sI .../assets/<any built file>` → `Cache-Control: public, max-age=31536000, immutable`.
- `docker compose --profile app port backend 8000` → an error or empty output: the backend has no host port.

- [ ] **Step 5: Check the backend refuses unsafe production settings**

Run: `docker compose --profile app run --rm -e APP_ENV=production backend`
Expected: exits non-zero before migrating, with an error naming `SESSION_COOKIE_SECURE`, `APP_BASE_URL`, `ALLOWED_ORIGINS`, the S3 keys and `DATABASE_URL`.

- [ ] **Step 6: Short end-to-end run through the containers.** Allow port 8080 through the firewall. Then:
  1. On the iPhone, open `http://<LAN-IP>:8080`, pick Tech and file a claim with a few photos.
  2. On the laptop, at the same address, pick Reviewer.
  3. Open the claim from the Mailpit link: the link uses port 8080.
  4. Download all photos: the zip arrives complete and named per the convention.
  5. Run `docker compose --profile app down`, then `up -d` again: the claim and photos are still there, and migrations rerun as a no-op.

- [ ] **Step 7: Update the docs**
  - **`README.md`:** a "Running the production containers locally" section covering `LAN_IP`, the up/down commands, port 8080, and that only nginx is exposed.
  - **`CLAUDE.md` Commands:** add `docker compose --profile app up --build` as the production-like run.

- [ ] **Step 8: Commit**

```bash
git add backend/Dockerfile backend/.dockerignore backend/docker-entrypoint.sh frontend/Dockerfile frontend/.dockerignore frontend/nginx.conf docker-compose.yml .env.example README.md CLAUDE.md
git commit -m "chore: production containers with nginx in front of the backend"
```

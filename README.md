# Warranty Claims

Techs file warranty claims (customer and vehicle details plus photos) from an iPhone. A reviewer edits each claim, chats with the tech about it, and exports its photos named in the warranty company's convention.

v1 runs in **test mode** on a laptop: anonymous sessions and made-up data only. Never enter real customer data.

- Design: `docs/superpowers/specs/2026-11-19-warranty-claims-design.md`
- Plan: `docs/superpowers/plans/2026-11-19-warranty-claims-v1.md`

## Dev setup

You need Docker and [`uv`](https://docs.astral.sh/uv/). `uv` installs Python 3.14 for the backend by itself. The system `python3` isn't used.

1. **Start the dev services** from the repo root:

   ```sh
   docker compose up -d
   ```

   - **Postgres 18** on `localhost:5432`, with databases `warranty` (dev) and `warranty_test` (tests). Nothing else on the laptop may be using port 5432.
   - **SeaweedFS**, S3-compatible photo storage, on port 9000. Its access keys are in `docker/seaweedfs/s3.json`.
   - **Mailpit**, which catches all outgoing email. Read it at http://localhost:8025.

2. **Set up the backend** in `backend/`:

   ```sh
   uv sync                                          # creates .venv with Python 3.14 and all dependencies
   uv run python -m app.setup_bucket                # creates the photo bucket, its upload expiry and CORS
   uv run uvicorn app.main:app --reload --port 8000
   ```

   Run `app.setup_bucket` once, and again whenever `ALLOWED_ORIGINS` changes. It's safe to run repeatedly.

   The defaults in `app/config.py` work for local development. To change a setting, copy `.env.example` to `backend/.env` and edit it.

3. **Run the backend tests** in `backend/`:

   ```sh
   uv run pytest
   ```

4. **Start the frontend** in `frontend/` with `npm run dev` (from Task 11). It serves the app at http://localhost:5173 and forwards `/api` to the backend.

## Testing on your iPhone

The phone reaches the laptop over Wi-Fi, so every address it uses must be the laptop's LAN IP, not `localhost`.

1. Find the laptop's LAN IP: `ipconfig getifaddr en0` on macOS.
2. In `backend/.env`, set:

   ```sh
   APP_BASE_URL=http://<LAN-IP>:5173
   ALLOWED_ORIGINS=["http://<LAN-IP>:5173","http://localhost:5173"]
   S3_ENDPOINT_URL=http://<LAN-IP>:9000
   ```

3. Allow incoming connections on ports 5173 (the app) and 9000 (photo storage) through the laptop's firewall.
4. Restart the backend. Then, on the phone, open `http://<LAN-IP>:5173`.

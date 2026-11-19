# Warranty Claims App

Techs file warranty claims (customer and vehicle details plus photos) from an iPhone. A reviewer (Kim) edits each claim, chats with the tech about it, and exports its photos named in the warranty company's convention. v1 runs in test mode on the owner's laptop.

- Design (approved): `docs/superpowers/specs/2026-11-19-warranty-claims-design.md`
- Implementation plan: `docs/superpowers/plans/2026-11-19-warranty-claims-v1.md`
- Original wireframe: `warranty_wireframe_v2.excalidraw`

## Working rules

- **The owner makes all major design decisions**: architecture, data model, API shape, UX flow and security. Bring options, their tradeoffs and one recommendation, then wait for the owner's call. Don't prototype or silently pick defaults for these. Label your own smaller calls as proposals.
- Record decisions in the design doc before planning or building.
- **No real customer data anywhere.** Use made-up names, `example.com` emails and the sample VIN `1M8GDM9AXKP042788`.
- **Never commit PDFs.** Sample invoices contain real customer details. `.gitignore` excludes `*.pdf`.
- Keep customer phone numbers and addresses out of emails and logs.

## How we build

The owner wants to understand every part of the codebase and review all code before it goes out. So the build goes one plan task at a time, and this section overrides the "continuous execution, don't pause" rule in the superpowers execution skills.

- **The owner starts each task.** Open it with a few lines on what it builds, which design decisions it carries out, and anything the plan leaves open.
- **Build it test-first, as the plan says**, on the `v1` branch, never `main`. Leave it uncommitted, so `git diff` shows exactly this task.
- **Then stop and review it with the owner**, at the depth the plan's "Build order and review depth" table gives. Show the test results, answer questions, and make changes until the owner approves.
- **Commit only after the owner approves**, one commit per task. **Push only when the owner says so** (the repo is public).
- **If the owner says "I'll write this one"**, coach instead of coding: point to the files, interfaces and tests, and then review what they write.
- **If a task needs something the plan or design doc doesn't settle**, stop and ask.

## Stack

- **`backend/`:** FastAPI, SQLAlchemy, Alembic, Postgres.
- **`frontend/`:** React, Vite, TypeScript, shadcn/ui, with light and dark themes.
- **Photos:** S3-compatible storage (MinIO locally).
- **Email:** Mailpit locally.
- **Dev services:** `docker compose up -d`.

## Commands

These work once the plan's Tasks 1 and 11 have landed:

- Backend tests: `cd backend && python -m pytest`
- Frontend tests: `cd frontend && npm test`
- Run locally: `uvicorn app.main:app --reload --port 8000` in `backend/`, and `npm run dev` in `frontend/`. Testing from the iPhone is covered in `README.md`.

# Warranty Claims App — Design

**Date:** 2026-11-19
**Status:** Approved by the owner on 2026-11-19. Amended 2026-11-19 with deployment readiness (§17), approved by the owner.
**Source:** `warranty_wireframe_v2.excalidraw` (repo root), plus decisions made in conversation on 2026-11-19.

**How to read this:** unmarked statements are the owner's decisions. **[Proposal]** marks Claude's calls, which the owner can overrule while reviewing.

---

## 1. Why

Today, techs email photos and claim information to the reviewer, Kim. She renames the photos and organizes them by hand.

The app replaces that:
- Techs file each claim, with its photos, from their iPhone.
- Kim gets every claim in one place, talks to the tech on the claim, tracks its status, and exports the photos already named in the warranty company's convention.

## 2. Goals, non-goals, anti-goals

**Who v1 is for:** the owner, developing on a personal laptop with their own iPhone on the same Wi-Fi, building toward a demo for Kim. After the demo and any changes, the next step is deploying for a pilot with Kim and techs. That deployment is a separate plan.

**Goals (v1)**
- A tech files a complete claim from an iPhone in one sitting, without losing work if Safari reloads the page.
- Year, make and model are prefilled from the VIN.
- A reviewer sees every claim and can:
  - edit it and set its status;
  - chat with the tech about it;
  - export its photos, named per the convention, in one step.
- Reviewers are emailed when a new claim comes in. In v1 that email lands in a local mail catcher.
- Techs and reviewers see at a glance which claims have unread activity.

**Non-goals (v1)**
- **Real customer data.** v1 runs in test mode with anonymous sessions.
- **Planned for after the demo:** hosting, HTTPS and a real email service.
- **Not planned yet:** Entra ID sign-in, monitoring, and anything involving invoices.
- **Not building:** real-time chat, email to techs on replies (the unread marker covers it), deleting photos, and shrinking photos before upload.

**Anti-goals [Proposal]** These would make v1 a failure even if it otherwise works:
- A tech loses an in-progress claim.
- Real customer data is entered while anonymous mode is on.
- Exported photos carry wrong or inconsistent names.
- A tech can see another tech's claims.

## 3. Constraints

- Intake happens on iPhone Safari. Review happens on a laptop, possibly on mobile later.
- **Frontend:** React + Vite + TypeScript, tested with Vitest + React Testing Library.
- **UI:** shadcn/ui components (on Tailwind CSS) for a clean, modern look, with light and dark themes. **[Proposal]** The theme follows the device's setting by default, and a toggle in the nav bar overrides it and is remembered on that device.
- **Backend:** FastAPI + Uvicorn + SQLAlchemy + Pydantic, tested with pytest.
- **Database:** PostgreSQL, with jsonb for flexible form data.
- **Photo storage:**
  - S3-compatible object storage. Hosting is undecided (maybe DigitalOcean or Vultr), so nothing AWS-specific.
  - The bucket is private; uploads and downloads go through pre-signed URLs.
  - Photos are stored as untouched originals: full resolution, with the photo's original date/time information.
- **OCR:** Tesseract.js in a browser Web Worker. It only prefills fields.
- **VIN decoding:** NHTSA's free vPIC service. It only prefills fields.
- **Local development:** the owner's personal laptop, which has Node and Docker. **[Proposal]** Docker Compose runs Postgres, an S3-compatible store and a local mail catcher. The store is SeaweedFS (owner's decision, 2026-11-19): MinIO's official Docker images were withdrawn, and SeaweedFS passed a check of pre-signed POST limits, the `uploads/` expiry rule, server-side copy, download filenames and CORS.
- **Phone access in v1:** the iPhone reaches the laptop over local Wi-Fi. The app, the API and the pre-signed upload/download URLs must use an address the phone can reach, not `localhost`.
- No real customer data until Entra ID sign-in replaces anonymous sessions.

## 4. Approaches considered

| Decision | Options weighed | Chosen, and why |
|---|---|---|
| Claim storage | All jsonb / hybrid / all columns | **Hybrid.** A field gets its own column if the app *does something* with it: search, filter, filenames, email. Display-only fields live in a jsonb `form_data`, so form changes don't need migrations. |
| Keeping intake safe on iPhone | A: draft on device, upload everything at submit / B: upload each photo as it's picked, keep a small draft on device / C: server-side draft claim | **B.** A reload re-uploads nothing, and submit is one small request. Cost: orphaned photos from abandoned drafts, which a bucket cleanup rule removes. A was rejected because iOS can clear large browser storage and the upload fails at the worst moment. C adds draft states, cleanup, and drafts leaking into queries. |
| Sign-in for v1 | Email + password / Entra ID now / anonymous persistent session | **Anonymous session** while data is fake. It avoids building a credential flow Entra will replace anyway. It's built so Entra replaces only the step that creates a user. |
| Chat delivery | Polling / server-sent events / WebSockets | **Polling** while a claim page is open. Chat doesn't need to be real-time. |
| Frontend | React / Jinja + HTMX / Vue | **React + Vite + TypeScript.** It suits the photo-heavy intake, the OCR worker, direct uploads and draft recovery. |
| Reviewer notification | Email / SMS / in-app only | **Email.** |
| Warranty company names | Free text with suggestions / list in a settings file / list reviewers manage | **Free text that suggests names used before.** Revisit after talking with Kim. |
| Bad photos after submission | Nothing / reviewer excludes from export / reviewer deletes | **Exclude from export**, reversibly. Deleting can come later; the exclude flag already marks the photos involved. |
| Photo size | Untouched originals / shrink on the phone | **Originals.** See how upload speed holds up. |
| Runtime versions | Postgres 16 and Python 3.12 / the newest releases (Postgres 18, Python 3.15) / the newest our dependencies fully support | **Postgres 18 and Python 3.14** (owner's decision, 2026-11-19). Postgres 19 isn't released. Python 3.15 is a month old and uvicorn's compiled extras don't ship for it yet. Whether the chosen host offers managed Postgres 18 gets checked in the deployment plan. |
| Production serving | A: one container, FastAPI serves the built frontend and `/api` / B: nginx container serves the built frontend and reverse-proxies `/api` to a separate backend container / C: frontend and API on separate domains | **B.** The owner has run this setup before. It mirrors the dev setup, where Vite proxies `/api`. C was ruled out because it breaks the same-origin session cookie and Origin check. See §17. |
| Claim lifecycle | No status / reviewer-set status | **Reviewer-set status.** |
| Time zone for the export month | One company time zone / tech's time zone | **The tech's time zone** at submission. |

## 5. Roles and access

- **First visit:** a role picker asks for a name and a role (tech or reviewer). Reviewers also enter a notification email, which they can change later.
- **Tech:**
  - Creates claims and sees only their own.
  - After submitting, can **add new photos**: damage photos (with descriptions), plus a mileage photo if the claim doesn't have one yet. Cannot change any existing field, photo or description.
  - **[Proposal]** Can't add photos once a claim is Closed. Chat stays open.
  - Chats on their own claims.
- **Reviewer:**
  - Sees all claims.
  - After submission, can:
    - edit every claim field, including photo descriptions;
    - set the claim's status;
    - exclude a photo from export, or include it again.
  - Chats, exports, and gets an email for each new claim.
- Anyone can pick any role. That's acceptable only because the data is fake.

## 6. Sessions (test mode) and the path to Entra ID

- The session cookie is the identity. The server sets it as HttpOnly. Safari caps cookies set by JavaScript at 7 days, so it must not be a JavaScript cookie.
- **[Proposal]** The cookie lasts about one year and renews on each visit. Expiry would delete a tech's identity.
- If a tech clears Safari data or switches phones, they lose their identity and their "my claims" list. Their claims stay visible to reviewers.
- **[Proposal]** A "Test mode — don't enter real customer data" banner shows whenever anonymous mode is on.
- **When Entra ID arrives:**
  - The users table already carries a role and an empty external-ID column for the Entra user ID.
  - Sessions and the single "who is the current user?" check every route uses stay as they are.
  - Only the step that creates a user changes.
  - How long Entra sessions last will be decided with IT.

## 7. Claim contents

**Required to submit**
- **Customer:** first name, last name, phone (10-digit US), address, city, state (searchable dropdown), ZIP (5 digits).
- **Vehicle:** year (4 digits), make, model.
- **VIN [Proposal]:** the VIN value is required, following from "VIN photo required"; the VIN appears in every export filename and in the reviewer email. Rule: 17 characters, letters and digits except I, O and Q.
- **Warranty company:** free text, suggesting names already used on earlier claims.
- **Photos:**
  - A VIN photo.
  - At least one damage photo. **Every damage photo needs a description.**

**Optional**
- Claim number and contract number. The reviewer usually adds these later.
- Mileage value and mileage photo.

**Set by the app**
- **Status:** Submitted, Approved or Closed. A new claim starts as Submitted.
  - **[Proposal]** Reviewers can set any status at any time, including reopening a claim.
  - **[Proposal]** Status is independent of the claim number; entering a claim number doesn't change it.
- **Submission time and the tech's time zone.** The browser supplies the time zone.

**Where each field lives [Proposal]**
- **Columns:** customer first name, customer last name, VIN, warranty company, claim number, status, submission time zone.
- **`form_data` (jsonb):** phone, address, city, state, ZIP, year, make, model, mileage, contract number.

## 8. Intake (iPhone)

This follows the wireframe's two intake phases.

1. **Free response:**
   - Customer fields and the warranty company.
   - The vehicle section starts with the VIN photo and the VIN field, so the VIN lookup can fill year, make and model on the same screen. This moves the VIN photo up from the wireframe's photo phase.
   - Optional claim number and contract number.
2. **Photos:**
   - Damage photos, each with a required free-text description, as the wireframe specifies (e.g. `Wheel.RF`, `PDR.LQP`).
   - The optional mileage photo with the mileage field.

**Behavior**
- **Uploads:**
  - Each original photo uploads straight to storage through a pre-signed URL as soon as it's picked.
  - **[Proposal]** Each photo shows uploading, done or failed status, with a retry.
- **Draft:**
  - The draft lives on the device: text fields, references to uploaded photos, descriptions and small thumbnails.
  - It's restored after a reload and cleared after a successful submit.
- **OCR:**
  - VIN and mileage photos go through Tesseract.js in a Web Worker, and the results prefill the VIN and mileage fields.
  - The fields stay editable, and an OCR failure never blocks the tech.
- **VIN decoding:**
  - When a valid VIN is entered or read by OCR, the app looks up year, make and model through NHTSA vPIC and fills them in. They stay editable.
  - If the lookup fails, the fields stay blank for the tech to fill.
  - **[Proposal]** The lookup goes through the backend with a short timeout. It fills only fields that are still empty, so it never overwrites what the tech typed.
- **Submit:** one small request that references the uploaded photos, after which reviewers are emailed.

## 9. Review (laptop)

The screens follow the wireframe's Review layout.

- **Claims list:**
  - Search matches customer name, VIN and claim number.
  - A status filter.
  - Pagination, and an unread marker per claim.
- **Claim detail:**
  - Claim details and status, editable by reviewers.
  - Info photos: the VIN photo with the VIN, and the mileage photo with the mileage.
  - Damage photos with descriptions, editable by reviewers.
  - A per-photo "exclude from export" toggle; excluded photos are shown greyed out.
  - The chat thread.
  - An export button.
- **Techs** see their own claims on the same screens, read-only, plus "add photos" (unless Closed) and chat.

## 10. Chat and unread markers

- There is one thread per claim, between the submitting tech and reviewers. The open claim page polls for new activity.
- **For techs:** a claim is unread when a reviewer has posted a message since the tech last opened it. Only new messages count; reviewer edits and status changes don't.
- **For reviewers:** a claim is unread when, since that reviewer last opened it, the tech has either posted a message or added photos. A claim a reviewer has never opened is unread for that reviewer.
- **[Proposal]** Read state is tracked per reviewer, so Kim reading a claim doesn't clear it for another reviewer.
- **[Proposal]** Photos added after submission don't email reviewers; the unread marker is enough.

## 11. Reviewer email

- Each new claim emails every reviewer who has set an email address.
- **Content:** last 8 of the VIN, the customer's last name, and a link to the claim.
- **[Proposal]** A send failure is logged and never blocks the tech's submission.
- **In v1,** mail goes to the local mail catcher.
- **For the pilot deployment,** check with IT before relying on company mail. Microsoft has been retiring password-based SMTP for Exchange Online, so this may need Microsoft Graph or a transactional provider.

## 12. Photo export

- **[Proposal]** A claim's photos download together as one zip file. Excluded photos are left out.
- **Filename:** `{WARRANTY COMPANY}.{last 8 of VIN}.{CUSTOMER LAST NAME}.{photo description}.{MM}.{YY}.{ext}`
  - MM and YY are the submission month and year, in the tech's time zone at submission.
  - Example with made-up values: `ASSURANT.KP042788.SMITH.Wheel.RF.11.26.jpg`.
- **Cleanup:**
  - Warranty company and last name are uppercased, with spaces, accents and apostrophes removed: "de la Cruz" → `DELACRUZ`, "Muñoz" → `MUNOZ`, "O'Brien" → `OBRIEN`.
  - Spaces in descriptions become dots: "Wheel RF" → `Wheel.RF`.
  - Repeated descriptions get `-2`, `-3`.
- **[Proposal]** VIN and mileage photos use `VIN` and `Mileage` as their description.
- **[Proposal]** Reviewers can change a damage photo's description but can't blank it, so every filename has one.
- The date part, and possibly the whole pattern, may change. Whether each warranty company has its own pattern is pending the owner's follow-up with Kim.
  - **[Proposal]** Until then, one pattern lives in one function that takes the date and the parts as inputs. A change is a small code edit with tests.

## 13. Data sketch [Proposal]

- **User:** name, role (tech/reviewer), notification email (reviewers), external ID (empty until Entra), created time.
- **Session:** user, hashed token, created and expiry times.
- **Claim:**
  - Owner (the tech who submitted it), submission time and submission time zone.
  - Status.
  - The column fields from §7, `form_data` jsonb, and updated time.
- **Photo:**
  - Claim and kind (VIN / mileage / damage).
  - Storage key, description, original filename, and an excluded-from-export flag.
  - Who added it and when, which separates intake photos from later additions and drives reviewer unread markers.
- **Chat message:** claim, sender, contents, time.
- **Claim read state:** user, claim, last-read time.
- **Warranty company suggestions:** the distinct names already used on claims. No separate table.

## 14. API changes from the wireframe [Proposal]

- All routes live under `/api`, served from the same origin as the frontend.
- `POST /claims` takes references to photos already uploaded, instead of the photos themselves.
- `GET /claims` changes:
  - It replaces `customer` with a general search `q` over customer name, VIN and claim number.
  - It adds a status filter.
  - Each claim carries an unread flag.
- `PATCH /claims/{id}` (reviewer) also sets status.
- **Added:**
  - Create an anonymous user (role picker); get and update the current user (name, email).
  - Get a pre-signed upload URL.
  - Add photos to a submitted claim (owning tech, not when Closed).
  - Edit a photo (reviewer): description, excluded flag.
  - Export photos as a zip.
  - Read a claim's chat thread (`GET /claims/{id}/conversations`).
  - Mark a claim read.
  - Look up year, make and model for a VIN.
  - List warranty company suggestions.

## 15. Deferred and next

- **Next plan, after the demo to Kim:** deploy for a pilot with Kim and techs. That means hosting (DigitalOcean or Vultr), HTTPS and a real email service (check with IT). v1 prepares for it (§17), so that plan is mostly choosing a host and setting configuration.
- **Entra ID sign-in.** It must land before any real data. Session length gets decided with IT at that point.
- **Pending Kim:**
  - Whether warranty companies need their own filename patterns.
  - Whether company names should come from a managed list.
- **Reviewer photo deletion.** Straightforward to add later: excluded photos are already flagged. Delete adds removing the stored file and deciding who may do it.
- Monitoring, invoices, email to techs on replies, shrinking photos before upload.

## 16. Left to the builder

- Libraries within the chosen stack: routing, data fetching, test helpers.
- Layout details beyond the wireframe.
- Polling interval, page size, photo size and type limits, and the status filter's default.
- Migration tooling, and exact route names and payload shapes, consistent with §14.

## 17. Deployment readiness

v1 still runs only on the laptop (§2). This section makes sure the code it produces can later be deployed by choosing a host and setting configuration, without restructuring. Hosting, HTTPS and the email provider stay in the next plan.

**Production shape (owner's decision: option B in §4)**
- Two app containers, plus the database and object storage:
  - **`frontend`:** nginx serving the built frontend (`npm run build` output). Any path that isn't a file falls back to `index.html` so client-side routes work. `/api/` is reverse-proxied to the backend. It's the only container the outside world reaches.
  - **`backend`:** FastAPI under uvicorn. It's reachable only from nginx, on the internal network, never published on a host port.
- Photos never pass through nginx: they upload and download straight to object storage through pre-signed URLs. The photo zip export does pass through nginx.
- Development is unchanged: Vite's dev server with its `/api` proxy, plus `uvicorn --reload`.

**[Proposal] Details of the production shape**
- **Images are built in multiple stages.** The frontend image is Node for the build, then `nginx:alpine` with only the built files and `nginx.conf`. The backend image is `python:3.14-slim` installing from the lockfile.
- **The images don't handle HTTPS.** nginx listens on plain HTTP inside the container. HTTPS is added in front by the deployment plan, either with certbot on the host or with the host's load balancer. The images stay the same either way.
- **nginx settings:** a longer read timeout on `/api/` for large zip exports, response buffering off for the export so the zip streams, and long-lived caching only on Vite's content-hashed `assets/` files, never on `index.html`.
- **Proxy headers:** uvicorn runs with `--proxy-headers`, trusting forwarded headers. That's safe because only nginx can reach the backend.
- **One uvicorn worker.** Reviewer email runs as an in-process background task (§11), which is fine for a single instance at pilot scale.
- **Migrations run before the server starts,** in the backend container's entrypoint (`alembic upgrade head`, then uvicorn). That's safe with one instance. Running several instances would need a separate migration step.
- **A Compose profile runs the production setup locally.** `docker compose --profile app up --build` builds and runs both app containers against the local Postgres, SeaweedFS and Mailpit, so the production setup is exercised before any host is involved. The plain `docker compose up -d` still starts only the dev services.

**[Proposal] Configuration that is safe in production**
- **An `APP_ENV` setting,** `development` by default or `production`.
- **When `APP_ENV=production`, the backend refuses to start** if any of these is true:
  - `SESSION_COOKIE_SECURE` is false;
  - `APP_BASE_URL` or any entry in `ALLOWED_ORIGINS` isn't `https://`;
  - the S3 keys or the database password are still the development defaults (`dev-access-key` / `dev-secret-key`, `warranty`).

  A missing variable fails loudly instead of quietly using dev values.
- `.env.example` documents every setting and marks the ones production must set.

**[Proposal] Bucket setup in code**
- **A backend command, `python -m app.setup_bucket`,** makes the bucket match what the app needs:
  - creates it if it's missing;
  - applies the 7-day expiry on `uploads/`;
  - applies a CORS rule allowing `ALLOWED_ORIGINS` to POST uploads and GET downloads.
- It's safe to run repeatedly. Dev runs it against SeaweedFS, and the deployment plan runs it once against DigitalOcean Spaces or Vultr.
- If a store doesn't support per-bucket CORS rules, the command logs that and carries on.

**[Proposal] Reproducible builds**
- **The backend uses `uv`,** with dependencies in `pyproject.toml` and exact versions locked in a committed `uv.lock`. The Docker image installs from that lock.
  - `uv` is already on the laptop, and it fetches the right Python itself. The laptop's default `python3` is 3.9, so the plan's `python -m venv` would have built a venv on an unsupported Python.
  - Dev commands become `uv sync` and `uv run pytest`.
- **The frontend's `package-lock.json` is committed,** and the image installs with `npm ci`.

**[Proposal] Migrations are what the tests run against**
- The test database is built with `alembic upgrade head`, not `create_all`, so a broken migration fails the tests instead of failing the deploy.
- A test checks that the migrations and the models match (Alembic's autogenerate comparison finds no differences).

**[Proposal] Health checks**
- `GET /api/health` also checks the database connection. It returns 503 if the database is unreachable, so a host or load balancer can tell when the app is down.

**Not in v1 (deployment plan)**
- Choosing the host, setting up HTTPS and the domain, the production email provider, backups, and monitoring.
- Entra ID sign-in, which must land before the pilot takes real claims (§6).

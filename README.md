# VeriDoc AI

VeriDoc AI is a web MVP for checking certificate images. A user uploads a JPG
or PNG; the FastAPI backend stores the image in MongoDB, extracts text with
Tesseract OCR, classifies the filename with a deterministic stub, and records
the verification and audit event in PostgreSQL. Authentic stub results also
receive a QR code that links to the local frontend result route.

## Project overview

- **Backend:** Python, FastAPI, SQLAlchemy, PostgreSQL, MongoDB
- **OCR:** Tesseract OCR through `pytesseract`
- **Frontend:** React, TypeScript, Vite, Axios, React Router
- **QR codes:** Python `qrcode`; authentic results only
- **Upload validation:** JPG/JPEG or PNG, maximum 5 MB

The verification URL is currently local-only:
`http://localhost:5173/verify/{verification_id}`.

## Prerequisites

- Windows 10/11 with PowerShell (the commands below use Windows paths)
- Python 3.10 or later
- Node.js 20.19 or later, or 22.12 or later, and npm
- PostgreSQL 16 and MongoDB 7, installed locally or run with Docker Desktop
- Tesseract OCR installed at
  `C:\Program Files\Tesseract-OCR\tesseract.exe`

The backend currently configures that Windows Tesseract executable path in
`app/routers/verify.py`. If Tesseract is installed elsewhere, update
`pytesseract.pytesseract.tesseract_cmd` in that file to the executable's path.

## Setup on Windows

Run commands from the repository root, `C:\Users\user\Desktop\veridoc`, unless
the command changes directory.

### 1. Start PostgreSQL and MongoDB

Start Docker Desktop and wait for its engine to be ready. For a fresh Docker
setup, create the database containers:

```powershell
docker run -d --name veridoc-postgres `
  -e POSTGRES_USER=veridoc `
  -e POSTGRES_PASSWORD=change-me `
  -e POSTGRES_DB=veridoc `
  -p 5432:5432 `
  postgres:16

docker run -d --name veridoc-mongo -p 27017:27017 mongo:7
```

On later starts, use the existing containers instead of running `docker run`
again:

```powershell
docker start veridoc-postgres
docker start veridoc-mongo
```

Confirm both containers are running:

```powershell
docker ps
Test-NetConnection localhost -Port 5432
Test-NetConnection localhost -Port 27017
```

If PostgreSQL and MongoDB are installed directly rather than in Docker, start
those services and configure the connection URLs in `.env` accordingly.

### 2. Configure and install the backend

Create and activate a virtual environment:

```powershell
py -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

Create `.env` from the example and edit it:

```powershell
Copy-Item .env.example .env
notepad .env
```

Use the following local database settings:

```env
DATABASE_URL=postgresql+psycopg://veridoc:change-me@localhost:5432/veridoc
MONGODB_URL=mongodb://localhost:27017
MONGODB_DATABASE=veridoc
```

Replace `SECRET_KEY` with a generated secret. Generate one with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copy the printed value into `.env` as `SECRET_KEY=...`; do not commit `.env`.
The other JWT settings can retain their example values for local development.

Install the backend dependencies:

```powershell
python -m pip install -r requirements.txt
```

Install Tesseract OCR separately from Python packages. Confirm the configured
executable exists and runs:

```powershell
& 'C:\Program Files\Tesseract-OCR\tesseract.exe' --version
```

SQLAlchemy creates the PostgreSQL tables when the API starts.

### 3. Install and start the frontend

The Vite React + TypeScript frontend is already scaffolded in `frontend`.
Install its dependencies:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
```

The frontend `.env` should contain:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Start the frontend development server:

```powershell
npm run dev
```

Open the printed local URL, normally `http://localhost:5173`.

## Run both servers

Keep the backend and frontend running in separate PowerShell terminals.

**Terminal 1 — backend, from the repository root:**

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --reload-dir app
```

The API is available at `http://127.0.0.1:8000`; Swagger UI is at
`http://127.0.0.1:8000/docs`. The backend allows browser requests from
`http://localhost:5173`.

**Terminal 2 — frontend, from the repository root:**

```powershell
cd frontend
npm run dev
```

Open `http://localhost:5173`, select a JPG or PNG no larger than 5 MB, and
choose **Verify certificate**. On a successful authentic result, the result
page displays the QR code. The backend accepts optional `user_id` and
`certificate_id` form fields; when they are omitted, it creates linked test
records.

For a quick API check in PowerShell, use `curl.exe` and preserve the MIME type:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/verify" `
  -F "file=@C:\path\to\certificate.png;type=image/png"
```

The classifier returns `fraudulent` when the uploaded filename contains
`fake`; otherwise it returns `authentic`. A fake result does not have a QR
code. The QR URL is a local frontend route and is not a public verification
website.

## Classifier status and future CNN integration

The current classifier is intentionally a stub, not a trained authenticity
model. In `app/routers/verify.py`, `classify_image(filename)` checks whether
the filename contains `fake` and returns a fixed result and confidence score.
These scores must not be treated as a real certificate-authenticity assessment.

To integrate a real CNN later:

1. Replace `classify_image` with an inference function that accepts the
   validated image bytes (or a decoded image) rather than the filename.
2. Apply the same preprocessing, resizing, and normalization used to train the
   model.
3. Load the trained model once at application startup, not once per request.
4. Map its class probabilities to the existing `VerificationResult` enum and
   return the selected result and confidence score.
5. Add model tests and keep model weights outside version control.

The rest of the verification endpoint can continue to persist the returned
result and confidence score in PostgreSQL.

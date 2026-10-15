# Employee Dashboard (FastAPI + MongoDB)

A small full-stack app: a FastAPI REST backend with a single-page dashboard to add, search, edit and delete employees, with live status and department counts.

## Project structure

    app/main.py        FastAPI backend (API + serves the dashboard)
    app/index.html     Frontend dashboard (plain HTML, CSS, JS)
    requirements.txt   Python dependencies
    .env.example       Template for environment variables
    REVIEW.md          Review of the provided starter code
    DECISIONS.md       Design decisions and trade-offs

## Run locally (Ubuntu)

    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env        # then put your MongoDB Atlas connection string in .env
    uvicorn app.main:app --reload

Open http://127.0.0.1:8000 for the dashboard and http://127.0.0.1:8000/docs for the interactive API docs.

If `MONGODB_URI` is missing or the connection fails, the app still starts using temporary in-memory storage (data is lost on restart). The badge at the top right of the dashboard, and `GET /api/health`, show which storage is active.

## MongoDB Atlas checklist

1. Create a database user (Database Access) and copy its password.
2. Allow your IP address (Network Access).
3. Copy the connection string into `.env` as `MONGODB_URI`. URL-encode special characters in the password.
4. Restart the server and check that the badge says "Connected to MongoDB".

## API

    GET    /api/health
    GET    /api/employees?q=&department=&status=&skip=&limit=
    POST   /api/employees
    GET    /api/employees/{id}
    PUT    /api/employees/{id}
    DELETE /api/employees/{id}
    GET    /api/stats

Employee fields: name, email (unique), department, role, status (active | on_leave | inactive).

## Quick API test

    curl -X POST http://127.0.0.1:8000/api/employees \
      -H "Content-Type: application/json" \
      -d '{"name":"Asha Rao","email":"asha@example.com","department":"Engineering","role":"Developer"}'
    curl http://127.0.0.1:8000/api/employees
    curl http://127.0.0.1:8000/api/stats

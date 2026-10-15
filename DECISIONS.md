# Design decisions

1. **FastAPI + Pydantic validation.** Input is validated on the server (lengths, email format, allowed status values), so bad data is rejected with clear 422/409 errors regardless of what the frontend does.
2. **Storage behind one interface, with an in-memory fallback.** `MongoStore` and `MemoryStore` expose the same methods. The app starts even when MongoDB is unreachable and says so in `/api/health` and in the dashboard badge, instead of crashing. Trade-off: fallback data is not persistent.
3. **Unique email enforced by the database.** A unique index on `email` prevents duplicates even under concurrent requests; the API maps it to HTTP 409.
4. **Secrets in environment variables.** The connection string lives in `.env` (git-ignored); `.env.example` documents it. Nothing sensitive is committed.
5. **Synchronous pymongo.** The data volume is small and the code is simpler to read and debug than an async driver. FastAPI runs these sync handlers in a thread pool. Switching to Motor would be the next step for heavy traffic.
6. **Server-side search, filter and pagination.** The list endpoint accepts `q`, `department`, `status`, `skip`, `limit` (max 200) so the dashboard does not need to download everything. Search text is regex-escaped to avoid regex injection.
7. **Frontend in a single dependency-free HTML file.** No build step, so it is easy to run and review. It is served by FastAPI at `/`, so there are no CORS problems in normal use.
8. **XSS-safe rendering.** The dashboard builds rows with `textContent`, never `innerHTML`, so employee data can't inject scripts.
9. **Accessibility basics.** Labelled inputs, visible focus, native `<dialog>`, dark mode and reduced-motion support.
10. **Not included (time):** authentication, automated tests, and rate limiting. These would be the next priorities.

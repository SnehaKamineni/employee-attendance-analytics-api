# Review of the provided starter code

> TODO: I wrote this template without access to the starter code, so the findings below must be checked against the actual files from SDT_candidate_kit.zip. Replace each placeholder with the real file name, line and issue you find. Delete any item that does not apply.

## How to use this template
For every issue, write: **where** (file and line), **what is wrong**, **why it matters**, and **how I fixed it**.

## Categories to check in the starter code

### Security
- Hard-coded secrets or connection strings in the source
- Missing input validation or unescaped user input (injection, XSS)
- Overly open CORS settings or missing authentication

### Correctness
- Wrong HTTP status codes or missing 404 / 409 handling
- Invalid ObjectId handling (a bad id causing a 500 error)
- Missing unique constraints (duplicate records)

### Reliability
- No error handling around database calls
- Database connection created on every request, or never closed
- No timeout when the database is unreachable

### Performance
- Fetching all documents with no pagination or filtering
- Missing indexes on searched fields

### Maintainability
- Everything in one file, no separation of storage and API logic
- Missing README, requirements, or `.env.example`
- No tests

## Findings

| # | File / line | Issue | Impact | Fix |
|---|-------------|-------|--------|-----|
| 1 | TODO | TODO | TODO | TODO |
| 2 | TODO | TODO | TODO | TODO |
| 3 | TODO | TODO | TODO | TODO |

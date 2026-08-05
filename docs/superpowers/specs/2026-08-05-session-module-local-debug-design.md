# Session Module Local Debug Design

## Goal

Run and verify the current `session_module.py` locally before replacing its in-memory repository with PostgreSQL. The immediate goal is a reliable, repeatable API smoke test; production persistence is a separate follow-up phase.

## Scope

The first phase covers:

- Repairing encoding damage and syntax errors in the existing module.
- Keeping `InMemorySessionRepository` unchanged as the first runtime backend.
- Starting the FastAPI application locally with Uvicorn.
- Verifying session creation, bearer-token authentication, preference saving, answer saving, restoration, invalid-token rejection, expiry rejection, and data clearing.
- Keeping the PostgreSQL target documented as `127.0.0.1:5433/free_time_agent` for phase two.

The first phase does not add PostgreSQL persistence, user accounts, background jobs, email delivery, or deployment infrastructure.

## Runtime Flow

1. `POST /api/v1/sessions` creates a session and returns `session_id`, a bearer token, stage, version, and expiry time.
2. The client sends `Authorization: Bearer <token>` on protected requests.
3. The service looks up the session, checks expiry, hashes the supplied token, and compares it with the stored hash.
4. Preferences move the session to the questionnaire stage.
5. Answers are validated as integers from 1 through 4 and stored by question ID.
6. Restore returns the current draft state.
7. Clear removes draft data and returns the stage to interests.

## Acceptance Checks

- The module imports and the FastAPI app starts without syntax or import errors.
- OpenAPI documentation is available at `/docs`.
- A newly created session can be restored with its returned token.
- Invalid or missing bearer tokens return HTTP 401.
- Invalid answer values return HTTP 422 at the request validation boundary or HTTP 400 in service-level validation.
- Preferences and answers are reflected by the restore endpoint.
- Clearing data removes preferences, answers, profile, and plan and resets the stage.
- The test run does not modify unrelated files or delete existing user data.

## Phase Two: PostgreSQL Migration

After phase one passes, introduce a repository interface with both in-memory and PostgreSQL implementations. The PostgreSQL implementation will use the local instance on port 5433, store only token hashes, persist timestamps in UTC, and be selected through environment configuration rather than code changes.

## Known Constraints

- The current file contains garbled Chinese literals and at least one malformed string, so syntax repair is required before execution.
- The current in-memory implementation loses data when the process exits; this is acceptable only for the first debugging phase.
- The local PostgreSQL instance is running on port 5433 because port 5432 could not be bound.

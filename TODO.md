# Production and CI TODOs

These tasks address issues identified during review of PR #2 and the related
PostgreSQL CI changes in PR #6.

## 1. Fix global JWT authentication configuration

**Priority:** High  
**Source:** PR #2

PR #2 registers `RoleMiddleware` globally with:

```python
app.add_middleware(RoleMiddleware, audience="your-audience")
```

Every request passes through this middleware, and JWT validation compares the
token audience against that literal placeholder. In production, tokens issued
for the real API or client audience may be rejected with HTTP 401, making
authenticated endpoints unusable.

### Required work

- Load the expected JWT audience from required environment/configuration.
- Validate the configuration during application startup.
- Fail clearly if the audience is missing or invalid.
- Do not log JWT contents or other sensitive token data.
- Add tests for:
  - A token with the configured audience being accepted.
  - A token with a mismatched audience being rejected.
- Document the required value for local development, CI, and production.

## 2. Enforce authentication for protected routes

**Priority:** Critical  
**Source:** PR #2

When no `Authorization` header is provided, the middleware assigns the
`student` role:

```python
request.state.user_role = "student"
```

Because the middleware is installed globally, unauthenticated callers can
reach the `/query` endpoint and any other route that trusts
`request.state.user_role`. This is an authentication bypass, not just a test
problem.

### Required work

- Return HTTP 401 when credentials are missing.
- Require the `Bearer` authentication scheme.
- Validate the JWT signature, audience, and issuer where applicable.
- Require an allowed role before forwarding the request.
- Remove permissive student fallbacks from endpoint handlers.
- Add tests for:
  - Missing credentials.
  - Malformed authorization schemes.
  - Expired tokens.
  - Invalid signatures.
  - Tokens without a role.
  - Unsupported roles.
  - Valid student and professor tokens.

## 3. Preserve role propagation for `/resource_query`

**Priority:** High  
**Source:** PR #2

PR #2 makes `SemanticRouter.process_query()` role-aware, but the existing
`/resource_query` handler still calls it without passing the role from
`request.state`. Calls to this existing endpoint can therefore return a
role-required error instead of query results.

The router also catches exceptions and returns an error-shaped dictionary,
which can make the failure appear as HTTP 200 unless the error contract is
corrected.

### Required work

- Decide whether `/resource_query` remains supported.
- If it remains supported:
  - Pass the authenticated middleware role explicitly.
  - Preserve the endpoint's intended success response.
  - Return appropriate HTTP error statuses instead of successful
    `{"error": ...}` responses.
  - Add regression tests for student and professor requests.
- If `/query` replaces it:
  - Deprecate or redirect `/resource_query` deliberately.
  - Document the replacement.
  - Add a test confirming the intended compatibility behavior.

## 4. Repair role-routing authentication tests

**Priority:** High  
**Source:** PR #2

The role-routing tests send an authorization value that is not a valid Bearer
header. The middleware rejects the request before the mocked `jwt.decode`
function is reached, so the tests do not actually exercise role routing.

### Required work

- Use a syntactically valid header such as:

  ```text
  Authorization: Bearer test-token
  ```

- Mock JWT decoding at the exact import path used by the middleware.
- Isolate external services, LLM calls, and router dependencies so tests are
  deterministic.
- Assert that:
  - Student requests can access only student routes.
  - Professor requests can access only professor routes.
  - Missing tokens return 401.
  - Malformed schemes return the documented 400 or 401 status.
  - Invalid tokens return 401.
  - Tokens without roles return 403.
  - Unsupported roles cannot access protected routes.

## 5. Stabilize the PostgreSQL CI test setup

**Priority:** High  
**Source:** PR #6

The CI workflow starts a fresh PostgreSQL service and runs
`src/databases/postgres/crud_test.py`, but that test module:

- Opens a database connection at import time.
- Executes `main()` unconditionally.
- Assumes user ID `4` already exists.
- Indexes `result["data"]["username"]` without checking the result.
- Contains no meaningful pytest assertions.

A clean CI database may not have the schema or user record, causing test
collection or execution to fail before the application is meaningfully tested.

### Required work

- Initialize the database schema in CI using the repository SQL setup, or
  create the schema through a pytest fixture.
- Create isolated fixture data instead of assuming user ID `4`.
- Remove top-level database connections and unconditional `main()` execution.
- Use pytest fixtures for connection setup and cleanup.
- Roll back or remove test data after each test.
- Add real assertions for create, get, and update behavior.
- Avoid developer-specific credentials or pre-existing rows.
- Verify the workflow against a clean PostgreSQL database.

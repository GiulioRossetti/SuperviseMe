# REST API v1

SuperviseMe exposes a versioned JSON REST API under the `/api/v1/` prefix, authenticated with **JWT Bearer tokens**.

---

## Authentication

### Obtain a token

```http
POST /api/v1/auth/token
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "secret"
}
```

**Response**

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "expires_in": 3600
}
```

Pass the token in subsequent requests:

```http
Authorization: Bearer <jwt>
```

---

## Endpoints

### Users

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/users/me` | Current user profile |
| `PATCH` | `/api/v1/users/me` | Update profile fields |

### Theses

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/theses/` | List theses (filtered by role) |
| `GET` | `/api/v1/theses/{id}` | Thesis detail |
| `POST` | `/api/v1/theses/` | Create thesis (supervisor/admin) |
| `PATCH` | `/api/v1/theses/{id}` | Update thesis |

### Progress Updates

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/theses/{id}/updates` | List updates |
| `POST` | `/api/v1/theses/{id}/updates` | Submit an update (student) |

### Notifications

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/notifications/` | List unread notifications |
| `POST` | `/api/v1/notifications/{id}/read` | Mark as read |
| `GET` | `/api/v1/notifications/stream` | **SSE** real-time stream |

!!! tip "Server-Sent Events"
    Connect to `/api/v1/notifications/stream` with an `EventSource` to receive push notifications in the browser without polling.

---

## Error responses

All errors follow a consistent envelope:

```json
{
  "error": "not_found",
  "message": "Thesis 42 does not exist.",
  "status": 404
}
```

---

## Rate limiting

The API enforces per-user rate limits via Flask-Caching. Exceeding the limit returns `429 Too Many Requests` with a `Retry-After` header.

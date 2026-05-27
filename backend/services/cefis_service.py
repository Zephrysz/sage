"""
CEFIS API service — wraps v1 and v3 HTTP calls using httpx with a 10s timeout.

API v1 base URL : https://cefis.com.br
API v3 base URL : https://api-v3.cefis.com.br

Auth headers:
  v1 → Authorization: {api_key}          (no prefix)
  v3 → Authorization: Bearer {api_key}
"""

import httpx

# ---------------------------------------------------------------------------
# Base URLs
# ---------------------------------------------------------------------------
_V1_BASE = "https://cefis.com.br"
_V3_BASE = "https://api-v3.cefis.com.br"

_TIMEOUT = 10.0  # seconds


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class CefisTimeoutError(Exception):
    """Raised when a CEFIS API request exceeds the 10-second timeout."""


class CefisAuthError(Exception):
    """Raised when a CEFIS API returns HTTP 401 or 403."""


class CefisServerError(Exception):
    """Raised when a CEFIS API returns HTTP 5xx."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _v1_headers(api_key: str) -> dict[str, str]:
    """Authorization header for CEFIS API v1 (no prefix)."""
    return {"Authorization": api_key}


def _v3_headers(api_key: str) -> dict[str, str]:
    """Authorization header for CEFIS API v3 (Bearer prefix)."""
    return {"Authorization": f"Bearer {api_key}"}


def _handle_response(response: httpx.Response) -> dict:
    """
    Inspect the HTTP response and raise the appropriate custom exception
    for error status codes, or return the parsed JSON body on success.
    """
    if response.status_code in (401, 403):
        raise CefisAuthError(
            f"CEFIS auth error: HTTP {response.status_code}"
        )
    if response.status_code >= 500:
        raise CefisServerError(
            f"CEFIS server error: HTTP {response.status_code}"
        )
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------------------
# API v1 endpoints
# ---------------------------------------------------------------------------

async def login(email: str, password: str) -> dict:
    """
    POST https://cefis.com.br/api/v1/login

    Authenticates with email+password and returns the session API key.
    No prior authentication required.
    Returns the full response data dict (contains key + user).
    """
    url = f"{_V1_BASE}/api/v1/login"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                url,
                json={"email": email, "pass": password},
            )
    except httpx.TimeoutException as exc:
        raise CefisTimeoutError(
            "Timeout while logging in to CEFIS"
        ) from exc

    return _handle_response(response)


async def get_user_me(api_key: str) -> dict:
    """
    GET https://cefis.com.br/api/v1/user/me

    Returns the authenticated user's profile data.
    Requirement 1.1, 1.7
    """
    url = f"{_V1_BASE}/api/v1/user/me"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(url, headers=_v1_headers(api_key))
    except httpx.TimeoutException as exc:
        raise CefisTimeoutError(
            "Timeout while fetching user profile from CEFIS v1"
        ) from exc

    return _handle_response(response)


# ---------------------------------------------------------------------------
# API v3 endpoints
# ---------------------------------------------------------------------------

async def get_certificates(api_key: str) -> list:
    """
    GET https://api-v3.cefis.com.br/performance/certificates

    Returns the list of certificates obtained by the authenticated user.
    Requirement 1.7, 3.1, 4.7
    """
    url = f"{_V3_BASE}/performance/certificates"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(url, headers=_v3_headers(api_key))
    except httpx.TimeoutException as exc:
        raise CefisTimeoutError(
            "Timeout while fetching certificates from CEFIS v3"
        ) from exc

    return _handle_response(response)


async def get_courses(api_key: str, quick_filter: bool = False) -> list:
    """
    GET https://api-v3.cefis.com.br/courses

    Returns the course catalogue. The quick_filter parameter is accepted for
    API compatibility but ignored — the CEFIS v3 API does not support
    ?filter=quick and returns 400 when it is sent (Requirement 4.1).
    """
    url = f"{_V3_BASE}/courses"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(url, headers=_v3_headers(api_key))
    except httpx.TimeoutException as exc:
        raise CefisTimeoutError(
            "Timeout while fetching courses from CEFIS v3"
        ) from exc

    return _handle_response(response)


async def get_course_detail(api_key: str, course_id: str) -> dict:
    """
    GET https://api-v3.cefis.com.br/courses/:id

    Returns detailed information for a single course.
    Requirement 4.3
    """
    url = f"{_V3_BASE}/courses/{course_id}"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(url, headers=_v3_headers(api_key))
    except httpx.TimeoutException as exc:
        raise CefisTimeoutError(
            f"Timeout while fetching course detail (id={course_id}) from CEFIS v3"
        ) from exc

    return _handle_response(response)


async def get_course_lessons(api_key: str, course_id: str) -> list:
    """
    GET https://api-v3.cefis.com.br/courses/:id/lessons

    Returns the list of lessons for a given course.
    Requirement 4.3
    """
    url = f"{_V3_BASE}/courses/{course_id}/lessons"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(url, headers=_v3_headers(api_key))
    except httpx.TimeoutException as exc:
        raise CefisTimeoutError(
            f"Timeout while fetching lessons for course (id={course_id}) from CEFIS v3"
        ) from exc

    return _handle_response(response)

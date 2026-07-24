"""Injectable HTTP transport for foley's live source adapters.

Live SOURCE adapters (Freesound, #5; hosted generators, #6) speak HTTP. To keep
``import foley`` dependency-light (dol-only) and the test suite hermetic (no
network, no HTTP library), the HTTP call is a **dependency-injected callable** —
a :class:`Transport` — that each adapter takes by keyword, defaulting to
:func:`requests_transport`. Tests inject a fake transport returning canned
responses; the real ``requests`` is imported lazily inside
:func:`requests_transport` and **nowhere else**, so it stays behind the
``foley[freesound]`` extra (never pulled by the core or by the fake-injection
tests).

A :class:`Transport` is any callable with the shape::

    transport(method, url, *, params=None, headers=None, json=None) -> Response

and a :class:`Response` is any object exposing ``status_code`` / ``content`` /
``json()`` — a structural subset of ``requests.Response`` (which therefore
satisfies it with no wrapper).

The keyword-only ``json`` body was added for the hosted **generate** adapters (#6:
ElevenLabs Sound Effects POSTs a JSON body), where Freesound (#5) only ever did
GET-with-params. It defaults to ``None`` and is passed straight through to
``requests.request(..., json=...)``, so every existing GET caller (and the
Freesound fake transport) is unaffected.
"""

from __future__ import annotations

from typing import Any, Optional, Protocol

#: Per-request timeout (seconds) for the default requests transport. A live
#: adapter never blocks foley indefinitely on a hung connection.
DEFAULT_TIMEOUT_S: int = 30


class Response(Protocol):
    """The minimal HTTP response surface an adapter needs.

    A structural subset of ``requests.Response`` — ``requests`` satisfies it with
    no wrapper, and a test double is a tiny dataclass with the same three members.
    """

    #: HTTP status code (200 on success).
    status_code: int
    #: Raw response body bytes (used for audio/preview downloads).
    content: bytes

    def json(self) -> Any:
        """Decode the response body as JSON."""
        ...


class Transport(Protocol):
    """A callable performing ONE HTTP request and returning a :class:`Response`.

    The dependency-injection seam: the default is :func:`requests_transport`;
    tests pass a fake. Keyword-only ``params`` / ``headers`` mirror ``requests``.
    """

    def __call__(
        self,
        method: str,
        url: str,
        *,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        json: Optional[dict] = None,
    ) -> Response:
        """Perform the request and return the response."""
        ...


def requests_transport(
    method: str,
    url: str,
    *,
    params: Optional[dict] = None,
    headers: Optional[dict] = None,
    json: Optional[dict] = None,
) -> "Response":
    """The default :class:`Transport` — a thin, lazy wrapper over ``requests``.

    ``requests`` is imported HERE and only here (the ``foley[freesound]`` /
    ``foley[elevenlabs]`` extras), so the foley core stays dol-only and the
    fake-injection test path never needs an HTTP library at all. The returned
    ``requests.Response`` structurally satisfies :class:`Response`.

    Args:
        method: HTTP method (``'GET'`` / ``'POST'`` …).
        url: The full request URL.
        params: Optional query-string parameters.
        headers: Optional request headers (e.g. the auth token).
        json: Optional JSON request body (POST), serialized by ``requests``.

    Returns:
        The ``requests.Response`` (a :class:`Response`).
    """
    import requests  # lazy: foley[freesound]/[elevenlabs]; keeps `import foley` dol-only

    return requests.request(
        method,
        url,
        params=params,
        headers=headers,
        json=json,
        timeout=DEFAULT_TIMEOUT_S,
    )

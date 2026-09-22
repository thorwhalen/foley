# foley.sources.http

Injectable HTTP transport for foley’s live source adapters.

Live SOURCE adapters (Freesound, #5; hosted generators, #6) speak HTTP. To keep
`import foley` dependency-light (dol-only) and the test suite hermetic (no
network, no HTTP library), the HTTP call is a **dependency-injected callable** —
a [`Transport`](#foley.sources.http.Transport) — that each adapter takes by keyword, defaulting to
[`requests_transport()`](#foley.sources.http.requests_transport). Tests inject a fake transport returning canned
responses; the real `requests` is imported lazily inside
[`requests_transport()`](#foley.sources.http.requests_transport) and **nowhere else**, so it stays behind the
`foley[freesound]` extra (never pulled by the core or by the fake-injection
tests).

A [`Transport`](#foley.sources.http.Transport) is any callable with the shape:

```default
transport(method, url, *, params=None, headers=None, json=None) -> Response
```

and a [`Response`](#foley.sources.http.Response) is any object exposing `status_code` / `content` /
`json()` — a structural subset of `requests.Response` (which therefore
satisfies it with no wrapper).

The keyword-only `json` body was added for the hosted **generate** adapters (#6:
ElevenLabs Sound Effects POSTs a JSON body), where Freesound (#5) only ever did
GET-with-params. It defaults to `None` and is passed straight through to
`requests.request(..., json=...)`, so every existing GET caller (and the
Freesound fake transport) is unaffected.

### Module Attributes

| [`DEFAULT_TIMEOUT_S`](#foley.sources.http.DEFAULT_TIMEOUT_S)   | Per-request timeout (seconds) for the default requests transport.   |
|----------------------------------------------------------------------|---------------------------------------------------------------------|

### Functions

| [`requests_transport`](#foley.sources.http.requests_transport)(method, url, \*[, params, ...])   | The default [`Transport`](#foley.sources.http.Transport) — a thin, lazy wrapper over `requests`.   |
|-------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------|

### Classes

| [`Response`](#foley.sources.http.Response)(\*args, \*\*kwargs)   | The minimal HTTP response surface an adapter needs.                                                               |
|---------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------|
| [`Transport`](#foley.sources.http.Transport)(\*args, \*\*kwargs)  | A callable performing ONE HTTP request and returning a [`Response`](#foley.sources.http.Response). |

### foley.sources.http.DEFAULT_TIMEOUT_S *: [int](https://docs.python.org/3/builtins/functions.html#int)* *= 30*

Per-request timeout (seconds) for the default requests transport. A live
adapter never blocks foley indefinitely on a hung connection.

### *class* foley.sources.http.Response(\*args, \*\*kwargs)

Bases: [`Protocol`](https://docs.python.org/3/library/typing.html#typing.Protocol)

The minimal HTTP response surface an adapter needs.

A structural subset of `requests.Response` — `requests` satisfies it with
no wrapper, and a test double is a tiny dataclass with the same three members.

#### content *: [bytes](https://docs.python.org/3/builtins/stdtypes.html#bytes)*

Raw response body bytes (used for audio/preview downloads).

#### json()

Decode the response body as JSON.

* **Return type:**
  [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)

#### status_code *: [int](https://docs.python.org/3/builtins/functions.html#int)*

HTTP status code (200 on success).

### *class* foley.sources.http.Transport(\*args, \*\*kwargs)

Bases: [`Protocol`](https://docs.python.org/3/library/typing.html#typing.Protocol)

A callable performing ONE HTTP request and returning a [`Response`](#foley.sources.http.Response).

The dependency-injection seam: the default is [`requests_transport()`](#foley.sources.http.requests_transport);
tests pass a fake. Keyword-only `params` / `headers` mirror `requests`.

### foley.sources.http.requests_transport(method, url, , params=None, headers=None, json=None)

The default [`Transport`](#foley.sources.http.Transport) — a thin, lazy wrapper over `requests`.

`requests` is imported HERE and only here (the `foley[freesound]` /
`foley[elevenlabs]` extras), so the foley core stays dol-only and the
fake-injection test path never needs an HTTP library at all. The returned
`requests.Response` structurally satisfies [`Response`](#foley.sources.http.Response).

* **Parameters:**
  * **method** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – HTTP method (`'GET'` / `'POST'` …).
  * **url** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – The full request URL.
  * **params** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)]) – Optional query-string parameters.
  * **headers** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)]) – Optional request headers (e.g. the auth token).
  * **json** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)]) – Optional JSON request body (POST), serialized by `requests`.
* **Return type:**
  [`Response`](#foley.sources.http.Response)
* **Returns:**
  The `requests.Response` (a [`Response`](#foley.sources.http.Response)).

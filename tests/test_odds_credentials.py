"""The Odds API key must never reach a log, a traceback, or a committed file.

`clients/odds.py` sends the key as the `apiKey` query parameter -- the only
form The Odds API accepts -- and `requests` embeds the full request URL in the
message of every exception it raises. This repository is public and its
scheduled runs print to a public Actions log, so an unhandled 401/429/5xx used
to carry the live key there behind nothing but GitHub's best-effort masking.

These tests fail on that defect: each one asserts the key is absent from the
exception, from its chain, and from the rendered traceback.
"""

from __future__ import annotations

import traceback

import pytest
import requests

from panthera_mvp.clients import odds

KEY = "s3cr3t-live-odds-key"


class _Resp:
    """Stands in for a failed `requests` response, raising the way `requests`
    does: the message quotes the full URL, query string and all."""

    def __init__(self, status_code: int, url: str) -> None:
        self.status_code = status_code
        self.url = url
        self.headers: dict[str, str] = {}

    def raise_for_status(self) -> None:
        raise requests.HTTPError(
            f"{self.status_code} Client Error: Unauthorized for url: {self.url}",
            response=self,
        )

    def json(self):  # pragma: no cover - never reached on a failed response
        raise AssertionError("json() must not be called on an errored response")


class _Session:
    """Offline session: records the request and fails it. No socket is opened."""

    def __init__(self, status_code: int = 401, transport_exc=None) -> None:
        self.status_code = status_code
        self.transport_exc = transport_exc
        self.requested_url: str | None = None

    def get(self, url, params, timeout):
        self.requested_url = url
        full = f"{url}?apiKey={params['apiKey']}&regions={params['regions']}"
        if self.transport_exc is not None:
            raise self.transport_exc(
                f"HTTPSConnectionPool(host='api.the-odds-api.com', port=443): "
                f"Max retries exceeded with url: {full}"
            )
        return _Resp(self.status_code, full)


def _rendered(exc: BaseException) -> str:
    """Everything an operator would see in a log: the message, the chained and
    contextual causes, and the traceback."""
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))


def _frame_locals(exc: BaseException) -> str:
    """Every local variable in every frame of the traceback, as a renderer that
    prints locals would show them (`pytest --showlocals`, rich, Sentry)."""
    out = []
    tb = exc.__traceback__
    while tb is not None:
        out.extend(f"{k}={v!r}" for k, v in tb.tb_frame.f_locals.items())
        tb = tb.tb_next
    return "\n".join(out)


@pytest.mark.parametrize("status", [401, 429, 500])
def test_http_error_never_carries_the_api_key(tmp_root, status):
    sess = _Session(status_code=status)
    with pytest.raises(odds.OddsRequestError) as caught:
        odds.fetch_snapshot(KEY, session=sess)

    exc = caught.value
    assert KEY not in str(exc)
    assert KEY not in _rendered(exc)
    assert KEY not in _frame_locals(exc)
    assert "apiKey" not in str(exc)
    # The diagnostic survives the scrub.
    assert exc.status_code == status
    assert exc.url == odds.BASE
    # Nothing holding the key may hang off the chain.
    assert exc.__cause__ is None and exc.__context__ is None


@pytest.mark.parametrize(
    "transport_exc", [requests.ConnectionError, requests.Timeout]
)
def test_transport_error_never_carries_the_api_key(tmp_root, transport_exc):
    """ConnectionError/Timeout quote the URL too ("Max retries exceeded with
    url: ...?apiKey=..."), so they are scrubbed on the same path."""
    sess = _Session(transport_exc=transport_exc)
    with pytest.raises(odds.OddsRequestError) as caught:
        odds.fetch_snapshot(KEY, session=sess)

    exc = caught.value
    assert KEY not in str(exc)
    assert KEY not in _rendered(exc)
    assert KEY not in _frame_locals(exc)
    assert exc.status_code is None
    assert exc.cause == transport_exc.__name__
    assert exc.__cause__ is None and exc.__context__ is None


def test_scrub_applies_to_every_sport_key(tmp_root):
    """NCAAF and college baseball snapshots call the same keyed helper."""
    for sport_key in (odds.NCAAF_SPORT_KEY, "baseball_ncaa"):
        sess = _Session(status_code=422)
        with pytest.raises(odds.OddsRequestError) as caught:
            odds.fetch_snapshot(KEY, session=sess, sport_key=sport_key)
        assert KEY not in _rendered(caught.value)
        assert sport_key in caught.value.url


def test_no_caller_frame_holds_the_key(tmp_root, monkeypatch):
    """The real production traceback runs through `cmd_snapshot`, not just
    `fetch_snapshot`, so the caller's frame is rendered too. It must not bind
    the key: callers pass `odds.api_key_from_env()` straight into the call,
    and that helper has returned before the request is made.
    """
    from panthera_mvp import pipeline

    monkeypatch.setenv("ODDS_API_KEY", KEY)
    # Patch the constructor `fetch_snapshot` falls back to, so the keyed call
    # fails without a socket and without cmd_snapshot passing a session.
    monkeypatch.setattr(requests, "Session", lambda: _Session(status_code=401))

    with pytest.raises(odds.OddsRequestError) as caught:
        pipeline.cmd_snapshot("open")

    exc = caught.value
    frames = []
    tb = exc.__traceback__
    while tb is not None:
        frames.append(tb.tb_frame.f_code.co_name)
        tb = tb.tb_next
    # The caller really is in the traceback being checked.
    assert "cmd_snapshot" in frames
    assert KEY not in _rendered(exc)
    assert KEY not in _frame_locals(exc)


def test_credit_guard_still_fires_before_any_request(tmp_root):
    """The disclosure fix must not have moved the guard: a low balance still
    raises CreditGuardError, and no request is attempted."""
    odds.record_credits("test", odds.CreditInfo(used=470, remaining=5))
    sess = _Session()
    with pytest.raises(odds.CreditGuardError):
        odds.fetch_snapshot(KEY, session=sess, min_credits_reserve=30)
    assert sess.requested_url is None

"""Vyrel `net` module (internally ``netx`` to avoid shadowing).

Registered under the Vyrel module name ``"net"``.

Thin HTTP client built on ``urllib.request`` (Python stdlib).  Only GET and
POST are exposed.  A timeout is mandatory (default 10 seconds) so programs
never hang indefinitely.

**Offline tests**: the test suite does not touch the network.  It installs a
``file://`` URL handler and exercises the code path against a temp file, so
this module is fully covered without any network dependency.
"""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

from ._util import StdlibError, as_str


def _check_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https", "file"):
        raise StdlibError(
            f"net: unsupported URL scheme '{parsed.scheme}'"
        )


def attrs() -> Dict[str, Any]:
    def _get(url: Any, timeout: Any = 10) -> str:
        u = as_str(url, "url")
        _check_url(u)
        try:
            with urllib.request.urlopen(u, timeout=float(timeout)) as r:
                data = r.read()
        except urllib.error.HTTPError as e:
            raise StdlibError(f"net: HTTP {e.code} from {u}")
        except urllib.error.URLError as e:
            raise StdlibError(f"net: cannot reach {u}: {e.reason}")
        except TimeoutError:
            raise StdlibError(f"net: timed out after {timeout}s")
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            raise StdlibError("net: response is not valid UTF-8")

    def _post(url: Any, body: Any, timeout: Any = 10) -> str:
        u = as_str(url, "url")
        _check_url(u)
        data = as_str(body, "body").encode("utf-8")
        req = urllib.request.Request(
            u, data=data, method="POST",
            headers={"Content-Type": "text/plain; charset=utf-8"},
        )
        try:
            with urllib.request.urlopen(req, timeout=float(timeout)) as r:
                resp = r.read()
        except urllib.error.HTTPError as e:
            raise StdlibError(f"net: HTTP {e.code} from {u}")
        except urllib.error.URLError as e:
            raise StdlibError(f"net: cannot reach {u}: {e.reason}")
        except TimeoutError:
            raise StdlibError(f"net: timed out after {timeout}s")
        try:
            return resp.decode("utf-8")
        except UnicodeDecodeError:
            raise StdlibError("net: response is not valid UTF-8")

    return {
        "get": _get,
        "post": _post,
    }

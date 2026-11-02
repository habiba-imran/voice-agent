"""Probe only the native SDK's loopback health endpoint; never contacts a provider."""

from http.client import HTTPConnection, HTTPException


def healthy(port: int = 8081) -> bool:
    connection = HTTPConnection("127.0.0.1", port, timeout=2)
    try:
        connection.request("GET", "/")
        response = connection.getresponse()
        return response.status == 200 and response.read(32).strip() == b"OK"
    except (OSError, ValueError, HTTPException):
        return False
    finally:
        connection.close()


def main():
    raise SystemExit(0 if healthy() else 1)


if __name__ == "__main__":
    main()

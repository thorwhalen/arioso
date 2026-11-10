"""A worker driver for tests: echoes requests; prints noise to stdout; fails on demand."""

from arioso._isolated import serve


def handle(req):
    print("library noise on stdout")  # must not reach the protocol channel
    if req.get("fail"):
        raise ValueError("asked to fail")
    return {"echo": req}


if __name__ == "__main__":
    serve(handle)

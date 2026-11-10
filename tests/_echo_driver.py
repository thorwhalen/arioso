"""A worker driver for tests: echoes requests; prints noise to stdout; fails on demand."""

import os
import sys

from arioso._isolated import serve


def handle(req):
    print("library noise on stdout")  # must not reach the protocol channel
    if req.get("fail"):
        raise ValueError("asked to fail")
    if req.get("garble"):
        sys.__stdout__.write("not json\n")  # fd 1 now points at stderr, so this is harmless
    return {"echo": req, "pythonpath": os.environ.get("PYTHONPATH", "")}


if __name__ == "__main__":
    serve(handle)

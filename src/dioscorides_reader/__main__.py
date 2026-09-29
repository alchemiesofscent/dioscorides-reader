"""Explicit local build, import, and preview commands."""
from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .compiler import compile_bundle, fetch_bundle, fetch_release, MARKER


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Dioscorides parallel reader")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="Compile a verified corpus bundle")
    build.add_argument("--bundle", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--lock", type=Path)
    build.add_argument("--exclude", action="append", default=[], metavar="STREAM",
                       help="Omit an exported stream from the output (repeatable)")
    fetch = commands.add_parser("fetch", help="Verify and cache a local immutable corpus export")
    fetch_source = fetch.add_mutually_exclusive_group(required=True)
    fetch_source.add_argument("--source", type=Path)
    fetch_source.add_argument("--repository")
    fetch.add_argument("--tag")
    fetch.add_argument("--asset", default="dioscorides-corpus.tar.gz")
    fetch.add_argument("--cache", type=Path, default=Path(".cache/corpus"))
    fetch.add_argument("--lock", type=Path)
    serve = commands.add_parser("serve", help="Serve completed output on loopback")
    serve.add_argument("--directory", type=Path, default=Path("dist"))
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--bind", default="127.0.0.1")
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            result = compile_bundle(args.bundle, args.output, args.lock, tuple(args.exclude))
            print(f"Built {len(result['editions'])} streams from {result['bundle_id']} -> {args.output}")
        elif args.command == "fetch":
            if args.source:
                print(fetch_bundle(args.source, args.cache, args.lock))
            else:
                if not args.tag or not args.lock:
                    raise ValueError("Private release fetch requires --tag and --lock")
                print(fetch_release(args.repository, args.tag, args.asset, args.cache, args.lock))
        else:
            directory = args.directory.resolve(strict=True)
            if not (directory / MARKER).is_file():
                raise ValueError("Serve requires a completed reader build")
            handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
            with ThreadingHTTPServer((args.bind, args.port), handler) as server:
                print(f"Dioscorides reader: http://{args.bind}:{args.port}/reader.html", flush=True)
                server.serve_forever()
    except (ValueError, OSError, KeyError) as error:
        parser.exit(2, f"error: {error}\n")
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

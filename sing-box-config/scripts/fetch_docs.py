#!/usr/bin/env python3
"""Fetch a sing-box documentation page for a specific version.

The live site documents the latest release, which is often newer than the
version the user runs.  This helper fetches the page from the matching git tag
instead, tries the jsDelivr mirror before raw.githubusercontent.com, and keeps a
local cache so repeated reads do not hit the network.

Examples:
  python3 scripts/fetch_docs.py dns --version 1.14.4
  python3 scripts/fetch_docs.py configuration/route/rule/ -v 1.14.4 --zh
  python3 scripts/fetch_docs.py schema -v 1.14.4 --out schema.json
  python3 scripts/fetch_docs.py inbound/tun --version testing
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_VERSION = "1.14.4"
USER_AGENT = "sing-box-config-skill/1.0 (+https://sing-box.sagernet.org/)"
ALIASES = {
    "dns": "configuration/dns/index.md",
    "route": "configuration/route/index.md",
    "inbounds": "configuration/inbound/index.md",
    "inbound": "configuration/inbound/index.md",
    "outbounds": "configuration/outbound/index.md",
    "outbound": "configuration/outbound/index.md",
    "endpoints": "configuration/endpoint/index.md",
    "endpoint": "configuration/endpoint/index.md",
    "services": "configuration/service/index.md",
    "service": "configuration/service/index.md",
    "log": "configuration/log/index.md",
    "ntp": "configuration/ntp/index.md",
    "experimental": "configuration/experimental/index.md",
    "certificate": "configuration/certificate/index.md",
    "http-clients": "configuration/shared/http-client/index.md",
    "http_client": "configuration/shared/http-client/index.md",
    "network-namespace": "configuration/network-namespace/index.md",
    "migration": "migration.md",
    "deprecated": "deprecated.md",
    "schema": "schema.json",
}


def cache_root(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    base = os.environ.get("XDG_CACHE_HOME")
    root = Path(base) / "sing-box-docs" if base else Path.home() / ".cache" / "sing-box-docs"
    try:
        root.mkdir(parents=True, exist_ok=True)
        return root
    except OSError:
        fallback = Path(tempfile.gettempdir()) / "sing-box-docs"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def normalize_page(value: str) -> str:
    """Return a docs-relative markdown path, without a language suffix."""
    text = value.strip()
    if text.startswith(("http://", "https://")):
        parsed = urllib.parse.urlparse(text)
        text = parsed.path
    text = text.strip("/")
    text = re.sub(r"^zh/", "", text)
    text = text.replace("\\", "/")
    if ".." in Path(text).parts:
        raise ValueError("path must not contain '..'")
    if not text:
        raise ValueError("empty page path")
    if text in ALIASES:
        return ALIASES[text]
    if text.startswith((
        "inbound/", "outbound/", "endpoint/", "service/", "dns/", "route/",
        "experimental/", "shared/", "certificate/", "network-namespace/",
        "log/", "ntp/",
    )):
        text = "configuration/" + text
    if text.endswith(".json"):
        return text
    if text.endswith(".md"):
        return re.sub(r"\.zh\.md$", ".md", text)
    # Directory pages are index.md; leaves such as migration are .md.
    if text.endswith("/") or "." not in Path(text).name:
        return f"{text}/index.md"
    return f"{text}.md"


def page_candidates(page: str) -> list[str]:
    if page.endswith("/index.md"):
        return [page, page[: -len("/index.md")] + ".md"]
    if page.endswith(".md"):
        return [page]
    return [f"{page}/index.md", f"{page}.md"]


def chinese_variant(page: str) -> str:
    if page.endswith(".md"):
        return page[:-3] + ".zh.md"
    return page + ".zh.md"


class NotFoundError(Exception):
    pass


def network_fetch(url: str, timeout: float) -> str:
    last: Exception | None = None
    for attempt in range(2):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except urllib.error.HTTPError as error:
            if error.code == 404:
                raise NotFoundError(url) from error
            last = error
        except Exception as error:  # noqa: BLE001 - urllib errors vary by platform
            last = error
        if attempt == 0:
            time.sleep(0.8)
    assert last is not None
    raise last


def strip_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    lines = text.splitlines(keepends=True)
    for index in range(1, min(len(lines), 40)):
        if lines[index].strip() == "---":
            return "".join(lines[index + 1 :]).lstrip("\n")
    return text


def tag_ref(version: str) -> str:
    lowered = version.lower()
    if lowered in ("testing", "dev", "latest"):
        return "testing"
    return "v" + version.lstrip("vV")


def source_urls(page: str, version: str) -> list[str]:
    ref = tag_ref(version)
    quoted = urllib.parse.quote(page, safe="/")
    return [
        f"https://cdn.jsdelivr.net/gh/SagerNet/sing-box@{ref}/docs/{quoted}",
        f"https://raw.githubusercontent.com/SagerNet/sing-box/{ref}/docs/{quoted}",
    ]


def cache_path(root: Path, version: str, page: str, zh: bool) -> Path:
    ref = tag_ref(version)
    safe = page.replace("/", "__")
    if zh:
        safe += ".zh"
    return root / ref / safe


def fetch_page(
    page: str,
    version: str,
    zh: bool,
    root: Path,
    refresh: bool,
    timeout: float,
) -> tuple[str, str, str]:
    """Return (text, source_url, cache_note)."""
    variants = [chinese_variant(page), page] if zh else [page]
    last_error: Exception | None = None
    for variant in variants:
        cached = cache_path(root, version, variant, zh and variant == chinese_variant(page))
        if cached.exists() and not refresh:
            return cached.read_text(encoding="utf-8"), f"cache:{cached}", "cache"
        for url in source_urls(variant, version):
            try:
                text = network_fetch(url, timeout)
                cached.parent.mkdir(parents=True, exist_ok=True)
                cached.write_text(text, encoding="utf-8")
                return text, url, "network"
            except NotFoundError:
                # jsDelivr mirrors the repository; a 404 there means this
                # variant does not exist.  Do not hang on raw.githubusercontent.
                break
            except Exception as error:  # noqa: BLE001
                last_error = error
    hint = (
        "抓取失败。可换用 jsDelivr 镜像，或离线执行："
        f"git clone --depth 1 --branch {tag_ref(version)} "
        "https://github.com/SagerNet/sing-box /tmp/sing-box-docs"
        "，然后直接读 /tmp/sing-box-docs/docs/<路径>。"
    )
    raise RuntimeError(f"{hint}\n最后一个错误: {last_error}")


def fetch_schema(version: str, root: Path, refresh: bool, timeout: float) -> tuple[str, str, str]:
    if tag_ref(version) == "testing":
        urls = [
            "https://cdn.jsdelivr.net/gh/SagerNet/sing-box@testing/docs/schema.json",
            "https://raw.githubusercontent.com/SagerNet/sing-box/testing/docs/schema.json",
            "https://sing-box.sagernet.org/schema.json",
        ]
    else:
        urls = [
            f"https://cdn.jsdelivr.net/gh/SagerNet/sing-box@{tag_ref(version)}/docs/schema.json",
            f"https://raw.githubusercontent.com/SagerNet/sing-box/{tag_ref(version)}/docs/schema.json",
        ]
    cached = root / tag_ref(version) / "schema.json"
    if cached.exists() and not refresh:
        return cached.read_text(encoding="utf-8"), f"cache:{cached}", "cache"
    last_error: Exception | None = None
    for url in urls:
        try:
            text = network_fetch(url, timeout)
            json.loads(text)  # fail early on an HTML error page
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_text(text, encoding="utf-8")
            return text, url, "network"
        except NotFoundError:
            break
        except Exception as error:  # noqa: BLE001
            last_error = error
    raise RuntimeError(
        "无法获取官方 schema。v1.14.0 起才有 tag 级 schema；旧版本请用文档和 "
        f"sing-box check。最后一个错误: {last_error}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch a versioned sing-box documentation page.")
    parser.add_argument("page", help="page path/URL, or an alias such as dns, route, tun, schema")
    parser.add_argument("-v", "--version", default=DEFAULT_VERSION,
                        help=f"target version or testing (default: {DEFAULT_VERSION})")
    parser.add_argument("--zh", action="store_true", help="prefer the Chinese .zh.md sibling")
    parser.add_argument("--schema", action="store_true", help="fetch docs/schema.json (same as page=schema)")
    parser.add_argument("--out", help="write the result to this file instead of stdout")
    parser.add_argument("--cache-dir", help="cache directory")
    parser.add_argument("--refresh", action="store_true", help="ignore and replace the cache")
    parser.add_argument("--timeout", type=float, default=20.0, help="network timeout seconds")
    parser.add_argument("--raw", action="store_true", help="keep YAML frontmatter")
    parser.add_argument("--json", action="store_true", help="emit a JSON envelope with source metadata")
    args = parser.parse_args(argv)

    try:
        if args.schema or args.page.strip().lower() == "schema":
            version = args.version
            root = cache_root(args.cache_dir)
            text, source, note = fetch_schema(version, root, args.refresh, args.timeout)
            kind = "schema"
        else:
            page = normalize_page(args.page)
            # A directory page may be index.md or <dir>.md; try both.
            candidates = page_candidates(page)
            text = None
            source = ""
            note = ""
            last_error: Exception | None = None
            for candidate in candidates:
                try:
                    text, source, note = fetch_page(
                        candidate, args.version, args.zh, cache_root(args.cache_dir),
                        args.refresh, args.timeout,
                    )
                    break
                except RuntimeError as error:
                    last_error = error
            if text is None:
                raise last_error or RuntimeError("page not found")
            kind = "docs"
            if not args.raw:
                text = strip_frontmatter(text)
    except (ValueError, RuntimeError) as error:
        print(f"错误: {error}", file=sys.stderr)
        return 2

    if args.out:
        destination = Path(args.out).expanduser()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8")
        if args.json:
            print(json.dumps({
                "kind": kind, "version": args.version, "source": source,
                "cache": note, "out": str(destination), "bytes": len(text.encode("utf-8")),
            }, ensure_ascii=False, indent=2))
        else:
            print(f"已写入 {destination}（{len(text.encode('utf-8'))} bytes，来源 {note}: {source}）",
                  file=sys.stderr)
    elif args.json:
        print(json.dumps({
            "kind": kind, "version": args.version, "source": source,
            "cache": note, "content": text,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"<!-- source: {source} ({note}) -->", file=sys.stderr)
        sys.stdout.write(text if text.endswith("\n") else text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

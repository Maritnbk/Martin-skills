#!/usr/bin/env python3
"""Validate a sing-box configuration against a target version.

The checker is deliberately layered so that a missing network or a missing
`sing-box` binary does not turn into a false "verified" claim:

  L0  JSONC syntax (comments and trailing commas are accepted)
  L1  version-aware removed/deprecated field scan + tag/reference checks
  L2  official JSON Schema (v1.14.0+; fetched from the tag, then cached)
  L3  `sing-box check` when the binary is available

Only L3 can say that the running program accepts the configuration.  The
script prints "STRUCTURE OK" when only L2 passed, and "UNVERIFIED" when
neither L2 nor L3 ran.

Usage:
  python3 scripts/validate.py config.jsonc --version 1.14.4
  python3 scripts/validate.py config.jsonc -v 1.14.4 --offline
  python3 scripts/validate.py config.jsonc -v 1.14.4 --json
  python3 scripts/validate.py references/recipes/tun-transparent.md -v 1.14.4 --extract
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

SNAPSHOT_VERSION = "1.14.4"
USER_AGENT = "sing-box-config-skill/1.0 (+https://sing-box.sagernet.org/)"


@dataclass
class Finding:
    level: str  # E / W / U
    code: str
    path: str
    message: str
    doc: str | None = None

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "level": self.level,
            "code": self.code,
            "path": self.path,
            "message": self.message,
        }
        if self.doc:
            out["doc"] = self.doc
        return out


@dataclass(frozen=True)
class FieldRule:
    pattern: str
    deprecated: str
    removed: str | None
    replacement: str
    doc: str
    only_type: str | None = None
    value_in: frozenset[str] | None = None


# Version thresholds are copied from the official deprecated list and the
# per-field "Deprecated / Removed" notes.  When in doubt the rule only warns:
# a false error is worse than a missed warning, and L3 remains authoritative.
FIELD_RULES: tuple[FieldRule, ...] = (
    FieldRule("dns.fakeip", "1.12.0", "1.14.0",
              "dns.servers 中使用 type=fakeip", "/configuration/dns/server/fakeip/"),
    FieldRule("route.geoip", "1.8.0", "1.12.0",
              "route.rule_set + rule_set 匹配", "/configuration/rule-set/"),
    FieldRule("route.geosite", "1.8.0", "1.12.0",
              "route.rule_set + rule_set 匹配", "/configuration/rule-set/"),
    FieldRule("dns.rules[*].geoip", "1.8.0", "1.12.0",
              "rule_set 匹配", "/configuration/dns/rule/"),
    FieldRule("dns.rules[*].geosite", "1.8.0", "1.12.0",
              "rule_set 匹配", "/configuration/dns/rule/"),
    FieldRule("dns.servers[*].address", "1.12.0", "1.14.0",
              "type + server（新版 DNS server 格式）", "/configuration/dns/server/"),
    FieldRule("dns.servers[*].address_resolver", "1.12.0", "1.14.0",
              "domain_resolver", "/configuration/dns/server/"),
    FieldRule("dns.servers[*].address_strategy", "1.12.0", "1.14.0",
              "strategy", "/configuration/dns/server/"),
    FieldRule("route.rules[*].geoip", "1.8.0", "1.12.0",
              "rule_set 匹配", "/configuration/route/rule/"),
    FieldRule("route.rules[*].geosite", "1.8.0", "1.12.0",
              "rule_set 匹配", "/configuration/route/rule/"),
    FieldRule("route.rules[*].rule_set_ipcidr_match_source", "1.10.0", "1.11.0",
              "rule_set_ip_cidr_match_source", "/configuration/route/rule/"),
    FieldRule("dns.rules[*].rule_set_ipcidr_match_source", "1.10.0", "1.11.0",
              "rule_set_ip_cidr_match_source", "/configuration/dns/rule/"),
    FieldRule("inbounds[*].inet4_address", "1.10.0", "1.12.0",
              "inbounds[].address", "/configuration/inbound/tun/"),
    FieldRule("inbounds[*].inet6_address", "1.10.0", "1.12.0",
              "inbounds[].address", "/configuration/inbound/tun/"),
    FieldRule("inbounds[*].inet4_route_address", "1.10.0", "1.12.0",
              "inbounds[].route_address", "/configuration/inbound/tun/"),
    FieldRule("inbounds[*].inet6_route_address", "1.10.0", "1.12.0",
              "inbounds[].route_address", "/configuration/inbound/tun/"),
    FieldRule("inbounds[*].inet4_route_exclude_address", "1.10.0", "1.12.0",
              "inbounds[].route_exclude_address", "/configuration/inbound/tun/"),
    FieldRule("inbounds[*].inet6_route_exclude_address", "1.10.0", "1.12.0",
              "inbounds[].route_exclude_address", "/configuration/inbound/tun/"),
    FieldRule("inbounds[*].gso", "1.11.0", "1.13.0",
              "删除该字段", "/configuration/inbound/tun/"),
    FieldRule("inbounds[*].sniff", "1.11.0", "1.13.0",
              "route.rules 中 action=sniff", "/configuration/route/rule_action/"),
    FieldRule("inbounds[*].sniff_override_destination", "1.11.0", "1.13.0",
              "删除该字段", "/configuration/route/rule_action/"),
    FieldRule("inbounds[*].sniff_timeout", "1.11.0", "1.13.0",
              "route.rules 中 action=sniff 的 timeout", "/configuration/route/rule_action/"),
    FieldRule("inbounds[*].domain_strategy", "1.11.0", "1.13.0",
              "dial 字段 domain_resolver", "/configuration/shared/dial/"),
    FieldRule("outbounds[*].type", "1.11.0", "1.13.0",
              "route.rules 中 action=reject / hijack-dns",
              "/configuration/route/rule_action/", value_in=frozenset({"block", "dns"})),
    FieldRule("outbounds[*].type", "1.11.0", "1.13.0",
              "endpoints 中 type=wireguard",
              "/configuration/endpoint/wireguard/", value_in=frozenset({"wireguard"})),
    FieldRule("outbounds[*].override_address", "1.11.0", "1.13.0",
              "route.rules 中 action=route-options", "/configuration/route/rule_action/",
              only_type="direct"),
    FieldRule("outbounds[*].override_port", "1.11.0", "1.13.0",
              "route.rules 中 action=route-options", "/configuration/route/rule_action/",
              only_type="direct"),
    FieldRule("dns.rules[*].outbound", "1.12.0", None,
              "dial 字段 domain_resolver / route.default_domain_resolver", "/configuration/dns/rule/"),
    FieldRule("dns.rules[*].strategy", "1.14.0", "1.16.0",
              "dns.servers[].strategy", "/configuration/dns/"),
    FieldRule("dns.independent_cache", "1.14.0", "1.16.0",
              "删除该字段", "/configuration/dns/"),
    FieldRule("experimental.cache_file.store_rdrc", "1.14.0", "1.16.0",
              "experimental.cache_file.store_dns", "/configuration/experimental/cache-file/"),
    FieldRule("route.rule_set[*].download_detour", "1.14.0", "1.16.0",
              "rule_set.http_client + top-level http_clients", "/configuration/rule-set/"),
    FieldRule("experimental.clash_api.store_mode", "1.8.0", None,
              "experimental.cache_file", "/configuration/experimental/clash-api/"),
    FieldRule("experimental.clash_api.store_selected", "1.8.0", None,
              "experimental.cache_file", "/configuration/experimental/clash-api/"),
    FieldRule("experimental.clash_api.store_fakeip", "1.8.0", None,
              "experimental.cache_file", "/configuration/experimental/clash-api/"),
    FieldRule("experimental.clash_api.cache_file", "1.8.0", None,
              "experimental.cache_file", "/configuration/experimental/clash-api/"),
    FieldRule("experimental.clash_api.cache_id", "1.8.0", None,
              "experimental.cache_file", "/configuration/experimental/clash-api/"),
)


def parse_version(text: str) -> tuple[int, int, int, int] | None:
    """Return (major, minor, patch, release) or None for testing/latest."""
    if not text:
        return None
    value = text.strip().lstrip("vV")
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?", value)
    if not match:
        return None
    major, minor, patch = (int(match.group(i)) for i in range(1, 4))
    release = 1 if match.group(4) is None else 0
    return major, minor, patch, release


def version_ge(version: tuple[int, int, int, int] | None, threshold: str) -> bool:
    if version is None:
        return False
    other = parse_version(threshold)
    return other is not None and version >= other


def strip_jsonc(text: str) -> str:
    """Remove // and /* */ comments plus trailing commas, preserving strings."""
    text = text.lstrip("\ufeff")
    out: list[str] = []
    index = 0
    length = len(text)
    in_string = False
    escaped = False
    while index < length:
        char = text[index]
        if in_string:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            out.append(char)
            index += 1
            continue
        if char == "/" and index + 1 < length and text[index + 1] == "/":
            index += 2
            while index < length and text[index] not in "\r\n":
                index += 1
            continue
        if char == "/" and index + 1 < length and text[index + 1] == "*":
            index += 2
            while index + 1 < length and not (text[index] == "*" and text[index + 1] == "/"):
                index += 1
            index += 2
            continue
        out.append(char)
        index += 1

    cleaned = "".join(out)
    result: list[str] = []
    index = 0
    length = len(cleaned)
    in_string = False
    escaped = False
    while index < length:
        char = cleaned[index]
        if in_string:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            result.append(char)
            index += 1
            continue
        if char == ",":
            lookahead = index + 1
            while lookahead < length and cleaned[lookahead] in " \t\r\n":
                lookahead += 1
            if lookahead < length and cleaned[lookahead] in "}]":
                index += 1
                continue
        result.append(char)
        index += 1
    return "".join(result)


def pattern_parts(pattern: str) -> list[str]:
    """Turn 'rules[*].outbound' into ['rules', '[*]', 'outbound']."""
    parts: list[str] = []
    for segment in pattern.split("."):
        while "[*]" in segment:
            head, _, tail = segment.partition("[*]")
            if head:
                parts.append(head)
            parts.append("[*]")
            segment = tail
        if segment:
            parts.append(segment)
    return parts


def find_paths(node: Any, parts: list[str], prefix: str = "", parent: Any = None) -> Iterable[tuple[str, Any, Any]]:
    """Yield (json_path, value, parent) for a simple pattern with [*] tokens."""
    if not parts:
        yield prefix or "/", node, parent
        return
    head, rest = parts[0], parts[1:]
    if head == "[*]":
        if isinstance(node, list):
            for position, value in enumerate(node):
                yield from find_paths(value, rest, f"{prefix}/{position}", node)
        elif isinstance(node, dict):
            for key, value in node.items():
                yield from find_paths(value, rest, f"{prefix}/{key}", node)
        return
    if isinstance(node, dict) and head in node:
        yield from find_paths(node[head], rest, f"{prefix}/{head}", node)


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def collect_tags(root: dict[str, Any]) -> dict[str, set[str]]:
    tags: dict[str, set[str]] = {}
    for section in ("inbounds", "outbounds", "endpoints", "services"):
        values = root.get(section)
        tags[section] = {
            item["tag"] for item in values
            if isinstance(values, list) and isinstance(item, dict) and isinstance(item.get("tag"), str)
        } if isinstance(values, list) else set()
    dns = root.get("dns")
    tags["dns_servers"] = {
        item["tag"] for item in dns.get("servers", [])
        if isinstance(dns, dict) and isinstance(item, dict) and isinstance(item.get("tag"), str)
    } if isinstance(dns, dict) and isinstance(dns.get("servers"), list) else set()
    route = root.get("route")
    tags["rule_sets"] = {
        item["tag"] for item in route.get("rule_set", [])
        if isinstance(route, dict) and isinstance(item, dict) and isinstance(item.get("tag"), str)
    } if isinstance(route, dict) and isinstance(route.get("rule_set"), list) else set()
    tags["http_clients"] = {
        item["tag"] for item in root.get("http_clients", [])
        if isinstance(root.get("http_clients"), list) and isinstance(item, dict) and isinstance(item.get("tag"), str)
    } if isinstance(root.get("http_clients"), list) else set()
    return tags


def check_duplicates(root: dict[str, Any], findings: list[Finding]) -> None:
    for section in ("inbounds", "outbounds", "endpoints", "services"):
        values = root.get(section)
        if not isinstance(values, list):
            continue
        seen: dict[str, int] = {}
        for position, item in enumerate(values):
            if not isinstance(item, dict) or not isinstance(item.get("tag"), str):
                continue
            tag = item["tag"]
            if tag in seen:
                findings.append(Finding(
                    "E", "DUPLICATE-TAG", f"/{section}/{position}/tag",
                    f"tag {tag!r} 与 /{section}/{seen[tag]}/tag 重复；同一类对象的 tag 必须唯一",
                    "/configuration/",
                ))
            else:
                seen[tag] = position


def check_references(root: dict[str, Any], tags: dict[str, set[str]], findings: list[Finding]) -> None:
    allowed_outbounds = tags["outbounds"] | tags["endpoints"]

    route = root.get("route")
    if isinstance(route, dict):
        final = route.get("final")
        if isinstance(final, str) and final not in allowed_outbounds:
            findings.append(Finding(
                "E", "REF-FINAL", "/route/final",
                f"route.final 指向不存在的 outbound/endpoint: {final!r}",
                "/configuration/route/",
            ))
        for position, rule in enumerate(as_list(route.get("rules"))):
            if not isinstance(rule, dict):
                continue
            action = rule.get("action", "route")
            if action in ("route", "bypass") and isinstance(rule.get("outbound"), str):
                target = rule["outbound"]
                if target not in allowed_outbounds:
                    findings.append(Finding(
                        "E", "REF-OUTBOUND", f"/route/rules/{position}/outbound",
                        f"规则引用了不存在的 outbound/endpoint: {target!r}",
                        "/configuration/route/rule_action/",
                    ))
            if isinstance(rule.get("rule_set"), (str, list)):
                for name in as_list(rule["rule_set"]):
                    if isinstance(name, str) and name not in tags["rule_sets"]:
                        findings.append(Finding(
                            "E", "REF-RULESET", f"/route/rules/{position}/rule_set",
                            f"规则引用了不存在的 rule_set: {name!r}",
                            "/configuration/route/rule_set/",
                        ))
        default_http = route.get("default_http_client")
        if isinstance(default_http, str) and default_http not in tags["http_clients"]:
            findings.append(Finding(
                "E", "REF-HTTP", "/route/default_http_client",
                f"default_http_client 指向不存在的 http_clients tag: {default_http!r}",
                "/configuration/shared/http-client/",
            ))
        default_resolver = route.get("default_domain_resolver")
        if isinstance(default_resolver, str) and default_resolver not in tags["dns_servers"]:
            findings.append(Finding(
                "E", "REF-DNS", "/route/default_domain_resolver",
                f"default_domain_resolver 指向不存在的 DNS server tag: {default_resolver!r}",
                "/configuration/route/",
            ))
        for position, rule_set in enumerate(as_list(route.get("rule_set"))):
            if isinstance(rule_set, dict) and isinstance(rule_set.get("http_client"), str):
                name = rule_set["http_client"]
                if name not in tags["http_clients"]:
                    findings.append(Finding(
                        "E", "REF-HTTP", f"/route/rule_set/{position}/http_client",
                        f"http_client 指向不存在的 http_clients tag: {name!r}",
                        "/configuration/rule-set/",
                    ))

    dns = root.get("dns")
    if isinstance(dns, dict):
        final = dns.get("final")
        if isinstance(final, str) and final not in tags["dns_servers"]:
            findings.append(Finding(
                "E", "REF-DNS", "/dns/final",
                f"dns.final 指向不存在的 DNS server: {final!r}",
                "/configuration/dns/",
            ))
        for position, rule in enumerate(as_list(dns.get("rules"))):
            if not isinstance(rule, dict):
                continue
            server = rule.get("server")
            if isinstance(server, str) and server not in tags["dns_servers"]:
                findings.append(Finding(
                    "E", "REF-DNS", f"/dns/rules/{position}/server",
                    f"DNS 规则引用了不存在的 server: {server!r}",
                    "/configuration/dns/rule/",
                ))
            for name in as_list(rule.get("rule_set")):
                if isinstance(name, str) and name not in tags["rule_sets"]:
                    findings.append(Finding(
                        "E", "REF-RULESET", f"/dns/rules/{position}/rule_set",
                        f"DNS 规则引用了不存在的 rule_set: {name!r}",
                        "/configuration/dns/rule/",
                    ))
        for position, server in enumerate(as_list(dns.get("servers"))):
            if isinstance(server, dict) and isinstance(server.get("detour"), str):
                name = server["detour"]
                if name not in allowed_outbounds:
                    findings.append(Finding(
                        "E", "REF-DETOUR", f"/dns/servers/{position}/detour",
                        f"DNS server 的 detour 指向不存在的 outbound/endpoint: {name!r}",
                        "/configuration/dns/",
                    ))

    for position, inbound in enumerate(as_list(root.get("inbounds"))):
        if isinstance(inbound, dict) and isinstance(inbound.get("detour"), str):
            name = inbound["detour"]
            if name not in tags["inbounds"]:
                findings.append(Finding(
                    "E", "REF-DETOUR", f"/inbounds/{position}/detour",
                    f"inbound 的 detour 指向不存在的 inbound tag: {name!r}",
                    "/configuration/shared/listen/",
                ))
    for position, outbound in enumerate(as_list(root.get("outbounds"))):
        if not isinstance(outbound, dict):
            continue
        if isinstance(outbound.get("detour"), str):
            name = outbound["detour"]
            if name not in allowed_outbounds:
                findings.append(Finding(
                    "E", "REF-DETOUR", f"/outbounds/{position}/detour",
                    f"outbound 的 detour 指向不存在的 outbound/endpoint: {name!r}",
                    "/configuration/shared/dial/",
                ))
        resolver = outbound.get("domain_resolver")
        if isinstance(resolver, str) and resolver not in tags["dns_servers"]:
            findings.append(Finding(
                "E", "REF-DNS", f"/outbounds/{position}/domain_resolver",
                f"domain_resolver 指向不存在的 DNS server: {resolver!r}",
                "/configuration/shared/dial/",
            ))


def apply_field_rules(
    root: dict[str, Any],
    target: tuple[int, int, int, int] | None,
    findings: list[Finding],
) -> None:
    if target is None:
        return
    for rule in FIELD_RULES:
        for path, value, parent in find_paths(root, pattern_parts(rule.pattern)):
            if rule.value_in is not None and value not in rule.value_in:
                continue
            if rule.only_type is not None:
                if not isinstance(parent, dict) or parent.get("type") != rule.only_type:
                    continue
            if rule.removed and version_ge(target, rule.removed):
                findings.append(Finding(
                    "E", "REMOVED-FIELD", path,
                    f"该字段在 v{rule.removed} 已移除；改用 {rule.replacement}",
                    rule.doc,
                ))
            elif version_ge(target, rule.deprecated):
                suffix = f"；计划在 v{rule.removed} 移除" if rule.removed else ""
                findings.append(Finding(
                    "W", "DEPRECATED-FIELD", path,
                    f"该字段在 v{rule.deprecated} 起废弃{suffix}；改用 {rule.replacement}",
                    rule.doc,
                ))


def strip_deprecated_fields(
    root: dict[str, Any],
    target: tuple[int, int, int, int] | None,
) -> dict[str, Any]:
    """Return a copy without fields that are deprecated but still accepted.

    The official schema omits some deprecated fields (for example
    `download_detour` in v1.14), while the program still accepts them until the
    removal version.  L1 reports the warning; schema validation should judge the
    rest of the object, not fail because of a documented transitional field.
    """
    if target is None:
        return root
    cleaned = copy.deepcopy(root)
    for rule in FIELD_RULES:
        if rule.only_type is not None or rule.value_in is not None:
            continue
        if rule.removed and version_ge(target, rule.removed):
            continue  # removed fields stay for schema to reject
        for path, _value, parent in find_paths(cleaned, pattern_parts(rule.pattern)):
            if isinstance(parent, dict):
                parent.pop(path.rsplit("/", 1)[-1], None)
    return cleaned


def fetch_text(url: str, timeout: float) -> str:
    last: Exception | None = None
    for attempt in range(2):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8")
        except Exception as error:  # noqa: BLE001 - network errors vary by platform
            last = error
            if attempt == 0:
                time.sleep(0.8)
    assert last is not None
    raise last


def schema_urls(version: str, is_testing: bool, target: tuple[int, int, int, int] | None) -> list[str]:
    if not is_testing and target is not None and not version_ge(target, "1.14.0"):
        return []
    ref = "testing" if is_testing else f"v{version.lstrip('v')}"
    urls = [
        f"https://cdn.jsdelivr.net/gh/SagerNet/sing-box@{ref}/docs/schema.json",
        f"https://raw.githubusercontent.com/SagerNet/sing-box/{ref}/docs/schema.json",
    ]
    if is_testing:
        urls.append("https://sing-box.sagernet.org/schema.json")
    return urls


def load_schema(
    args: argparse.Namespace,
    version: str,
    is_testing: bool,
    target: tuple[int, int, int, int] | None,
    findings: list[Finding],
) -> tuple[dict[str, Any] | None, str]:
    if args.schema:
        path = Path(args.schema).expanduser()
        try:
            return json.loads(path.read_text(encoding="utf-8")), f"local:{path}"
        except Exception as error:  # noqa: BLE001
            findings.append(Finding("U", "SCHEMA-LOCAL", str(path), f"无法读取本地 schema: {error}"))
            return None, "unavailable"
    if args.no_schema:
        return None, "skipped"
    urls = schema_urls(version, is_testing, target)
    if not urls:
        findings.append(Finding(
            "U", "SCHEMA-VERSION", "/",
            "官方 JSON Schema 只随 v1.14.0+ 发布；旧版本请以 tag 文档和 sing-box check 为准",
            "/configuration/schema/",
        ))
        return None, "unavailable"

    cache_dir = Path(args.cache_dir).expanduser() if args.cache_dir else default_cache_dir()
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Some sandboxes expose a read-only home.  A temp cache is still better
        # than aborting the whole validation.
        cache_dir = Path(tempfile.gettempdir()) / "sing-box-config"
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            findings.append(Finding(
                "U", "SCHEMA-CACHE", "/", f"无法创建 schema 缓存目录: {error}",
                "/configuration/schema/",
            ))
            return None, "unavailable"
    cache_name = f"schema-{'testing' if is_testing else 'v' + version.lstrip('v')}.json"
    cache_path = cache_dir / cache_name
    if cache_path.exists():
        try:
            return json.loads(cache_path.read_text(encoding="utf-8")), f"cache:{cache_path}"
        except Exception:  # noqa: BLE001
            cache_path.unlink(missing_ok=True)

    if args.offline:
        findings.append(Finding(
            "U", "SCHEMA-OFFLINE", "/",
            f"离线模式且缓存中没有 {cache_name}；跳过 schema 校验",
            "/configuration/schema/",
        ))
        return None, "unavailable"

    last_error: Exception | None = None
    for url in urls:
        try:
            text = fetch_text(url, args.timeout)
            schema = json.loads(text)
            if not isinstance(schema, dict):
                raise ValueError("schema is not a JSON object")
            try:
                cache_path.write_text(text, encoding="utf-8")
            except OSError:
                pass
            source = "live" if "sing-box.sagernet.org" in url else "tag"
            return schema, f"{source}:{url}"
        except Exception as error:  # noqa: BLE001
            last_error = error
    findings.append(Finding(
        "U", "SCHEMA-FETCH", "/",
        f"无法获取官方 schema（{last_error}）；跳过 schema 校验",
        "/configuration/schema/",
    ))
    return None, "unavailable"


def default_cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME")
    if base:
        return Path(base) / "sing-box-config"
    return Path.home() / ".cache" / "sing-box-config"


def schema_findings(
    config: dict[str, Any],
    schema: dict[str, Any],
    findings: list[Finding],
) -> str:
    try:
        import jsonschema  # type: ignore
    except ImportError:
        findings.append(Finding(
            "U", "SCHEMA-MODULE", "/",
            "未安装 jsonschema；无法执行完整 schema 校验（pip install jsonschema）",
            "/configuration/schema/",
        ))
        return "unavailable"
    try:
        validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
        errors = sorted(validator.iter_errors(config), key=lambda error: list(error.absolute_path))
    except Exception as error:  # noqa: BLE001
        findings.append(Finding("U", "SCHEMA-ERROR", "/", f"schema 校验器出错: {error}"))
        return "unavailable"
    if not errors:
        return "passed"

    seen: set[tuple[str, str]] = set()
    for error in errors[:40]:
        path = "/" + "/".join(str(part) for part in error.absolute_path)
        if path == "/":
            path = "/"
        message = error.message
        if error.context:
            candidates = sorted(
                error.context,
                key=lambda item: (
                    len(item.absolute_path),
                    {"additionalProperties": 0, "unevaluatedProperties": 0, "type": 1, "enum": 1, "const": 1}.get(item.validator, 2),
                ),
            )
            if candidates:
                message = f"{message}（{candidates[0].message}）"
        level = "E"
        code = "SCHEMA"
        deprecated_names = (
            "download_detour", "independent_cache", "store_rdrc",
            "store_mode", "store_selected", "store_fakeip", "cache_file", "cache_id",
        )
        if error.validator == "additionalProperties" and any(f"'{name}'" in message for name in deprecated_names):
            level = "W"
            code = "SCHEMA-DEPRECATED"
        key = (path, message)
        if key in seen:
            continue
        seen.add(key)
        findings.append(Finding(level, code, path, f"schema: {message}", "/configuration/schema/"))
    if len(errors) > 40:
        findings.append(Finding("U", "SCHEMA-TRUNCATED", "/", f"schema 错误过多，只显示前 40 条（共 {len(errors)} 条）"))
    return "failed"


def detect_binary_version(binary: str) -> str | None:
    try:
        result = subprocess.run(
            [binary, "version"], capture_output=True, text=True, timeout=15, check=False,
        )
    except Exception:  # noqa: BLE001
        return None
    match = re.search(r"version\s+(\S+)", result.stdout + result.stderr)
    return match.group(1) if match else None


def run_sing_box_check(binary: str, config: Path, timeout: float, findings: list[Finding]) -> str:
    try:
        result = subprocess.run(
            [binary, "check", "-c", str(config)],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
    except FileNotFoundError:
        findings.append(Finding("U", "CHECK-MISSING", "/", f"找不到 sing-box 可执行文件: {binary}"))
        return "unavailable"
    except subprocess.TimeoutExpired:
        findings.append(Finding("E", "CHECK-TIMEOUT", "/", f"sing-box check 超时（{timeout}s）"))
        return "failed"
    output = (result.stderr or result.stdout).strip()
    if result.returncode == 0:
        return "passed"
    detail = "\n".join(output.splitlines()[:12]) if output else f"exit code {result.returncode}"
    findings.append(Finding("E", "CHECK-FAILED", "/", f"sing-box check 未通过：\n{detail}"))
    return "failed"


def extract_jsonc_blocks(text: str) -> list[str]:
    """Return fenced code blocks that look like JSON objects.

    Recipes are Markdown, not standalone config files.  We only accept a
    fenced block that parses as a JSON object, so prose examples and shell
    snippets are skipped.
    """
    blocks = re.findall(r"```(?:jsonc?|json)?\s*\n(.*?)```", text, re.S | re.I)
    parsed: list[str] = []
    for block in blocks:
        try:
            value = json.loads(strip_jsonc(block))
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            parsed.append(block)
    return parsed


def read_config(path: Path, extract: bool = False) -> tuple[dict[str, Any] | None, Finding | None]:
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception as error:  # noqa: BLE001
        return None, Finding("E", "READ", str(path), f"无法读取配置: {error}")
    if extract:
        blocks = extract_jsonc_blocks(raw)
        if not blocks:
            return None, Finding("E", "EXTRACT", str(path), "Markdown 中没有可解析的 JSONC/JSON 代码块")
        raw = blocks[0]
    try:
        parsed = json.loads(strip_jsonc(raw))
    except json.JSONDecodeError as error:
        return None, Finding(
            "E", "JSONC", f"line {error.lineno}, column {error.colno}",
            f"JSONC 解析失败: {error.msg}",
        )
    if not isinstance(parsed, dict):
        return None, Finding("E", "ROOT", "/", "配置根节点必须是 JSON 对象")
    return parsed, None


def print_human(
    config_path: Path,
    version_text: str,
    version_source: str,
    findings: list[Finding],
    schema_status: str,
    check_status: str,
    verdict: str,
) -> None:
    print(f"配置: {config_path}")
    print(f"目标版本: {version_text}（{version_source}）")
    print(f"L2 schema: {schema_status}；L3 sing-box check: {check_status}")
    print()
    if not findings:
        print("未发现问题。")
    else:
        order = {"E": 0, "W": 1, "U": 2}
        for finding in sorted(findings, key=lambda item: (order.get(item.level, 3), item.path, item.code)):
            print(f"[{finding.level}] {finding.path}  {finding.message}")
            if finding.doc:
                print(f"     文档: https://sing-box.sagernet.org{finding.doc}")
    errors = sum(1 for item in findings if item.level == "E")
    warnings = sum(1 for item in findings if item.level == "W")
    notes = sum(1 for item in findings if item.level == "U")
    print()
    print(f"结论: {verdict}")
    print(f"错误 {errors} · 警告 {warnings} · 未验证 {notes}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a sing-box JSONC config by target version.")
    parser.add_argument("config", help="config.json / config.jsonc / recipe .md")
    parser.add_argument("--extract", action="store_true", help="extract the first parseable fenced JSONC block from Markdown")
    parser.add_argument("-v", "--version", help="target version, e.g. 1.14.4, or testing")
    parser.add_argument("--schema", help="local schema.json (overrides download)")
    parser.add_argument("--offline", action="store_true", help="use cached schema only")
    parser.add_argument("--no-schema", action="store_true", help="skip JSON Schema validation")
    parser.add_argument("--no-check", action="store_true", help="skip sing-box check")
    parser.add_argument("--sing-box", dest="sing_box", help="path to sing-box binary")
    parser.add_argument("--cache-dir", help="schema cache directory")
    parser.add_argument("--timeout", type=float, default=20.0, help="network / check timeout seconds")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    config_path = Path(args.config).expanduser()
    config, parse_finding = read_config(config_path, extract=args.extract)
    if config is None:
        findings = [parse_finding] if parse_finding else []
        if args.json:
            print(json.dumps({
                "config": str(config_path), "version": args.version or SNAPSHOT_VERSION,
                "verdict": "FAIL", "findings": [item.as_dict() for item in findings],
                "levels": {"parse": "failed"},
            }, ensure_ascii=False, indent=2))
        else:
            print_human(config_path, args.version or SNAPSHOT_VERSION, "无法确定", findings, "skipped", "skipped",
                        "FAIL — 配置未能读取或解析")
        return 2

    binary = args.sing_box or shutil.which("sing-box")
    binary_version = detect_binary_version(binary) if binary else None

    if args.version:
        version_text = args.version.strip()
        version_source = "--version"
    elif os.environ.get("SING_BOX_VERSION"):
        version_text = os.environ["SING_BOX_VERSION"].strip()
        version_source = "SING_BOX_VERSION"
    elif binary_version:
        version_text = binary_version
        version_source = "sing-box version"
    else:
        version_text = SNAPSHOT_VERSION
        version_source = "默认快照（未指定版本）"

    lowered = version_text.lower()
    is_testing = lowered in ("testing", "dev", "latest")
    target = None if is_testing else parse_version(version_text)
    if target is None and not is_testing:
        print(f"警告: 无法解析版本 {version_text!r}；只做语法和引用检查", file=sys.stderr)

    findings: list[Finding] = []
    if version_source.startswith("默认快照"):
        findings.append(Finding(
            "U", "VERSION-ASSUMED", "/",
            f"未指定目标版本，按 {SNAPSHOT_VERSION} 检查；请用 --version 指定用户实际版本",
        ))
    if is_testing:
        findings.append(Finding(
            "U", "VERSION-TESTING", "/",
            "testing/latest 不适用按版本号的废弃/移除规则；请以对应分支文档和 sing-box check 为准",
        ))
    if binary_version and not is_testing and target is not None:
        parsed_binary = parse_version(binary_version)
        if parsed_binary != target:
            findings.append(Finding(
                "W", "VERSION-BINARY", "/",
                f"本机 sing-box 是 {binary_version}，与目标 {version_text} 不同；check 结果只代表本机版本",
            ))

    check_duplicates(config, findings)
    tags = collect_tags(config)
    check_references(config, tags, findings)
    apply_field_rules(config, target, findings)

    schema, schema_source = load_schema(args, version_text, is_testing, target, findings)
    schema_status = "skipped" if args.no_schema else "unavailable"
    if schema is not None:
        schema_status = schema_findings(strip_deprecated_fields(config, target), schema, findings)

    check_status = "skipped"
    if args.no_check:
        findings.append(Finding("U", "CHECK-SKIPPED", "/", "按 --no-check 跳过 sing-box check"))
    elif binary:
        check_status = run_sing_box_check(binary, config_path, args.timeout, findings)
    else:
        check_status = "unavailable"
        findings.append(Finding(
            "U", "CHECK-MISSING", "/",
            "未找到 sing-box 可执行文件；schema 只能证明结构，不能证明程序接受该配置",
            "/configuration/",
        ))

    errors = sum(1 for item in findings if item.level == "E")
    if errors:
        verdict = "FAIL — 有必须修复的错误"
    elif check_status == "passed":
        verdict = "PASS — sing-box check 通过"
    elif schema_status == "passed":
        verdict = "STRUCTURE OK — schema 通过，但未运行 sing-box check（运行时未验证）"
    else:
        verdict = "UNVERIFIED — 未获得可用的 schema 或二进制校验"

    # Avoid a false sense of passing when the config was parsed but no layer ran.
    if args.json:
        print(json.dumps({
            "config": str(config_path),
            "version": version_text,
            "version_source": version_source,
            "binary_version": binary_version,
            "schema_source": schema_source,
            "levels": {"parse": "ok", "schema": schema_status, "check": check_status},
            "verdict": verdict,
            "findings": [item.as_dict() for item in findings],
        }, ensure_ascii=False, indent=2))
    else:
        print_human(config_path, version_text, version_source, findings, schema_status, check_status, verdict)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

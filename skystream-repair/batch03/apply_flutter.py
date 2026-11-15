#!/usr/bin/env python3
"""Batch03: CloudStream -> playback correctness. Apply AFTER Batch02 Flutter patch.

Source-only until Batch04 final Windows installer. Identified regression:
CloudStream subtitle URLs with Cookie headers were routed through the local
proxy without ProxyOptions.keepCookies, so the proxy deliberately deleted
those source cookies before fetching the subtitle file.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "skystream"
target = ROOT / "lib/core/cloudstream/cloudstream_provider.dart"
src = target.read_text(encoding="utf-8")

def patch(before: str, after: str) -> None:
    global src
    count = src.count(before)
    if count != 1:
        raise SystemExit(f"Batch03 expected one anchor; found {count}: {before[:110]}")
    src = src.replace(before, after, 1)

patch(
    """        url = LocalProxyService.instance.getProxyUrl(url, headers: headers);""",
    """        // The proxy discards cookies by default unless the individual
        // cookie names are explicitly allowlisted (the video player already
        // does this). The subtitle belongs to this same media session.
        url = LocalProxyService.instance.getProxyUrl(
          url,
          headers: headers,
          options: ProxyOptions(keepCookies: _cookieNames(headers)),
        );""",
)

patch(
    """  static List<Map<String, dynamic>> _list(Object? value) => [""",
    """  /// Parse the cookie names from the subtitle's own source headers.
  /// Return only names, never values; the proxy receives only the exact
  /// source cookies via sticky headers, not the browser's whole jar.
  static List<String> _cookieNames(Map<String, String> headers) {
    final cookies = <String>{};
    for (final entry in headers.entries) {
      if (entry.key.toLowerCase() != 'cookie') continue;
      for (final part in entry.value.split(';')) {
        final equals = part.indexOf('=');
        if (equals <= 0) continue;
        final name = part.substring(0, equals).trim();
        if (name.isNotEmpty) cookies.add(name);
      }
    }
    return cookies.toList();
  }

  static List<Map<String, dynamic>> _list(Object? value) => [""",
)

target.write_text(src, encoding="utf-8")
test_file = ROOT / "test/core/cloudstream/batch03_playback_contract_test.dart"
test_file.write_text((Path(__file__).parent / "playback_contract_test.dart").read_text(encoding="utf-8"), encoding="utf-8")
native_test = ROOT / "integration_test/cloudstream/fixture_playback_test.dart"
native_test.write_text((Path(__file__).parent / "native_playback_test.dart").read_text(encoding="utf-8"), encoding="utf-8")
print("BATCH03 FLUTTER PATCH APPLIED: subtitle cookies, mapping tests and Windows native integration test")

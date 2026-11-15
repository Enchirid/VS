#!/usr/bin/env python3
"""Batch02 Flutter adapter patch. Apply ONLY when building the complete final app.

The pinned v2.9.0 portable Flutter executable contains old Dart AOT code.
Replacing Java engine JARs alone will NOT apply this Dart handling change.
"""
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent / "skystream"
path = ROOT / "lib/core/cloudstream/cloudstream_provider.dart"
source = path.read_text(encoding="utf-8")
old = """    if (_list(result['links']).isEmpty && result['fullScreen'] == true) throw const ExtensionScreenEnded();
    final subtitles = await _subtitles(_list(result['subtitles']));
    return [
      for (final link in _list(result['links']))"""
new = """    final links = _list(result['links']);
    if (links.isEmpty && result['fullScreen'] == true) throw const ExtensionScreenEnded();
    // The engine now preserves zero-link responses and includes a short,
    // category-only explanation. Keep CloudStream's game/full-screen behavior,
    // but surface safe diagnostics when ordinary extraction returns no links.
    if (links.isEmpty && result['error'] is String && (result['error'] as String).trim().isNotEmpty) {
      throw Cs3EngineException('EmptySources', result['error'] as String);
    }
    final subtitles = await _subtitles(_list(result['subtitles']));
    return [
      for (final link in links)"""
if source.count(old) != 1:
    raise SystemExit(f"Unexpected Flutter adapter layout: {source.count(old)} anchors")
path.write_text(source.replace(old, new, 1), encoding="utf-8")
print("Batch02 Flutter adapter patched, requires a full Flutter Windows rebuild to activate")

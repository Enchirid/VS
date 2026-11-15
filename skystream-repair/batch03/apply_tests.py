#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent/"skystream"
file=ROOT/"test/core/cloudstream/cloudstream_provider_test.dart"
s=file.read_text(encoding="utf-8")
anchor="  group('an HLS link with no quality of its own', () {"
snippet="""  group('Batch 03: link-to-player identity and metadata', () {
    CloudStreamProvider qa(Map<String, dynamic> answer) => CloudStreamProvider(
      plugin: const CsInstalledPlugin(
        info: CsPluginInfo(internalName: 'Fixture', name: 'Fixture', url: '', repositoryUrl: ''),
        filePath: '/plugins/Fixture.cs3',
      ),
      pluginKey: 'qa/Fixture',
      info: const CsProviderInfo(name: 'Fixture'),
      host: _AnsweringHost(answer),
    );
    test('preserves headers and adaptive quality for authorized HLS', () async {
      final streams = await qa({
        'links': [{
          'url': 'https://fixture.invalid/original.m3u8', 'name': 'Master',
          'quality': 400, 'type': 'M3U8',
          'headers': {'User-Agent': 'QA-Agent', 'X-Playback-QA': 'Batch03-Authorized'},
          'referer': 'https://fixture.invalid/authorized',
        }],
      }).loadStreams(CloudStreamProvider.token('original-episode'));
      expect(streams, hasLength(1));
      expect(streams.single.quality, 0);
      expect(streams.single.headers, {
        'User-Agent': 'QA-Agent', 'X-Playback-QA': 'Batch03-Authorized',
        'Referer': 'https://fixture.invalid/authorized',
      });
    });
    test('respects explicit case-insensitive referer and quality', () async {
      final stream = (await qa({'links': [{
        'url': 'https://fixture.invalid/movie.mp4', 'name': 'Direct',
        'quality': 1080, 'type': 'VIDEO',
        'headers': {'referer': 'https://fixture.invalid/original'},
        'referer': 'https://fixture.invalid/fallback',
      }]}).loadStreams(CloudStreamProvider.token('x'))).single;
      expect(stream.headers, {'referer': 'https://fixture.invalid/original'});
      expect(stream.source, contains('1080p'));
    });
    test('retains multiple subtitle languages', () async {
      final stream = (await qa({
        'links': [{'url': 'https://fixture.invalid/movie.m3u8', 'name': 'Video'}],
        'subtitles': [
          {'url': 'https://fixture.invalid/en.srt', 'lang': 'English'},
          {'url': 'https://fixture.invalid/fil.srt', 'lang': 'Filipino'},
        ],
      }).loadStreams(CloudStreamProvider.token('x'))).single;
      expect(stream.subtitles, hasLength(2));
      expect(stream.subtitles!.map((s) => s.lang).toList(), ['English', 'Filipino']);
    });
    test('preserves approved DRM metadata', () async {
      final stream = (await qa({'links': [{
        'url': 'https://fixture.invalid/manifest.mpd', 'name': 'DASH',
        'drm': {'kid': 'qa-kid', 'key': 'qa-key', 'licenseUrl': 'https://fixture.invalid/license'},
      }]}).loadStreams(CloudStreamProvider.token('x'))).single;
      expect(stream.drmKid, 'qa-kid');
      expect(stream.drmKey, 'qa-key');
      expect(stream.licenseUrl, 'https://fixture.invalid/license');
    });
    test('reported empty extraction surfaces diagnostic, old empty answer stays compatible', () async {
      expect(qa({
        'links': <Object?>[], 'error': 'Provider returned no links; diagnostics: HTTP_403=2'
      }).loadStreams(CloudStreamProvider.token('x')),
        throwsA(isA<Cs3EngineException>().having((e) => e.message, 'message', contains('HTTP_403=2'))));
      expect(await qa({'links': <Object?>[]}).loadStreams(CloudStreamProvider.token('x')), isEmpty);
    });
    test('full-screen extension closes quietly even when diagnostics exist', () {
      expect(qa({'links': <Object?>[], 'fullScreen': true, 'error': 'HTTP_403=2'})
        .loadStreams(CloudStreamProvider.token('x')), throwsA(isA<ExtensionScreenEnded>()));
    });
  });

"""
if s.count(anchor)!=1:raise SystemExit("Anchor count mismatch")
file.write_text(s.replace(anchor,snippet+anchor,1),encoding="utf-8")
print("Batch03 Flutter provider playback handoff tests applied")

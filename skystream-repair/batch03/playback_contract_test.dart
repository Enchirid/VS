/// Batch 03: CloudStream link/subtitle mapping and local media delivery.
///
/// All network requests use ephemeral loopback servers; no external streams.
import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:cs3_engine/cs3_engine.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:skystream/core/cloudstream/cloudstream_engine.dart';
import 'package:skystream/core/cloudstream/cloudstream_models.dart';
import 'package:skystream/core/cloudstream/cloudstream_provider.dart';
import 'package:skystream/core/services/local_proxy_service.dart';
import 'package:skystream/features/player/domain/stream_resolver.dart';
import 'package:vlc_player/vlc_player.dart';

class _StubHost extends CloudStreamEngineHost {
  _StubHost(this.answer);
  final Map<String, dynamic> answer;
  @override
  Future<T> run<T>(
    String path,
    Future<T> Function(Cs3Engine engine) call, {
    String kind = 'call',
    String? provider,
    String mainUrl = '',
    String? pluginUrl,
  }) async => answer as T;
}

CloudStreamProvider _provider(Map<String, dynamic> result) => CloudStreamProvider(
  plugin: const CsInstalledPlugin(
    info: CsPluginInfo(internalName: 'Fixture', name: 'Fixture', url: '', repositoryUrl: ''),
    filePath: '/fixtures/Fixture.cs3',
  ),
  pluginKey: 'batch03/Fixture',
  info: const CsProviderInfo(name: 'Fixture'),
  host: _StubHost(result),
);

Future<String> _get(String url) async {
  final client = HttpClient();
  try {
    final request = await client.getUrl(Uri.parse(url));
    final response = await request.close();
    expect(response.statusCode, HttpStatus.ok);
    return await response.transform(utf8.decoder).join();
  } finally {
    client.close(force: true);
  }
}

void main() {
  // Plain test() uses real loopback HttpClient. Widget-test binding forces HTTP 400.
  tearDown(() async => LocalProxyService.instance.shutdown());

  test('link headers, referer, adaptive quality, subtitle language survive mapping', () async {
    final result = await _provider({
      'links': [
        {
          'url': 'http://127.0.0.1:4567/fixture.m3u8',
          'name': 'Fixture',
          'source': 'Synthetic',
          'quality': 400,
          'type': 'M3U8',
          'referer': 'https://example.invalid/player/',
          'headers': {'Authorization': 'Bearer fixture', 'Cookie': 'session=fixture'},
        },
      ],
      'subtitles': [{'url': 'http://127.0.0.1:4567/en.srt', 'lang': 'English'}],
    }).loadStreams(CloudStreamProvider.token('fixture-episode'));

    expect(result, hasLength(1));
    final stream = result.single;
    expect(stream.url, 'http://127.0.0.1:4567/fixture.m3u8');
    expect(stream.headers?['Cookie'], 'session=fixture');
    expect(stream.headers?['Authorization'], 'Bearer fixture');
    expect(stream.headers?['Referer'], 'https://example.invalid/player/');
    expect(stream.quality, 0, reason: 'Unknown-quality HLS must remain adaptive');
    expect(stream.subtitles?.single.lang, 'English');
    final headers = playbackHeaders(stream);
    expect(headers.keys.any((k) => k.toLowerCase() == 'user-agent'), isTrue);
    expect(unsupportedVlcHeaders(headers), contains('Cookie'));
    expect(unsupportedVlcHeaders(headers), contains('Authorization'));
  });

  test('subtitle proxy forwards only the source-supplied cookies', () async {
    final origin = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    addTearDown(() => origin.close(force: true));
    final seen = <String, String?>{};
    origin.listen((request) async {
      seen['path'] = request.uri.path;
      seen['cookie'] = request.headers.value(HttpHeaders.cookieHeader);
      seen['authorization'] = request.headers.value(HttpHeaders.authorizationHeader);
      seen['referer'] = request.headers.value('referer');
      request.response
        ..statusCode = HttpStatus.ok
        ..headers.contentType = ContentType('text', 'vtt', charset: 'utf-8')
        ..write('WEBVTT\n\n00:00:00.100 --> 00:00:02.000\nFixture subtitle\n');
      await request.response.close();
    });

    final base = 'http://127.0.0.1:${origin.port}';
    final streams = await _provider({
      'links': [
        {'url': '$base/video.mp4', 'name': 'Video', 'type': 'VIDEO'},
      ],
      'subtitles': [
        {
          'url': '$base/subtitle.vtt',
          'lang': 'en',
          'headers': {
            'Cookie': 'session=allowed; preference=viewer',
            'Authorization': 'Bearer fixture-token',
            'Referer': 'https://example.invalid/player/',
          },
        },
      ],
    }).loadStreams(CloudStreamProvider.token('fixture'));

    final subtitle = streams.single.subtitles!.single;
    expect(Uri.parse(subtitle.url).host, '127.0.0.1');
    expect(Uri.parse(subtitle.url).path, '/proxy');
    expect(await _get(subtitle.url), contains('Fixture subtitle'));
    expect(seen['path'], '/subtitle.vtt');
    expect(seen['cookie'], contains('session=allowed'));
    expect(seen['cookie'], contains('preference=viewer'));
    expect(seen['authorization'], 'Bearer fixture-token');
    expect(seen['referer'], 'https://example.invalid/player/');
  });

  test('public subtitles remain direct and require no proxy', () async {
    const subtitleUrl = 'https://example.invalid/public.vtt';
    final streams = await _provider({
      'links': [{'url': 'https://example.invalid/film.mp4', 'name': 'Video'}],
      'subtitles': [{'url': subtitleUrl, 'lang': 'en', 'headers': <String, String>{}}],
    }).loadStreams(CloudStreamProvider.token('fixture'));
    expect(streams.single.subtitles!.single.url, subtitleUrl);
  });
}

/// Windows-only Batch03 integration: a synthetic CloudStream provider returns
/// an authorized local media link, mapped via SkyStream into its real local
/// proxy and the actual native libVLC decoder. Not a third-party site test.
///
/// Pass BATCH03_FILM_FILE as an absolute local file path (fixture distributed
/// with upstream vlc_player/example); no media is fetched from the Internet.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:isolate';

import 'package:cs3_engine/cs3_engine.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:skystream/core/cloudstream/cloudstream_engine.dart';
import 'package:skystream/core/cloudstream/cloudstream_models.dart';
import 'package:skystream/core/cloudstream/cloudstream_provider.dart';
import 'package:skystream/core/services/local_proxy_service.dart';
import 'package:skystream/features/player/domain/stream_resolver.dart';
import 'package:vlc_player/vlc_player.dart';

const film = String.fromEnvironment('BATCH03_FILM_FILE');
const allowedReferer = 'https://example.invalid/player/';
const fixtureCookie = 'fixture_session=allowed';

class _FixtureHost extends CloudStreamEngineHost {
  _FixtureHost(this.result);
  final Map<String, dynamic> result;
  @override
  Future<T> run<T>(
    String path,
    Future<T> Function(Cs3Engine engine) call, {
    String kind = 'call',
    String? provider,
    String mainUrl = '',
    String? pluginUrl,
  }) async => result as T;
}

CloudStreamProvider _cloudStream(Uri video, Uri subtitle) => CloudStreamProvider(
  plugin: const CsInstalledPlugin(
    info: CsPluginInfo(internalName: 'Fixture', name: 'Fixture', url: '', repositoryUrl: ''),
    filePath: '/fixtures/Fixture.cs3',
  ),
  pluginKey: 'native/Fixture',
  info: const CsProviderInfo(name: 'Fixture'),
  host: _FixtureHost({
    'completed': true,
    'links': [
      {
        'url': video.toString(),
        'source': 'Fixture',
        'name': 'Windows native H264 fixture',
        'quality': 720,
        'type': 'VIDEO',
        'referer': allowedReferer,
        'headers': {
          'Cookie': fixtureCookie,
          'Authorization': 'Bearer fixture-local',
          'X-Media-Fixture': 'yes',
        },
      },
    ],
    'subtitles': [
      {
        'url': subtitle.toString(),
        'lang': 'English',
        'headers': {
          'Cookie': fixtureCookie,
          'Authorization': 'Bearer fixture-local',
          'Referer': allowedReferer,
        },
      },
    ],
  }),
);

class _FixtureServer {
  _FixtureServer(this._isolate, this.port);
  final Isolate _isolate;
  final int port;
  Uri address(String path) => Uri.parse('http://127.0.0.1:$port$path');
  void close() => _isolate.kill(priority: Isolate.immediate);

  static Future<_FixtureServer> open(String file) async {
    final answer = ReceivePort();
    final isolate = await Isolate.spawn(_serve, [answer.sendPort, file]);
    final port = await answer.first as int;
    answer.close();
    return _FixtureServer(isolate, port);
  }
}

Future<void> _serve(List<Object> args) async {
  final ready = args[0] as SendPort;
  final bytes = await File(args[1] as String).readAsBytes();
  final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
  ready.send(server.port);
  await for (final request in server) {
    unawaited(() async {
      try {
        final headers = request.headers;
        if (headers.value(HttpHeaders.cookieHeader)?.contains(fixtureCookie) != true ||
            headers.value(HttpHeaders.authorizationHeader) != 'Bearer fixture-local' ||
            headers.value('referer') != allowedReferer) {
          request.response.statusCode = HttpStatus.forbidden;
          await request.response.close();
          return;
        }
        if (request.uri.path == '/sub.vtt') {
          request.response
            ..headers.contentType = ContentType('text', 'vtt', charset: 'utf-8')
            ..write('WEBVTT\n\n00:00:00.500 --> 00:00:03.000\nAuthorized test subtitle\n');
          await request.response.close();
          return;
        }
        if (request.uri.path != '/film.mp4' || headers.value('x-media-fixture') != 'yes') {
          request.response.statusCode = HttpStatus.notFound;
          await request.response.close();
          return;
        }
        var start = 0;
        var end = bytes.length - 1;
        final range = headers.value(HttpHeaders.rangeHeader);
        final match = range == null ? null : RegExp(r'bytes=(\d+)-(\d*)').firstMatch(range);
        if (match != null) {
          start = int.parse(match.group(1)!);
          if (match.group(2)!.isNotEmpty) end = int.parse(match.group(2)!);
          if (start >= bytes.length) {
            request.response.statusCode = HttpStatus.requestedRangeNotSatisfiable;
            request.response.headers.set(HttpHeaders.contentRangeHeader, 'bytes */${bytes.length}');
            await request.response.close();
            return;
          }
          if (end >= bytes.length) end = bytes.length - 1;
          request.response
            ..statusCode = HttpStatus.partialContent
            ..headers.set(HttpHeaders.contentRangeHeader, 'bytes $start-$end/${bytes.length}');
        }
        request.response.headers
          ..contentType = ContentType('video', 'mp4')
          ..set(HttpHeaders.acceptRangesHeader, 'bytes');
        request.response.contentLength = end - start + 1;
        request.response.add(bytes.sublist(start, end + 1));
        await request.response.close();
      } catch (_) {
        // libVLC may end a range request early while seeking or stopping.
      }
    }());
  }
}

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('authorized CloudStream link plays through Windows native VLC', (tester) async {
    expect(Platform.isWindows, isTrue, reason: 'CI intentionally runs this test only on Windows');
    expect(film, isNotEmpty, reason: 'Pass --dart-define=BATCH03_FILM_FILE=<absolute fixture path>');
    expect(await File(film).exists(), isTrue);

    final origin = await _FixtureServer.open(film);
    addTearDown(origin.close);
    addTearDown(LocalProxyService.instance.shutdown);

    // Real plugin-to-app mapping; the stub only replaces remote source
    // discovery, never the playback engine or local HTTP proxy.
    final streams = await _cloudStream(
      origin.address('/film.mp4'),
      origin.address('/sub.vtt'),
    ).loadStreams(CloudStreamProvider.token('synthetic-episode'));
    final selected = streams.single;
    final headers = playbackHeaders(selected);
    expect(unsupportedVlcHeaders(headers), contains('Cookie'));
    await LocalProxyService.instance.startServer();
    final proxied = LocalProxyService.instance.getProxyUrl(
      selected.url,
      headers: headers,
      options: ProxyOptions(keepCookies: ['fixture_session']),
    );

    // Confirm the separately protected subtitle follows the exact same
    // authorization path and is not stripped by the local proxy.
    final subtitleUrl = selected.subtitles!.single.url;
    final client = HttpClient();
    try {
      final response = await (await client.getUrl(Uri.parse(subtitleUrl))).close();
      expect(response.statusCode, HttpStatus.ok);
      expect(await response.transform(utf8.decoder).join(), contains('Authorized test subtitle'));
    } finally {
      client.close(force: true);
    }

    final controller = VlcPlayerController(options: const ['--aout=dummy']);
    addTearDown(controller.dispose);
    await tester.pumpWidget(
      MaterialApp(home: Scaffold(body: Center(child: SizedBox(
        width: 480, height: 270, child: VlcPlayer(controller: controller),
      )))),
    );
    for (var i = 0; i < 160 && !controller.isAttached; i++) {
      await tester.pump(const Duration(milliseconds: 250));
    }
    expect(controller.isAttached, isTrue, reason: 'native Windows VLC view did not attach');
    await controller.setMedia(
      VlcMediaSource(uri: Uri.parse(proxied), httpHeaders: headers),
      autoPlay: true,
    );

    for (var i = 0; i < 240 &&
        !controller.value.hasError &&
        controller.value.position < const Duration(seconds: 2); i++) {
      await tester.pump(const Duration(milliseconds: 250));
    }
    expect(controller.value.hasError, isFalse, reason: 'native decoder entered error state');
    expect(controller.value.position, greaterThanOrEqualTo(const Duration(seconds: 2)),
        reason: 'source-to-proxy-to-libVLC playback failed to advance');
    final media = await controller.getMediaInfo();
    expect(
      controller.value.videoSize != null || media.videoTracks.isNotEmpty,
      isTrue,
      reason: 'the native Windows decoder must identify an actual video track',
    );
    // A seek must not silently drop source authorization on the next range request.
    await controller.seekTo(const Duration(seconds: 5));
    for (var i = 0; i < 100 &&
        !controller.value.hasError &&
        controller.value.position < const Duration(seconds: 5); i++) {
      await tester.pump(const Duration(milliseconds: 250));
    }
    expect(controller.value.hasError, isFalse);
    expect(controller.value.position, greaterThanOrEqualTo(const Duration(seconds: 5)));
    await controller.stop();
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump(const Duration(milliseconds: 100));
  }, timeout: const Timeout(Duration(minutes: 8)));
}

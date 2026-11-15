/// Batch 03 native Windows codec regression, using only SkyStream's own test fixtures.
/// No external media hosts are contacted; audio output uses libVLC's dummy sink.
///
/// BATCH03_AUDIO_FILE: audio.mp3
/// BATCH03_HLS_FILE: playlist.m3u8, beside segment.ts on local disk.
library;

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:vlc_player/vlc_player.dart';

const audioFile = String.fromEnvironment('BATCH03_AUDIO_FILE');
const hlsFile = String.fromEnvironment('BATCH03_HLS_FILE');

Future<VlcPlayerController> _attached(WidgetTester tester) async {
  final controller = VlcPlayerController(options: const ['--aout=dummy']);
  addTearDown(controller.dispose);
  await tester.pumpWidget(MaterialApp(home: Scaffold(body: Center(child: SizedBox(
    width: 400, height: 225, child: VlcPlayer(controller: controller),
  )))));
  for (var i = 0; i < 160 && !controller.isAttached; i++) {
    await tester.pump(const Duration(milliseconds: 250));
  }
  expect(controller.isAttached, isTrue, reason: 'native libVLC surface failed to attach');
  return controller;
}

Future<void> _close(WidgetTester tester, VlcPlayerController controller) async {
  await controller.stop();
  await tester.pumpWidget(const SizedBox.shrink());
  await tester.pump(const Duration(milliseconds: 100));
}

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('Windows libVLC recognizes and plays an authorized local MP3 audio fixture', (tester) async {
    expect(Platform.isWindows, isTrue);
    expect(audioFile, isNotEmpty);
    expect(await File(audioFile).exists(), isTrue);
    final controller = await _attached(tester);
    await controller.setMedia(VlcMediaSource(uri: File(audioFile).uri), autoPlay: true);

    var hasAudio = false;
    for (var i = 0; i < 80 && !controller.value.hasError && !hasAudio; i++) {
      await tester.pump(const Duration(milliseconds: 250));
      try {
        final info = await controller.getMediaInfo();
        hasAudio = info.audioTracks.isNotEmpty;
      } catch (_) {
        // Media metadata may not exist until the native demuxer opens.
      }
    }
    expect(controller.value.hasError, isFalse);
    expect(hasAudio, isTrue, reason: 'native backend failed to identify the MP3 audio track');
    await _close(tester, controller);
  }, timeout: const Timeout(Duration(minutes: 5)));

  testWidgets('Windows libVLC opens a local HLS playlist and MPEG-TS video segment', (tester) async {
    expect(Platform.isWindows, isTrue);
    expect(hlsFile, isNotEmpty);
    expect(await File(hlsFile).exists(), isTrue);
    expect(await File(File(hlsFile).parent.path + Platform.pathSeparator + 'segment.ts').exists(), isTrue);
    final controller = await _attached(tester);
    await controller.setMedia(VlcMediaSource(uri: File(hlsFile).uri), autoPlay: true);

    var hasVideo = false;
    for (var i = 0; i < 100 && !controller.value.hasError && !hasVideo; i++) {
      await tester.pump(const Duration(milliseconds: 250));
      try {
        final info = await controller.getMediaInfo();
        hasVideo = info.videoTracks.isNotEmpty || controller.value.videoSize != null;
      } catch (_) {
        // The HLS manifest and first segment can still be loading.
      }
    }
    expect(controller.value.hasError, isFalse);
    expect(hasVideo, isTrue, reason: 'native Windows HLS pipeline failed to identify a video track');
    await _close(tester, controller);
  }, timeout: const Timeout(Duration(minutes: 5)));
}

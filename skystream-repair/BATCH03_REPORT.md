# SkyStream Windows — Batch 03 Playback Verification (2026-11-15)

## Result
**Batch 03 controlled playback regression suite: PASS.** Both native Windows VLC media fixture tests and the additional Flutter/authorized HLS transport tests passed. **Real StreamPlay v687/v709 external extraction remains UNVERIFIED**, so this report does not claim that the user's original 'No streams found' issue has been resolved.

## Source baseline
- Pinned upstream `akashdh11/skystream` tag `v2.9.0`.
- Cumulative branch `Enchirid/VS:skystream-windows-repair-20261115`.
- Preserve Batch 01 JVM repair and Batch 02 privacy-safe source diagnostics.
- No intermediate installer is requested or published for Batch 03.

## Existing native Windows verification — successful
GitHub Actions: https://github.com/Enchirid/VS/actions/runs/43701853735
- Full Windows Flutter adapter/proxy/header/subtitle regressions passed.
- Bundled Java sidecar runtime task passed.
- Actual native Windows VLC tested using upstream licensed local MP4 fixture: passed.
- Actual native Windows MP3 and HLS fixture playback: passed.
- This isolated test does not call external StreamPlay hosts.
- Existing Batch 03 patch `skystream-repair/batch03/apply_flutter.py` fixes a concrete issue: subtitle requests carrying a source-provided Cookie header were proxied without allowing those cookie names, so subtitle origin rejected them. New code uses `ProxyOptions(keepCookies: _cookieNames(headers))` to retain only cookie names supplied by the subtitle link, not the browser's complete jar.
- Existing tests: `batch03/playback_contract_test.dart`, `native_playback_test.dart`, and `native_format_smoke_test.dart`.

## Additional Batch 03 tests — successful
GitHub Actions: https://github.com/Enchirid/VS/actions/runs/43704143857
Both jobs succeeded:
1. Flutter link-to-player test suite on pinned Flutter 3.47.7:
   - Tests adapted `CloudStreamProvider.loadStreams()` final Flutter source behavior from Batch 02 and additional Batch 03 mapping cases.
   - Preserves episode tokens, HLS adaptive quality, provider referer/authorization/UA headers, explicitly supplied referer precedence, multiple language subtitle URLs, and licensed test DRM metadata without mutating link identity.
   - Confirms zero-link diagnostic errors are surfaced without breaking legacy empty responses or CloudStream's full-screen game behavior.
   - Also passes player media option, buffer/recovery, sidecar subtitle replay, and seek-not-stall tests.
2. Windows original-media fixture:
   - Generates original 4-second video/test tone with FFmpeg and serves a 4-segment HLS manifest and original subtitle from a temporary local server.
   - Requires an explicit request header; requests without it are rejected with HTTP 403.
   - Every segment fetch succeeds with authorized headers.
   - FFprobe identifies video and audio tracks; the original subtitle file downloads successfully.
   - Test's output explicitly sets `guiVlcPlaybackTested=false`, because this second job tests the transport layer; the **separate native integration workflow above** tests VLC itself.
   - No media from unlicensed external hosts is fetched.

## New source artifacts
- `skystream-repair/batch03/apply_tests.py`: extra Flutter-provider tests added to the upstream provider test file during CI.
- `skystream-repair/batch03/local_playback_fixture.py`: original test video/audio, protected HTTP HLS server, segment access validation, and subtitle fetch.
- `.github/workflows/skystream-batch03-tests.yml`: repeatable pinned Flutter 3.47.7 + Windows FFmpeg CI workflow.
- `skystream-repair/batch03/apply_flutter.py`: existing native subtitle source-cookie fix (ensure final Batch 04 build applies this after Batch 02 adapter).

## Open issue and acceptance boundaries
The user's original problem is StreamPlay returning zero playable links from external sources on their Windows laptop. No CI test here has proven that StreamPlay sources return external video links. Bytecode conversion/registration and downstream playback have been separately verified, so remaining failure possibilities include unsupported desktop network/browser APIs, source-site changes, account settings, and runtime differences. Existing Batch 02 structured diagnostic instrumentation can help distinguish them once observed.

Tests do not establish real-user UI launch, hardware decoding, all subtitle combinations, TV fullscreen behavior, or the state of third-party streaming websites. These cannot be claimed resolved without specific verification.

## Batch 04 next
- Produce one final Windows EXE only after merging Batch 01 JVM engine, Batch 02 diagnostic changes, Batch 02 Flutter diagnostics adapter, and Batch 03 subtitle-cookie fix into the pinned source.
- Use the upstream Flutter executable/build pipeline, not the invisible-window Go launcher.
- Validate Windows runtime, native VLC, extension scanner, and startup of the actual packaged EXE.
- Include GPL-3.0 attribution/source and checksums.
- Clearly label external StreamPlay playback as not verified if the final build has no actual authorized source-link test. Do not promise guaranteed streaming availability.

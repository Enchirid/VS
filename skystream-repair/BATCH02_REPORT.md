# SkyStream Windows — Batch 02: Extraction Diagnostics & Version Compatibility
Date: 2026-11-15
Branch: skystream-windows-repair-20261115

## Status
**Batch 02 source changes and automated tests complete. External StreamPlay source resolution is NOT proven repaired.** No intermediate Windows installer is being delivered in this batch, per the user's revised four-batch protocol.

## Original user case (known, not inferred)
- Windows SkyStream v2.9.0 initial installation: StreamPlay v687 from Adam Knight installed and selected; catalogue and episodes visible; playback shows "No streams found".
- Experimental v2.9.0.2: Windows GUI launches; improved error says StreamPlay completed extraction with zero playable links.
- User has not established success from an actual video stream after Batch01; source site/network cause remains unknown.

## Exact tested artifacts
- SkyStream upstream pinned tag: akashdh11/skystream v2.9.0.
- Adam Knight StreamPlay v687:
  - Repository entry: admknight/CloudstreamExtensions builds/plugins.json.
  - Original pinned binary: https://raw.githubusercontent.com/phisher98/cloudstream-extensions-phisher/3b67c552158a9dc0f898069974a3a9838743bd64/StreamPlay.cs3
  - SHA-256: fc779f9c8e07afba3cca8a9c63c58cd3c40b514cbb4369b6115ad466bf3eca00
  - Size: 1,957,398 bytes.
- Upstream StreamPlay v709:
  - Binary: https://raw.githubusercontent.com/phisher98/cloudstream-extensions-phisher/refs/heads/builds/StreamPlay.cs3
  - SHA-256: b4ad26b1d2f18cd30450e4dd75242dd8bfcaf475e30dcca4924613abe9f5397e
  - Size: 2,181,036 bytes.
- Never conflate v687 with v709. They are distinct binaries.

## Technical root cause of the generic empty-result error
Pinned CloudStream library src:
\`library/src/commonMain/kotlin/com/lagradost/cloudstream3/ParCollections.kt\` and \`mvvm/ArchComponentExt.kt\`.
- \`runAllAsync\` catches individual extractor exceptions and calls \`logError\`, so the enclosing \`MainAPI.loadLinks\` can complete and produce zero callbacks without surfacing its internal failures.
- \`logError\` writes to \`com.lagradost.api.Log.d("ApiError", ...)\` and writes the stack trace to \`System.err\`.
- SkyStream's previous errors reported only final zero links (Batch01's exception also broke certain full-screen/game response tests). The root source/HTTP failure on the user's machine remains unobserved.

## Batch 02 implementation (source-only)
1. \`skystream-repair/batch02/ExtractionDiagnostics.kt\`
   - Per-invocation coroutine-scoped diagnostics; child coroutines that inherit the scope are correlated with their originating \`loadLinks\` request.
   - Collects bucketed HTTP response statuses, allowlisted exception types, and bounded StreamPlay extractor method names recovered from stack-frame lines.
   - Never saves URL strings, query tokens, cookies, headers, request/response bodies, full stack traces or arbitrary third-party text in the structured report.
   - Count/category caps avoid unbounded accumulation.
2. \`skystream-repair/batch02/apply.py\`
   - Adds a JVM-only observer to the \`android.util.Log\` stand-in without requiring a new method on the real Android framework.
   - Instruments \`ClearanceInterceptor\` and its CloudflareKiller path to count status categories and IO exception classes on the shared HTTP clients (no bypass of access checks).
   - Adds a bounded stderr stack-frame observer to the JVM Main.kt sidecar; does not modify the actual Flutter launcher.
   - Returns \`diagnostics\` and \`providerReportedSuccess\` in the CloudStream engine link response.
   - Preserves original \`completed\` and \`fullScreen\` protocol behavior; zero links is a response with \`error\` details, not a thrown JVM exception. The v2.9.0.2 / Batch01 generic throw had broken two upstream EngineUi tests.
   - Corrects a pre-existing Windows-only absolute-path expectation in the upstream KeptWindows regression test; production identity code unchanged.
3. \`skystream-repair/batch02/ExtractionDiagnosticsTest.kt\`
   - Covers HTTP codes, allowlisted errors, log-hook availability, concurrent coroutine separation, bounded categories, private URL/token redaction, and safe source-method capture.
4. \`skystream-repair/batch02/ExtractionPipelineTest.kt\`
   - Exercises fake provider callback returning a synthetic \`example.invalid\` M3U8 URL, provider success flag, empty-provider false return, and safe error diagnostics. No real copyrighted media accessed.
5. \`skystream-repair/batch02/apply_flutter.py\`
   - STAGED for final full Flutter Windows build: if no links and engine error exists, convert safe \`error\` field into a \`Cs3EngineException\` for SkyStream's error presentation, without changing game/full-screen handling.
   - The pinned v2.9.0 Flutter executable contains old Dart AOT code. This adapter change is NOT active merely by replacing Java JARs.

## Verified automated tests and version comparison
GitHub Windows Actions run: https://github.com/Enchirid/VS/actions/runs/43699290831
**Conclusion: SUCCESS.**
- Applied Batch01 and Batch02 patches to pristine pinned SkyStream v2.9.0 source.
- Passed \`:app-shims:test :engine-core:test :engine-jvm:test :engine-jvm:dist\` on Windows JDK 21 + Android 36.
- Passed SHA verification of both published v687 and v709 StreamPlay binaries.
- v687 scan:
  - \`ok=true\`, \`providers=2\`, \`dexClasses=1972\`, \`jvmClasses=1972\`,
    \`failedMethods=0\`, \`incomplete=false\`, \`outOfMemory=false\`, \`convertMs=64155\`.
  - \`invokeMovieBox\` retried via Batch01's aggressive register coloring.
- v709 scan:
  - \`ok=true\`, \`providers=2\`, \`dexClasses=2239\`, \`jvmClasses=2239\`,
    \`failedMethods=0\`, \`incomplete=false\`, \`outOfMemory=false\`, \`convertMs=46624\`.
  - \`invokeMovieBox\` retried via Batch01's aggressive register coloring.
- Full source build and JVM tests passed; these scans exercise conversion/registration, NOT live video extraction.
- CI test outputs retained as GitHub Actions artifacts.

## Known limitations
- Zero failed bytecode methods does NOT mean StreamPlay's external scrapers can access all providers or return links.
- Network diagnostics cover CloudStream's shared HTTP clients and inheriting coroutine contexts; independently constructed HTTP clients, detached threads and external DRM flows can remain outside the scope.
- No authorized end-to-end network playback on the user's Windows device has been run after these patches.
- The earlier installed v2.9.0.2 continues to use its old engine and GUI. No intermediate EXE should be requested of the user.
- The Batch02 Flutter adapter is not yet compiled into an EXE; full Flutter build is reserved for final packaging.

## Next task — Batch 03 (Playback verification)
- Use licensed or public-domain test media and a deterministic test fixture for end-to-end link -> player verification, including video, audio, headers, referer, subtitles, skips, buffering.
- Run a Windows JVM sidecar integration test that verifies engine's JSON contract and safe error reports.
- If real StreamPlay returns zero links, use the captured diagnostic categories to identify reproducible platform API/network compatibility faults. Fix supported API implementation; do not promise access to third-party or restricted sites.
- Regression-test the original SkyStream Flutter entrypoint and avoid the broken 2.9.0.1 Go wrapper.

## Final packaging rule — Batch 04
- Apply both Python patches and the Flutter adapter to the pinned full SkyStream source.
- Compile using GitHub Windows runner; verify the GUI launches, and package a normal one-click Windows installer.
- Maintain attribution and GPL-3.0 obligations for SkyStream, CloudStream and adapted cs3d conversion code.
- Deliver ONE final EXE (plus checksum and source) once playback testing and packaging verification pass; no intermediate user installation required.

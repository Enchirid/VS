# SkyStream Windows — Batch 01 Engineering Report (2026-11-15)

## Status
**Batch 01 source and compatibility tests passed.** Windows EXE packaging is managed separately in `.github/workflows/skystream-windows-batch01.yml`. This is a **JVM compatibility fix, NOT a verified StreamPlay playback fix.**

### Pinned inputs
- SkyStream upstream: `akashdh11/skystream`, tag `v2.9.0`.
- Native Windows portable ZIP SHA-256: `99864dd0f75b403efde2e6f8e683ad0191717a23c82723685a22755585b26dbe`.
- Test extension: `phisher98/cloudstream-extensions-phisher` builds/StreamPlay.cs3, manifest **v709**, SHA-256 `B4AD26B1D2F18CD30450E4DD75242DD8BFCAF475E30DCCA4924613ABE9F5397E`. Do not equate this with the user's previously installed **v687**.
- Earlier user Windows release `2.9.0.2` launches but `StreamPlay.loadLinks` returns 0 links. No playback repair proven on this machine.

### Reproduced upstream defects
1. v709 `java.lang.NoSuchFieldError: com.lagradost.cloudstream3.plugins.Plugin.$stable`.
2. After adding the field: `java.lang.ClassFormatError: Absent Code attribute in com/phisher98/StreamPlayExtractor`.
3. Instrumented converter identified the root: `org.objectweb.asm.MethodTooLargeException` for `StreamPlayExtractor.invokeMovieBox` — JVM single-method Code limit (65,535 bytes), **not** heap exhaustion.
4. The v709 original conversion produced 2239/2239 classes but **two recorded failures** (one translation failure plus one missing-body repair), marked incomplete.

### Implemented changes
- `skystream-repair/patch_engine.py`: reproducible pinned upstream patch; makes `Plugin.$stable` available, sets cache version 7, allows safe migration only from complete and structurally valid older cache, logs sanitized failed method signatures, adds explicit missing-method-body exception fallback, maintains v2.9.0.2 human-readable error reporting.
- `skystream-repair/src/MissingMethodCode.kt`: repairs invalid concrete JVM methods with missing Code attributes by installing an explicit throwing placeholder **and marking the conversion incomplete**; never silently counts such methods as playable.
- `skystream-repair/src/MissingMethodCodeTest.kt`: regression coverage for invalid methods, already-valid methods, native/abstract methods, and exact `Plugin.$stable` JVM field.
- `skystream-repair/shrink_large_methods.py`: targeted oversized-method retry; normal methods use SkyStream's original converter. Large methods invoke a Java ASM size probe, then use aggressive copy-coalescing register allocation only when over the limit.
- `skystream-repair/src/transformers/{Liveness.java,LowMemUnSSATransformer.java,LowMemRegAssignTransformer.java}`: GPL-3.0 adaptation of existing cs3d desktop DEX conversion components, with source attribution: https://github.com/lelouchcodes11/cs3d.
- No removal of upstream license, UI branding, metadata, or provider sources.

### Verified results
- **Run:** https://github.com/Enchirid/VS/actions/runs/43696308569 — **SUCCESS**.
- Full `:engine-jvm:test :engine-jvm:dist` stage succeeded. Existing migration tests and new JVM tests pass.
- Real StreamPlay v709 scan with Java 21 on Windows runner, `-Xmx6g`, reports:
  - `ok=true`
  - `providers=2`
  - `dexClasses=2239`
  - `jvmClasses=2239`
  - `failedMethods=0`
  - `incomplete=false`
  - `outOfMemory=false`
  - `convertMs=44850`
- Important log: `[CS3-SIZE] Retrying invokeMovieBox with aggressive register coloring`.

### Not yet verified
- StreamPlay v687 compatibility on the user's laptop.
- Whether v709 extraction actually returns media links (the scan only loads and registers providers).
- Browser/network/HTTP request handling, cookies, redirects, extension-level source settings, source reliability, subtitles, and real playback.
- The unmodified Flutter GUI still runs as original `skystream.exe` in the installer. Never reinstate the previous short-lived Go launch wrapper; v2.9.0.1 was invisible in Task Manager while apparently running.

### Next — Batch 02
- Run a lawful test video end-to-end on Windows using the v2.9.0.3 QA installer.
- Add protected structured diagnostics for individual extractor/network failures that StreamPlay's `runAllAsync()` may swallow; redact URLs/cookies/tokens.
- Compare v687 vs v709 behavior and review extension settings persistence.
- Fix only reproduced platform APIs or request mapping faults. Never represent a generic "No streams found" error as proof a particular host is down.
- Advance to Batch 03 playback testing and Batch 04 final Windows installer only after verified improvements.

### Build rule
The user does **not** want to compile Windows binaries manually. Use GitHub Actions on Windows to produce an actual installer EXE. Publish only after a successful workflow and checksum verification. For test builds, clearly label incomplete playback validation.

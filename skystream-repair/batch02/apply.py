#!/usr/bin/env python3
"""Batch 02, source-only CloudStream extraction diagnostics on pinned SkyStream v2.9.0.

This patch must run AFTER batch01 patch_engine.py. All replacements are strict,
so an upstream change cannot silently create a partial repair.
"""
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent / "skystream"

def patch(path: str, replacements: list[tuple[str, str]]) -> None:
    target = ROOT / path
    source = target.read_text(encoding="utf-8")
    for before, after in replacements:
        if source.count(before) != 1:
            raise SystemExit(f"Batch02 expected one match in {path}: {before[:140]!r}; found {source.count(before)}")
        source = source.replace(before, after, 1)
    target.write_text(source, encoding="utf-8")
    print(f"Batch02 patched {path}")

shims = "packages/cs3_engine/engine"
diagnostics = ROOT / shims / "app-shims/src/main/kotlin/dev/akash/cs3engine/host/ExtractionDiagnostics.kt"
shutil.copyfile(HERE / "ExtractionDiagnostics.kt", diagnostics)

patch(
    f"{shims}/android-stubs/src/main/java/android/util/Log.java",
    [
        (
            "import java.io.StringWriter;",
            """import java.io.StringWriter;
import java.util.function.BiConsumer;""",
        ),
        (
            "    private Log() {}",
            """    private Log() {}

    /** Optional JVM-only subscriber: listener receives raw text transiently, stores only categories. */
    private static volatile BiConsumer<Integer, String> diagnosticObserver;
    public static void setDiagnosticObserver(BiConsumer<Integer, String> observer) {
        diagnosticObserver = observer;
    }""",
        ),
        (
            """        System.err.println(line);
        return line.length();""",
            """        System.err.println(line);
        BiConsumer<Integer, String> observer = diagnosticObserver;
        if (observer != null) {
            try { observer.accept(priority, line); }
            catch (RuntimeException ignored) { /* diagnostics must never break extension logging */ }
        }
        return line.length();""",
        ),
    ],
)

patch(
    f"{shims}/app-shims/src/main/kotlin/dev/akash/cs3engine/host/ClearanceInterceptor.kt",
    [
        (
            """    override fun intercept(chain: Interceptor.Chain): Response = intercept(chain, ::isChallenge)""",
            """    override fun intercept(chain: Interceptor.Chain): Response = recordResult { intercept(chain, ::isChallenge) }

    /** Records only response status or network exception category, never its URL or credentials. */
    private inline fun recordResult(call: () -> Response): Response {
        return try {
            call().also { ExtractionDiagnostics.httpStatus(it.code) }
        } catch (e: IOException) {
            ExtractionDiagnostics.networkFailure(e)
            throw e
        }
    }""",
        ),
        (
            """    internal fun interceptForKiller(chain: Interceptor.Chain): Response = intercept(chain, ::isRefusal)""",
            """    internal fun interceptForKiller(chain: Interceptor.Chain): Response = recordResult { intercept(chain, ::isRefusal) }""",
        ),
    ],
)

engine_file = f"{shims}/engine-core/src/main/kotlin/dev/akash/cs3engine/Engine.kt"
patch(
    engine_file,
    [
        (
            "import dev.akash.cs3engine.host.ClearanceInterceptor",
            """import dev.akash.cs3engine.host.ClearanceInterceptor
import dev.akash.cs3engine.host.ExtractionDiagnostics""",
        ),
        (
            """        NewPipeDownloader.install()""",
            """        NewPipeDownloader.install()
        // Optional JVM-only Android Log hook; Android's framework remains untouched.
        ExtractionDiagnostics.installJvmLogHook()""",
        ),
        (
            """        val subtitles = Collections.synchronizedList(mutableListOf<Map<String, Any?>>())
        val call = pluginScope.async {
            api.loadLinks(data, false, { subtitles += Mappers.subtitle(it) }, { links += Mappers.link(it) })
        }""",
            """        val subtitles = Collections.synchronizedList(mutableListOf<Map<String, Any?>>())
        val diagnostics = ExtractionDiagnostics.start()
        val call = pluginScope.async {
            // Scope survives inherited child coroutines in third-party runAllAsync.
            // Independent raw threads / HTTP clients may escape this context.
            withContext(ExtractionDiagnostics.context(diagnostics)) {
                api.loadLinks(data, false, { subtitles += Mappers.subtitle(it) }, { links += Mappers.link(it) })
            }
        }""",
        ),
        (
            """        val finished = try {
            BrokerClock.shared.await(call, timeoutMs, standStill = standStill(plugin)).also { finished -> if (finished) call.await() }""",
            """        var providerSuccess: Boolean? = null
        val finished = try {
            BrokerClock.shared.await(call, timeoutMs, standStill = standStill(plugin)).also { finished ->
                if (finished) providerSuccess = call.await()
            }""",
        ),
        (
            """            "completed" to finished,
            "error" to failure?.let { Json.rootCause(it).message ?: it.toString() },""",
            """            "completed" to finished,
            "providerReportedSuccess" to providerSuccess,
            "diagnostics" to diagnostics.snapshot(),
            "error" to failure?.let { Json.rootCause(it).message ?: it.toString() },""",
        ),
        (
            """            if (!finished) throw TimeoutException(
                "${api.name} produced no links before the ${timeoutMs / 1000}s extension deadline"
            )
            throw IllegalStateException(
                "${api.name} completed extraction with no playable links; check its sources or desktop compatibility"
            )""",
            """            val status = if (providerSuccess == true) "true" else if (providerSuccess == false) "false" else "unknown"
            val safe = diagnostics.summary()
            // Preserve CloudStream's original protocol: zero links is a completed response,
            // not a thrown JVM exception. Extension games, waiting windows and callers that
            // inspect completed/fullScreen rely on that behavior.
            answer["error"] = if (!finished)
                "${api.name} produced no links before the ${timeoutMs / 1000}s extension deadline; diagnostics: $safe"
            else
                "${api.name} completed extraction with no playable links; extension returned $status; diagnostics: $safe" """,
        ),
    ],
)

# Capture the safe exception and source-method categories hidden by
# CloudStream logError(Throwable.printStackTrace()); leave existing stderr
# output behavior intact and only inspect stack-line text transiently.
patch(
    f"{shims}/engine-jvm/src/main/kotlin/dev/akash/cs3engine/jvm/Main.kt",
    [
        (
            "import dev.akash.cs3engine.host.HostHooks",
            """import dev.akash.cs3engine.host.HostHooks
import dev.akash.cs3engine.host.ExtractionDiagnostics""",
        ),
        (
            """    System.setErr(PrintStream(FileOutputStream(FileDescriptor.err), true, "UTF-8"))
    System.setOut(System.err)""",
            """    val diagnosticErr = object : PrintStream(FileOutputStream(FileDescriptor.err), true, "UTF-8") {
        override fun println(x: Any?) {
            if (x != null) ExtractionDiagnostics.stderrLine(x.toString())
            super.println(x)
        }
        override fun println(x: String?) {
            if (x != null) ExtractionDiagnostics.stderrLine(x)
            super.println(x)
        }
    }
    System.setErr(diagnosticErr)
    System.setOut(System.err)""",
        ),
    ],
)

# Upstream KeptWindowsTest assumes a Unix-rooted File is absolute on Windows.
# The production keeper keys plugins by absolutePath; test that invariant on both OSes.
patch(
    f"{shims}/engine-core/src/test/kotlin/dev/akash/cs3engine/ui/KeptWindowsTest.kt",
    [
        (
            """        assertEquals(plugin, kept.gone { it == "a" })""",
            """        assertEquals(plugin.absoluteFile, kept.gone { it == "a" })""",
        ),
    ],
)

tests = ROOT / shims / "app-shims/src/test/kotlin/dev/akash/cs3engine/host/ExtractionDiagnosticsTest.kt"
shutil.copyfile(HERE / "ExtractionDiagnosticsTest.kt", tests)
engine_tests = ROOT / shims / "engine-core/src/test/kotlin/dev/akash/cs3engine/ExtractionPipelineTest.kt"
shutil.copyfile(HERE / "ExtractionPipelineTest.kt", engine_tests)
print("BATCH02 SOURCE PATCH COMPLETE: bounded extraction diagnostics plus synthetic callback regression")

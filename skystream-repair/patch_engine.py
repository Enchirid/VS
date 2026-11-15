#!/usr/bin/env python3
"""Reproducible experimental fixes for SkyStream v2.9.0's Windows CS3 engine.

This patch only changes the bundled Java extension engine. It does not change
Flutter UI, payment/account code, CloudStream provider URLs, or media catalogs.
GitHub source upstream: https://github.com/akashdh11/skystream
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "skystream"


def patch(rel_path: str, changes: list[tuple[str, str]]) -> None:
    path = ROOT / rel_path
    text = path.read_text(encoding="utf-8")
    for before, after in changes:
        actual = text.count(before)
        if actual != 1:
            raise SystemExit(f"FAILED {rel_path}: patch expected one match, got {actual}: {before[:96]!r}")
        text = text.replace(before, after, 1)
    path.write_text(text, encoding="utf-8")
    print(f"PATCHED {rel_path} ({len(changes)} changes)")


patch(
    "packages/cs3_engine/engine/engine-jvm/src/main/kotlin/dev/akash/cs3engine/jvm/Dex2Jar.kt",
    [
        (
            "internal const val CACHE_VERSION = 5",
            "internal const val CACHE_VERSION = 7",
        ),
        (
            "private val converting = Semaphore(2)",
            # Limit peak heap pressure when large plugins are converting.
            "private val converting = Semaphore(1)",
        ),
        (
            '            carryOver(File(cacheRoot, "v${CACHE_VERSION - 1}/$hash"), root, dir)?.let { return it }',
            """            // Repair v7: rebuild original DEX, not the v6 cache, so we
            // can identify and quarantine missing JVM method bodies.
            // Never carry over incomplete older jars.""",
        ),
    ],
)


patch(
    "packages/cs3_engine/engine/engine-jvm/src/main/kotlin/dev/akash/cs3engine/jvm/Dex2Jar.kt",
    [
        (
            "                val visitors = classWriters(frames, parents, handler, interfaces) { name, bytes -> output[i] = name to localClasses.fix(name, bytes) }",
            """                val visitors = classWriters(frames, parents, handler, interfaces) { name, bytes ->
                    val fixed = MissingMethodCode.repair(localClasses.fix(name, bytes))
                    if (fixed.missing.isNotEmpty()) {
                        failedMethods.addAndGet(fixed.missing.size)
                        System.err.println("[CS3-CODE] ${fixed.missing.size} missing method bodies in $name; first=${fixed.missing.first()}")
                    }
                    output[i] = name to fixed.bytes
                }""",
        ),
    ],
)

patch(
    "packages/cs3_engine/engine/app-shims/src/main/kotlin/com/lagradost/cloudstream3/plugins/Plugin.kt",
    [
        (
            "abstract class Plugin : BasePlugin() {",
            """abstract class Plugin : BasePlugin() {
    // Compiled extensions compiled with Compose expect this exact JVM static field.
    companion object {
        const val `$stable`: Int = 0
    }""",
        ),
    ],
)

# Install the same testable bytecode repair class in the actual JVM module.
import shutil
patch_root = Path(__file__).resolve().parent
jvm_root = ROOT / "packages/cs3_engine/engine/engine-jvm/src"
destination = jvm_root / "main/kotlin/dev/akash/cs3engine/jvm/MissingMethodCode.kt"
shutil.copyfile(patch_root / "src/MissingMethodCode.kt", destination)
test_dest = jvm_root / "test/kotlin/dev/akash/cs3engine/jvm/MissingMethodCodeTest.kt"
test_dest.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(patch_root / "src/MissingMethodCodeTest.kt", test_dest)
print("INSTALLED bytecode sanitizer + JVM regression tests")

patch(
    "packages/cs3_engine/engine/engine-jvm/src/main/kotlin/dev/akash/cs3engine/jvm/JvmPluginLoader.kt",
    [
        (
            """        return PreparedPlugin(PluginClassLoader(conversion.jar, file, framework, conversion.interfaces), conversion.notes())""",
            """        if (conversion.incomplete) {
            // Filename and conversion counts only: avoid logging provider URLs or credentials.
            System.err.println("[CS3-REPAIR] Incomplete JVM conversion for ${file.name}: ${conversion.notes()}")
        }
        return PreparedPlugin(PluginClassLoader(conversion.jar, file, framework, conversion.interfaces), conversion.notes())""",
        )
    ],
)

patch(
    "packages/cs3_engine/engine/engine-core/src/main/kotlin/dev/akash/cs3engine/Engine.kt",
    [
        (
            """        if (plugin != null && ui.fullScreenEndedWith(plugin, since, quietEndMs)) answer["fullScreen"] = true
        return answer""",
            """        val fullScreen = plugin != null && ui.fullScreenEndedWith(plugin, since, quietEndMs)
        if (found.isEmpty() && !fullScreen) {
            // Distinguish an incomplete resolver from a completed request with no
            // playable links. Prior releases surfaced both as "No streams found".
            if (!finished) throw TimeoutException(
                "${api.name} produced no links before the ${timeoutMs / 1000}s extension deadline"
            )
            throw IllegalStateException(
                "${api.name} completed extraction with no playable links; check its sources or desktop compatibility"
            )
        }
        if (fullScreen) answer["fullScreen"] = true
        return answer""",
        )
    ],
)

print("SOURCE PATCH COMPLETE: v7 converter + ABI shim + bytecode repair + regression tests")

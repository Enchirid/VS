#!/usr/bin/env python3
"""Port cs3d's conservative JVM oversized-method retry into pinned SkyStream.

Adapts GPL-3.0 sources from https://github.com/lelouchcodes11/cs3d.
Recompiles ONLY methods that cannot fit in a JVM Code attribute; ordinary
methods continue through SkyStream's original dex2jar pipeline unchanged.
"""
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE / "skystream"
JVM = ROOT / "packages/cs3_engine/engine/engine-jvm"
TARGET = JVM / "src/main/kotlin/dev/akash/cs3engine/jvm/Dex2Jar.kt"


def strict_replace(content: str, before: str, after: str) -> str:
    count = content.count(before)
    if count != 1:
        raise SystemExit(f"shrink_large_methods: expected one anchor, got {count}: {before[:90]!r}")
    return content.replace(before, after, 1)


s = TARGET.read_text(encoding="utf-8")
s = strict_replace(
    s,
    "import org.objectweb.asm.MethodVisitor",
    """import org.objectweb.asm.MethodVisitor
import org.objectweb.asm.MethodTooLargeException
import dev.akash.cs3engine.jvm.mem.LowMemUnSSATransformer
import dev.akash.cs3engine.jvm.mem.LowMemRegAssignTransformer""",
)
s = strict_replace(
    s,
    """        /** Converts [method]'s code ahead of its class, keeping any failure for dex2jar to report then. */
        fun prepare(method: DexMethodNode, context: Context) {
            prepared[method] = try {
                val ir = super.dex2ir(method)
                optimize(ir)
                val code = MethodNode(Opcodes.ASM9, method.access, method.method.name, method.method.desc, null, null)
                ir2j(ir, code, context)
                Prepared(code, null)
            } catch (t: Throwable) {
                Prepared(null, t)
            }
        }""",
    """        /** Convert one DEX method using normal or memory-efficient aggressive register coloring. */
        private fun translateMethod(method: DexMethodNode, context: Context, compact: Boolean): MethodNode {
            val ir = super.dex2ir(method)
            optimizeWithMode(ir, compact)
            val code = MethodNode(Opcodes.ASM9, method.access, method.method.name, method.method.desc, null, null)
            ir2j(ir, code, context)
            return code
        }

        /**
         * Detect oversize code before class emission. A temporary class writer measures
         * the actual JVM Code length, including wide branches and local-register opcodes.
         * The original instruction list is preserved; labels reset for the real writer.
         */
        private fun oversized(code: MethodNode): Boolean {
            if (code.instructions.size() < 2000) return false
            val probe = ClassWriter(ClassWriter.COMPUTE_MAXS)
            probe.visit(Opcodes.V1_8, Opcodes.ACC_PUBLIC or Opcodes.ACC_SUPER,
                "cs3/SizeProbe", null, "java/lang/Object", null)
            return try {
                code.accept(probe)
                probe.visitEnd()
                probe.toByteArray()
                false
            } catch (_: MethodTooLargeException) {
                true
            } finally {
                code.instructions.resetLabels()
            }
        }

        /**
         * Retry only oversized methods with cs3d's SSA/liveness-aware aggressive
         * register allocation; all ordinary methods keep the original transformer.
         * If the retry also exceeds JVM's 64 KiB Code limit, report honestly.
         */
        fun prepare(method: DexMethodNode, context: Context) {
            prepared[method] = try {
                val initial = translateMethod(method, context, compact = false)
                val code = if (oversized(initial)) {
                    System.err.println("[CS3-SIZE] Retrying ${method.method.name} with aggressive register coloring")
                    val reduced = translateMethod(method, context, compact = true)
                    if (oversized(reduced)) {
                        error("JVM method remains above 65535 Code bytes after aggressive coloring: ${method.method.name}")
                    }
                    reduced
                } else initial
                Prepared(code, null)
            } catch (t: Throwable) {
                Prepared(null, t)
            }
        }""",
)
s = strict_replace(
    s,
    """        override fun optimize(irMethod: IrMethod) {
            if (irMethod is Prepared) return""",
    """        override fun optimize(irMethod: IrMethod) = optimizeWithMode(irMethod, compact = false)

        private fun optimizeWithMode(irMethod: IrMethod, compact: Boolean) {
            if (irMethod is Prepared) return""",
)
s = strict_replace(
    s,
    """            T_UNSSA.transform(irMethod)
            // Dex2jar assigns registers before trimming handlers; Dex2Asm's default does the reverse.
            T_IR_2_J_REG_ASSIGN.transform(irMethod)
            T_TRIM_EX.transform(irMethod)""",
    """            if (compact) {
                // cs3d's linear-memory SSA destruction and copy-coalescing register allocator.
                LowMemUnSSATransformer().transform(irMethod)
                LowMemRegAssignTransformer(true).transform(irMethod)
            } else {
                T_UNSSA.transform(irMethod)
                T_IR_2_J_REG_ASSIGN.transform(irMethod)
            }
            // Assign registers before trimming exception handlers, as dex2jar does.
            T_TRIM_EX.transform(irMethod)""",
)
TARGET.write_text(s, encoding="utf-8")

java_dest = JVM / "src/main/java/dev/akash/cs3engine/jvm/mem"
java_dest.mkdir(parents=True, exist_ok=True)
for name in ("Liveness.java", "LowMemUnSSATransformer.java", "LowMemRegAssignTransformer.java"):
    shutil.copyfile(HERE / "src/transformers" / name, java_dest / name)
print("SIZE REDUCTION PATCH: three GPL-3.0 Java transformer classes copied; only oversize methods retried")

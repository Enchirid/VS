package dev.akash.cs3engine.jvm

import org.objectweb.asm.ClassReader
import org.objectweb.asm.ClassVisitor
import org.objectweb.asm.ClassWriter
import org.objectweb.asm.MethodVisitor
import org.objectweb.asm.Opcodes

/**
 * dex2jar can emit concrete methods with NO Code attribute when a DEX method
 * conversion fails. Such a class cannot even be loaded by the desktop JVM
 * (ClassFormatError), hiding which method actually failed.
 *
 * This is a STRICT fallback, not a replacement implementation: every such
 * method throws immediately when invoked. The conversion is marked incomplete,
 * and callers must never mistake successfully loading the class for a working
 * extractor.
 */
internal object MissingMethodCode {
    data class Result(val bytes: ByteArray, val missing: List<String>)

    fun repair(bytecode: ByteArray): Result {
        val patched = ArrayList<String>()
        var owner = "unknown"
        val writer = ClassWriter(ClassWriter.COMPUTE_MAXS)
        val visitor = object : ClassVisitor(Opcodes.ASM9, writer) {
            override fun visit(
                version: Int, access: Int, name: String?, signature: String?,
                superName: String?, interfaces: Array<out String>?,
            ) {
                owner = name ?: owner
                super.visit(version, access, name, signature, superName, interfaces)
            }

            override fun visitMethod(
                access: Int, name: String?, descriptor: String?,
                signature: String?, exceptions: Array<out String>?,
            ): MethodVisitor? {
                val downstream = super.visitMethod(access, name, descriptor, signature, exceptions) ?: return null
                if (access and (Opcodes.ACC_ABSTRACT or Opcodes.ACC_NATIVE) != 0) return downstream
                val methodName = name ?: "unknown"
                val methodDescriptor = descriptor ?: "()V"
                return object : MethodVisitor(Opcodes.ASM9, downstream) {
                    var hasCode = false

                    override fun visitCode() {
                        hasCode = true
                        super.visitCode()
                    }

                    override fun visitEnd() {
                        if (!hasCode) {
                            val label = "$owner.$methodName$methodDescriptor"
                            patched.add(label)
                            // Preserve the class and provide an explicit fault
                            // instead of an opaque JVM ClassFormatError.
                            super.visitCode()
                            super.visitTypeInsn(Opcodes.NEW, "java/lang/UnsupportedOperationException")
                            super.visitInsn(Opcodes.DUP)
                            super.visitLdcInsn("CS3 bytecode translator omitted method: $label")
                            super.visitMethodInsn(
                                Opcodes.INVOKESPECIAL, "java/lang/UnsupportedOperationException",
                                "<init>", "(Ljava/lang/String;)V", false,
                            )
                            super.visitInsn(Opcodes.ATHROW)
                            super.visitMaxs(3, 0)
                        }
                        super.visitEnd()
                    }
                }
            }
        }
        ClassReader(bytecode).accept(visitor, 0)
        return Result(if (patched.isEmpty()) bytecode else writer.toByteArray(), patched)
    }
}

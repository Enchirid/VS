package dev.akash.cs3engine.jvm

import org.objectweb.asm.ClassWriter
import org.objectweb.asm.Opcodes
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.assertFailsWith
import java.lang.reflect.InvocationTargetException

class MissingMethodCodeTest {
    private fun generatedClass(
        body: Boolean,
        abstractMethod: Boolean = false,
        nativeMethod: Boolean = false,
    ): ByteArray {
        val cw = ClassWriter(0)
        cw.visit(Opcodes.V1_8, Opcodes.ACC_PUBLIC or
            (if (abstractMethod) Opcodes.ACC_ABSTRACT else 0),
            "test/Converted", null, "java/lang/Object", null)

        val ctor = cw.visitMethod(Opcodes.ACC_PUBLIC, "<init>", "()V", null, null)
        ctor.visitCode()
        ctor.visitVarInsn(Opcodes.ALOAD, 0)
        ctor.visitMethodInsn(Opcodes.INVOKESPECIAL, "java/lang/Object", "<init>", "()V", false)
        ctor.visitInsn(Opcodes.RETURN)
        ctor.visitMaxs(1, 1)
        ctor.visitEnd()

        val flags = Opcodes.ACC_PUBLIC or Opcodes.ACC_STATIC or
            (if (abstractMethod) Opcodes.ACC_ABSTRACT else 0) or
            (if (nativeMethod) Opcodes.ACC_NATIVE else 0)
        val method = cw.visitMethod(flags, "run", "()I", null, null)
        if (body) {
            method.visitCode()
            method.visitInsn(Opcodes.ICONST_1)
            method.visitInsn(Opcodes.IRETURN)
            method.visitMaxs(1, 0)
        }
        method.visitEnd()
        cw.visitEnd()
        return cw.toByteArray()
    }

    private fun load(bytes: ByteArray): Class<*> =
        object : ClassLoader(javaClass.classLoader) {
            fun define(): Class<*> = defineClass("test.Converted", bytes, 0, bytes.size)
        }.define()

    @Test
    fun `a missing concrete body becomes a clearly reported failure, not an invalid JVM class`() {
        val fixed = MissingMethodCode.repair(generatedClass(body = false))
        assertEquals(1, fixed.missing.size)
        assertTrue(fixed.missing.single().contains(".run()I"))
        val method = load(fixed.bytes).getMethod("run")
        val thrown = assertFailsWith<InvocationTargetException> { method.invoke(null) }
        assertTrue(thrown.cause is UnsupportedOperationException)
        assertTrue(thrown.cause!!.message!!.contains("CS3 bytecode translator omitted method"))
    }

    @Test
    fun `already valid method bytecode is never rewritten`() {
        val original = generatedClass(body = true)
        val fixed = MissingMethodCode.repair(original)
        assertTrue(fixed.missing.isEmpty())
        assertTrue(fixed.bytes.contentEquals(original))
        assertEquals(1, load(fixed.bytes).getMethod("run").invoke(null))
    }

    @Test
    fun `abstract and native methods without code are valid and preserved`() {
        val abstract = MissingMethodCode.repair(generatedClass(body = false, abstractMethod = true))
        val native = MissingMethodCode.repair(generatedClass(body = false, nativeMethod = true))
        assertTrue(abstract.missing.isEmpty())
        assertTrue(native.missing.isEmpty())
        load(abstract.bytes)
        load(native.bytes)
    }

    @Test
    fun `Plugin shim exports the exact static Compose ABI field`() {
        val field = Class.forName("com.lagradost.cloudstream3.plugins.Plugin").getDeclaredField("\$stable")
        assertEquals(0, field.getInt(null))
    }
}

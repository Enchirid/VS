package dev.akash.cs3engine.host

import kotlinx.coroutines.ThreadContextElement
import kotlinx.coroutines.asContextElement
import java.io.IOException
import java.util.concurrent.atomic.AtomicInteger
import java.util.function.BiConsumer

/**
 * Per-loadLinks diagnostics. Captures categories/counts only: NEVER source URLs,
 * headers, cookies, authorization, request bodies, response bodies or stack traces.
 *
 * Child coroutines inheriting the loadLinks coroutine context retain its session.
 * Independent third-party clients/threads may be invisible; this is not full tracing.
 */
object ExtractionDiagnostics {
    private val current = ThreadLocal<Session?>()
    private val exceptionPattern = Regex("""\b([A-Za-z][A-Za-z0-9]*(?:Exception|Error))\b""")
    private val allowedExceptions = setOf(
        "UnknownHostException", "SocketTimeoutException", "ConnectException",
        "SSLHandshakeException", "SSLPeerUnverifiedException", "IOException",
        "InterruptedIOException", "TimeoutCancellationException", "CancellationException",
        "IllegalStateException", "IllegalArgumentException", "ClassFormatError",
        "NoSuchMethodError", "NoSuchFieldError", "UnsupportedOperationException",
        "SecurityException", "JsonParseException", "JSONException",
    )

    class Session internal constructor() {
        private val lock = Any()
        private val categories = mutableMapOf<String, Int>()
        private val statuses = mutableMapOf<String, Int>()
        private val started = System.nanoTime()

        private fun count(where: MutableMap<String, Int>, category: String) {
            synchronized(lock) {
                // Hard bound against adversarial third-party plugin behavior.
                if (where.size >= 24 && !where.containsKey(category)) return
                where[category] = (where[category] ?: 0).coerceAtMost(999) + 1
            }
        }

        internal fun event(category: String) = count(categories, category)
        internal fun http(category: String) = count(statuses, category)

        fun snapshot(): Map<String, Any> = synchronized(lock) {
            mapOf(
                "httpStatuses" to statuses.toSortedMap(),
                "exceptions" to categories.toSortedMap(),
                "elapsedMs" to ((System.nanoTime() - started) / 1_000_000).coerceAtLeast(0),
                "coverage" to "shared HTTP client and inherited coroutine logs only",
            )
        }

        /** Finite safe error text for current SkyStream GUI; no third-party raw strings. */
        fun summary(): String = synchronized(lock) {
            val parts = mutableListOf<String>()
            statuses.toSortedMap().forEach { (key, count) -> parts.add(key + "=" + count) }
            categories.toSortedMap().forEach { (key, count) -> parts.add(key + "=" + count) }
            if (parts.isEmpty()) "no captured network/error events"
            else parts.take(12).joinToString(", ")
        }
    }

    fun start(): Session = Session()

    fun context(session: Session): ThreadContextElement<Session?> = current.asContextElement(session)

    fun httpStatus(status: Int) {
        val session = current.get() ?: return
        session.http(when {
            status in 200..299 -> "HTTP_2xx"
            status in 300..399 -> "HTTP_3xx"
            status == 401 -> "HTTP_401"
            status == 403 -> "HTTP_403"
            status == 404 -> "HTTP_404"
            status == 429 -> "HTTP_429"
            status in 400..499 -> "HTTP_4xx"
            status in 500..599 -> "HTTP_5xx"
            else -> "HTTP_other"
        })
    }

    fun networkFailure(error: IOException) {
        val session = current.get() ?: return
        val className = error.javaClass.simpleName
        session.event(if (className in allowedExceptions) className else "NetworkIOException")
    }

    /** Called by Android's Log compatibility class only when the hook exists. */
    fun androidLog(priority: Int, raw: String) {
        val session = current.get() ?: return
        if (priority < 5 && !raw.startsWith("D/ApiError:") && !raw.startsWith("E/ApiError:")) return
        val type = exceptionPattern.find(raw)?.groupValues?.getOrNull(1)
        session.event(if (type in allowedExceptions) type!! else "ExtractorWarning")
    }

    /**
     * The JVM substitute for android.util.Log exposes setDiagnosticObserver.
     * Android's real Log doesn't: reflection makes this an opt-in JVM-only hook,
     * preserving the unchanged SkyStream Android runtime.
     */
    fun installJvmLogHook() {
        runCatching {
            val cls = Class.forName("android.util.Log")
            val setter = cls.getMethod("setDiagnosticObserver", BiConsumer::class.java)
            setter.invoke(null, BiConsumer<Int, String> { priority, text ->
                androidLog(priority, text)
            })
        }
    }
}

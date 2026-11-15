package dev.akash.cs3engine.host

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import java.net.UnknownHostException

class ExtractionDiagnosticsTest {
    @Test
    fun recordsBucketsWithoutLeakingSecrets() = runBlocking {
        val session = ExtractionDiagnostics.start()
        withContext(Dispatchers.IO + ExtractionDiagnostics.context(session)) {
            ExtractionDiagnostics.httpStatus(200)
            ExtractionDiagnostics.httpStatus(403)
            ExtractionDiagnostics.httpStatus(429)
            ExtractionDiagnostics.httpStatus(503)
            ExtractionDiagnostics.networkFailure(UnknownHostException("secret.example.org?token=secret"))
        }
        val report = session.snapshot().toString()
        assertTrue(report.contains("HTTP_403=1"))
        assertTrue(report.contains("HTTP_429=1"))
        assertTrue(report.contains("HTTP_5xx=1"))
        assertTrue(report.contains("UnknownHostException=1"))
        assertFalse(report.contains("secret.example.org"))
        assertFalse(report.contains("token="))
    }

    @Test
    fun capturesApiErrorLogsWithoutRawUrls() = runBlocking {
        val session = ExtractionDiagnostics.start()
        assertTrue(ExtractionDiagnostics.installJvmLogHook(), "Log diagnostic observer must be present in desktop stub")
        withContext(Dispatchers.IO + ExtractionDiagnostics.context(session)) {
            android.util.Log.d("ApiError", "safeApiCall: java.net.SocketTimeoutException at https://example.org/watch?apikey=secret")
            android.util.Log.e("SomePlugin", "SSLHandshakeException for https://example.org/private?cookie=do-not-leak")
        }
        val report = session.snapshot().toString()
        assertTrue(report.contains("SocketTimeoutException=1"))
        assertTrue(report.contains("SSLHandshakeException=1"))
        assertFalse(report.contains("apikey="))
        assertFalse(report.contains("do-not-leak"))
    }

    @Test
    fun isolatesConcurrentSessionsAndInheritedChildCoroutines() = runBlocking {
        val first = ExtractionDiagnostics.start()
        val second = ExtractionDiagnostics.start()
        val jobs = listOf(
            async(Dispatchers.Default + ExtractionDiagnostics.context(first)) {
                (0 until 15).map {
                    async {
                        ExtractionDiagnostics.httpStatus(403)
                    }
                }.awaitAll()
            },
            async(Dispatchers.Default + ExtractionDiagnostics.context(second)) {
                (0 until 7).map {
                    async {
                        ExtractionDiagnostics.httpStatus(200)
                    }
                }.awaitAll()
            },
        )
        jobs.awaitAll()
        val firstStatuses = first.snapshot()["httpStatuses"].toString()
        val secondStatuses = second.snapshot()["httpStatuses"].toString()
        assertTrue(firstStatuses.contains("HTTP_403=15"))
        assertFalse(firstStatuses.contains("HTTP_2xx"))
        assertTrue(secondStatuses.contains("HTTP_2xx=7"))
        assertFalse(secondStatuses.contains("HTTP_403"))
        assertEquals("no captured network/error events", ExtractionDiagnostics.start().summary())
    }

    @Test
    fun enforcesBoundsWithoutRetainingInput() = runBlocking {
        val session = ExtractionDiagnostics.start()
        withContext(ExtractionDiagnostics.context(session)) {
            repeat(1100) {
                ExtractionDiagnostics.httpStatus(200)
                ExtractionDiagnostics.androidLog(6, "E/ApiError: https://example.invalid/oauth?access_token=TOPSECRET")
            }
        }
        val report = session.snapshot().toString()
        assertTrue(report.contains("HTTP_2xx=1000"))
        assertTrue(report.contains("ExtractorWarning=1000"))
        assertFalse(report.contains("TOPSECRET"))
    }
}

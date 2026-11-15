package dev.akash.cs3engine

import android.content.Context
import android.util.Log
import com.lagradost.cloudstream3.MainAPI
import com.lagradost.cloudstream3.SubtitleFile
import com.lagradost.cloudstream3.utils.ExtractorLink
import com.lagradost.cloudstream3.utils.ExtractorLinkType
import com.lagradost.cloudstream3.utils.newExtractorLink
import dev.akash.cs3engine.host.ExtractionDiagnostics
import kotlinx.coroutines.runBlocking
import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * Authorized synthetic extraction: exercises provider callback plumbing and error reporting.
 * The URL is an invalid test domain: no copyrighted media is requested or downloaded.
 */
class ExtractionPipelineTest {
    private object NoPlugins : PluginLoader {
        override fun prepare(file: File) = PreparedPlugin(ExtractionPipelineTest::class.java.classLoader)
    }

    private class FakeProvider(private val good: Boolean) : MainAPI() {
        override var name: String = "SyntheticProvider"
        override var mainUrl: String = "https://example.invalid"
        override suspend fun loadLinks(
            data: String,
            isCasting: Boolean,
            subtitleCallback: (SubtitleFile) -> Unit,
            callback: (ExtractorLink) -> Unit,
        ): Boolean {
            // Simulate a third-party extractor swallowed error in an inherited coroutine context.
            ExtractionDiagnostics.httpStatus(if (good) 200 else 403)
            if (!good) {
                Log.d("ApiError", "safeApiCall: java.net.SocketTimeoutException at https://example.invalid/media?token=SECRET")
                return false
            }
            callback(newExtractorLink("Synthetic", "Synthetic Test", "https://example.invalid/synthetic.m3u8", ExtractorLinkType.M3U8))
            return true
        }
    }

    private fun engine(good: Boolean): Engine {
        val result = Engine(NoPlugins, { Context() }, "desktop-test")
        val field = Engine::class.java.getDeclaredField("providers")
        field.isAccessible = true
        @Suppress("UNCHECKED_CAST")
        val map = field.get(result) as MutableMap<String, MainAPI>
        map["SyntheticProvider"] = FakeProvider(good)
        return result
    }

    private fun request(): com.fasterxml.jackson.databind.JsonNode =
        Json.mapper.valueToTree(mapOf("provider" to "SyntheticProvider", "data" to "synthetic-only", "timeoutMs" to 4000))

    @Test
    fun successRetainsVideoCallbackAndDiagnostics() = runBlocking {
        @Suppress("UNCHECKED_CAST")
        val result = engine(true).execute("loadLinks", request()) as Map<String, Any?>
        assertEquals(true, result["completed"])
        assertEquals(true, result["providerReportedSuccess"])
        val links = result["links"] as List<*>
        assertEquals(1, links.size)
        @Suppress("UNCHECKED_CAST")
        val diagnostic = result["diagnostics"] as Map<String, Any?>
        assertTrue(diagnostic.toString().contains("HTTP_2xx=1"))
    }

    @Test
    fun emptyProviderResultExposesSafeFailureReason() = runBlocking {
        val error = assertFailsWith<IllegalStateException> { engine(false).execute("loadLinks", request()) }
        assertTrue(error.message.orEmpty().contains("extension returned false"))
        assertTrue(error.message.orEmpty().contains("HTTP_403=1"))
        assertTrue(error.message.orEmpty().contains("SocketTimeoutException=1"))
        assertFalse(error.message.orEmpty().contains("SECRET"))
        assertFalse(error.message.orEmpty().contains("example.invalid"))
    }
}

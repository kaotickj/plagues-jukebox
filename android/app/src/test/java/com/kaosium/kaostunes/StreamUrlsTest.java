package com.kaosium.kaostunes;
import org.junit.Test;
import static org.junit.Assert.*;

public class StreamUrlsTest {
    @Test public void acceptsRadioAndHls() {
        assertTrue(StreamUrls.isValid(StreamUrls.GNB));
        assertTrue(StreamUrls.isValid("http://radio.example:8000/live"));
        assertTrue(StreamUrls.isValid("https://radio.example/live.m3u8?token=abc"));
    }
    @Test public void rejectsMalformedAndCredentialUrls() {
        for (String url : new String[]{"https://", "file:///tmp/song", "https://u:p@radio.example/live", "https://radio.example/a b", "https://radio.example:99999/live", "https://radio.example/#section"})
            assertFalse(url, StreamUrls.isValid(url));
    }
}

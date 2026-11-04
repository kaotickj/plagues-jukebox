package com.kaosium.kaostunes;

import java.util.Locale;
import java.util.regex.Pattern;

/** Device discovery only. Explicit file and folder imports bypass this policy. */
public final class MusicScanPolicy {
    private static final Pattern VOICE_FILE = Pattern.compile(
        "^(?:voice[ _-]?mail|visual[ _-]?voice[ _-]?mail|vvm|call[ _-]?recording|voice[ _-]?recording|voice[ _-]?memo)(?:[ _.-]*[0-9]|\\.(?:mp3|m4a|amr|wav|ogg|opus|aac|3gp)$|$)");

    private MusicScanPolicy() { }

    public static boolean include(boolean music, boolean ringtone, boolean alarm,
                                  boolean notification, boolean recording, String path,
                                  String filename, long durationMs, long minimumMs) {
        if (!music || ringtone || alarm || notification || recording) return false;
        if (voicePath(path) || VOICE_FILE.matcher(normalize(filename)).find()) return false;
        // Unknown duration cannot pass an explicitly enabled minimum.
        return minimumMs <= 0 || durationMs >= minimumMs;
    }

    private static String normalize(String value) {
        return value == null ? "" : value.trim().toLowerCase(Locale.ROOT);
    }

    private static boolean voicePath(String path) {
        for (String part : normalize(path).replace('\\', '/').split("/")) {
            String folder = part.replaceAll("[ _-]", "");
            switch (folder) {
                case "voicemail": case "voicemails": case "visualvoicemail":
                case "visualvoicemails": case "vvm": case "recording": case "recordings":
                case "voicerecorder": case "voicerecordings": case "voicememos":
                case "callrecording": case "callrecordings":
                case "ringtones": case "notifications": case "alarms": return true;
                default: break;
            }
        }
        return false;
    }

    public static String restoredSource(String savedSource, String uri) {
        if ("manual".equals(savedSource) || "device".equals(savedSource)) return savedSource;
        // Version 0.1.0's scanner created these URIs. Document-picker URIs stay manual.
        return uri != null && uri.matches("content://media/[^/]+/audio/media/[0-9]+")
            ? "device" : "manual";
    }
}

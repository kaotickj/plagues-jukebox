package com.kaosium.kaostunes;

import java.util.List;
import java.util.Locale;

/** Match desktop M3U paths to an accessible Android catalog, rejecting ambiguous names. */
public final class PlaylistResolver {
    public static int resolve(String entry, List<String> uris, List<String> filenames) {
        String clean = entry.trim();
        int exact = uris.indexOf(clean);
        if (exact >= 0) return exact;
        String name = clean.replace('\\', '/');
        name = name.substring(name.lastIndexOf('/') + 1).toLowerCase(Locale.ROOT);
        int found = -1;
        for (int i = 0; i < filenames.size(); i++) {
            if (filenames.get(i).toLowerCase(Locale.ROOT).equals(name)) {
                if (found >= 0) return -1;
                found = i;
            }
        }
        return found;
    }
}

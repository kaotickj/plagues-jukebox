package com.kaosium.kaostunes;

import java.util.HashSet;
import java.util.List;
import java.util.Set;

/** Merge a successful scan without overwriting tags or removing explicit imports. */
public final class ScanCatalogUpdater {
    public static final class Update {
        public int added;
        public final Set<String> removed = new HashSet<>();
    }

    private ScanCatalogUpdater() { }

    public static Update apply(List<Track> library, List<Track> found, Set<String> excluded) {
        Update update = new Update();
        library.removeIf(t -> {
            boolean reject = "device".equals(t.scanSource) && excluded.contains(t.uri);
            if (reject) update.removed.add(t.uri);
            return reject;
        });
        Set<String> existing = new HashSet<>();
        for (Track t : library) existing.add(t.uri);
        for (Track t : found) if (existing.add(t.uri)) { library.add(t); update.added++; }
        return update;
    }
}

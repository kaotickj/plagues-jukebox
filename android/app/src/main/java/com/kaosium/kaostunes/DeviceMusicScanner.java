package com.kaosium.kaostunes;

import android.content.ContentResolver;
import android.content.ContentUris;
import android.database.Cursor;
import android.net.Uri;
import android.os.Build;
import android.provider.MediaStore;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

public final class DeviceMusicScanner {
    public static final class Result {
        public final List<Track> music = new ArrayList<>();
        public final Set<String> excluded = new HashSet<>();
    }

    private DeviceMusicScanner() { }

    @SuppressWarnings("deprecation")
    public static Result scan(ContentResolver resolver, long minimumMs) throws IOException {
        Uri base = MediaStore.Audio.Media.EXTERNAL_CONTENT_URI;
        String pathColumn = Build.VERSION.SDK_INT >= 29
            ? MediaStore.Audio.Media.RELATIVE_PATH : MediaStore.Audio.Media.DATA;
        List<String> projection = new ArrayList<>(Arrays.asList(
            MediaStore.Audio.Media._ID, MediaStore.Audio.Media.TITLE,
            MediaStore.Audio.Media.ARTIST, MediaStore.Audio.Media.ALBUM,
            MediaStore.Audio.Media.DURATION, MediaStore.Audio.Media.DISPLAY_NAME,
            MediaStore.Audio.Media.IS_MUSIC, MediaStore.Audio.Media.IS_RINGTONE,
            MediaStore.Audio.Media.IS_ALARM, MediaStore.Audio.Media.IS_NOTIFICATION, pathColumn));
        if (Build.VERSION.SDK_INT >= 31) projection.add(MediaStore.Audio.Media.IS_RECORDING);
        Result result = new Result();
        // Read rejected rows too, so a rescan can clean up the previous version's imports.
        try (Cursor c = resolver.query(base, projection.toArray(new String[0]), null, null,
                                     MediaStore.Audio.Media.TITLE + " ASC")) {
            if (c == null) throw new IOException("Android's audio index is unavailable. Try again.");
            while (c.moveToNext()) {
                Track t = new Track(ContentUris.withAppendedId(base, c.getLong(0)).toString());
                t.title = clean(c.getString(1)); t.artist = clean(c.getString(2));
                t.album = clean(c.getString(3)); t.duration = c.getLong(4);
                t.filename = clean(c.getString(5)); t.scanSource = "device";
                boolean recording = Build.VERSION.SDK_INT >= 31 && c.getInt(11) != 0;
                if (MusicScanPolicy.include(c.getInt(6) != 0, c.getInt(7) != 0,
                        c.getInt(8) != 0, c.getInt(9) != 0, recording,
                        c.getString(10), t.filename, t.duration, minimumMs)) result.music.add(t);
                else result.excluded.add(t.uri);
            }
        }
        return result;
    }

    private static String clean(String value) {
        return value == null || value.equals("<unknown>") ? "" : value.trim();
    }
}

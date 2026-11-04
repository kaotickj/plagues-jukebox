package com.kaosium.kaostunes;

import android.content.Context;
import org.json.JSONArray;
import java.util.ArrayList;
import java.util.List;

public final class Catalog {
    public static List<Track> load(Context c, String key) {
        List<Track> tracks = new ArrayList<>();
        try {
            JSONArray a = new JSONArray(c.getSharedPreferences("kaostunes", 0).getString(key, "[]"));
            for (int i = 0; i < a.length(); i++) {
                Track t = Track.from(a.getJSONObject(i));
                if (!t.uri.trim().isEmpty()) tracks.add(t);
            }
        } catch (Exception ignored) { }
        return tracks;
    }

    public static String encode(List<Track> tracks) {
        JSONArray a = new JSONArray();
        for (Track t : tracks) a.put(t.json());
        return a.toString();
    }

    public static void save(Context c, String key, List<Track> tracks) {
        c.getSharedPreferences("kaostunes", 0).edit().putString(key, encode(tracks)).apply();
    }

    public static int find(List<Track> tracks, String uri) {
        for (int i = 0; i < tracks.size(); i++) if (tracks.get(i).uri.equals(uri)) return i;
        return -1;
    }
}

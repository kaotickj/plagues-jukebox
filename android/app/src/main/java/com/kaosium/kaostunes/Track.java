package com.kaosium.kaostunes;

import android.net.Uri;
import org.json.JSONObject;
import androidx.media3.common.MediaItem;
import androidx.media3.common.MediaMetadata;

public final class Track {
    public String uri, title = "", artist = "", album = "", filename = "", art = "";
    public String year = "", genre = "", metadataSource = "";
    public String scanSource = "manual";
    public long duration;

    public Track(String uri) { this.uri = uri; }
    public String displayTitle() { return title.trim().isEmpty() ? (filename.trim().isEmpty() ? "Untitled audio" : filename) : title; }
    public String subtitle() { return (artist.trim().isEmpty() ? "Unknown artist" : artist) + (album.trim().isEmpty() ? "" : " · " + album); }

    public JSONObject json() {
        JSONObject o = new JSONObject();
        try {
            o.put("uri", uri).put("title", title).put("artist", artist).put("album", album)
             .put("filename", filename).put("duration", duration).put("art", art)
             .put("year", year).put("genre", genre).put("metadata_source", metadataSource)
             .put("scan_source", scanSource);
        } catch (Exception ignored) { }
        return o;
    }

    public static Track from(JSONObject o) {
        Track t = new Track(o.optString("uri"));
        t.title = o.optString("title"); t.artist = o.optString("artist"); t.album = o.optString("album");
        t.filename = o.optString("filename"); t.duration = o.optLong("duration"); t.art = o.optString("art");
        t.year = o.optString("year"); t.genre = o.optString("genre"); t.metadataSource = o.optString("metadata_source");
        t.scanSource = MusicScanPolicy.restoredSource(o.optString("scan_source"), t.uri);
        return t;
    }

    public MediaItem mediaItem() {
        MediaMetadata.Builder meta = new MediaMetadata.Builder().setTitle(displayTitle()).setArtist(artist).setAlbumTitle(album);
        if (!art.trim().isEmpty()) meta.setArtworkUri(Uri.parse(art));
        return new MediaItem.Builder().setMediaId(uri).setUri(Uri.parse(uri)).setMediaMetadata(meta.build()).build();
    }
}

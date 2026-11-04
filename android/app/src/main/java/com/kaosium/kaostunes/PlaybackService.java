package com.kaosium.kaostunes;

import android.app.PendingIntent;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Handler;
import android.os.Looper;
import androidx.annotation.Nullable;
import androidx.media3.common.AudioAttributes;
import androidx.media3.common.C;
import androidx.media3.common.Player;
import androidx.media3.exoplayer.ExoPlayer;
import androidx.media3.session.MediaSession;
import androidx.media3.session.MediaSessionService;
import java.util.ArrayList;
import java.util.List;
import com.google.common.util.concurrent.Futures;
import com.google.common.util.concurrent.ListenableFuture;

public final class PlaybackService extends MediaSessionService {
    private ExoPlayer player;
    private MediaSession session;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable checkpoint = new Runnable() {
        public void run() { if (player != null && player.isPlaying()) save(); handler.postDelayed(this, 5000); }
    };

    @Override public void onCreate() {
        super.onCreate();
        player = new ExoPlayer.Builder(this).build();
        player.setAudioAttributes(new AudioAttributes.Builder().setUsage(C.USAGE_MEDIA).setContentType(C.AUDIO_CONTENT_TYPE_MUSIC).build(), true);
        player.setHandleAudioBecomingNoisy(true);
        player.setWakeMode(C.WAKE_MODE_LOCAL);
        SharedPreferences prefs = getSharedPreferences("kaostunes", 0);
        List<androidx.media3.common.MediaItem> items = new ArrayList<>();
        for (Track t : Catalog.load(this, "queue")) items.add(t.mediaItem());
        if (!items.isEmpty()) {
            int index = Math.max(0, Math.min(prefs.getInt("index", 0), items.size() - 1));
            player.setMediaItems(items, index, Math.max(0, prefs.getLong("position", 0)));
            player.prepare();
        }
        player.setRepeatMode(prefs.getInt("repeat", Player.REPEAT_MODE_OFF));
        player.setShuffleModeEnabled(prefs.getBoolean("shuffle", false));
        PendingIntent activity = PendingIntent.getActivity(this, 0, new Intent(this, MainActivity.class), PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        session = new MediaSession.Builder(this, player).setSessionActivity(activity).setCallback(new MediaSession.Callback() {
            @Override public ListenableFuture<List<androidx.media3.common.MediaItem>> onAddMediaItems(
                MediaSession s, MediaSession.ControllerInfo info, List<androidx.media3.common.MediaItem> requested
            ) {
                List<androidx.media3.common.MediaItem> resolved = new ArrayList<>();
                for (var item : requested) {
                    var uri = android.net.Uri.parse(item.mediaId);
                    if ("content".equals(uri.getScheme()) || StreamUrls.isValid(item.mediaId))
                        resolved.add(item.buildUpon().setUri(uri).build());
                }
                return Futures.immediateFuture(resolved);
            }
        }).build();
        player.addListener(new Player.Listener() {
            @Override public void onEvents(Player p, Player.Events events) { save(); }
        });
        handler.post(checkpoint);
    }

    private void save() {
        if (player == null) return;
        List<Track> queue = new ArrayList<>();
        List<Track> catalog = Catalog.load(this, "library");
        for (int i = 0; i < player.getMediaItemCount(); i++) {
            var item = player.getMediaItemAt(i);
            int row = Catalog.find(catalog, item.mediaId);
            Track t = row >= 0 ? catalog.get(row) : new Track(item.mediaId);
            if (item.mediaMetadata.title != null) t.title = item.mediaMetadata.title.toString();
            if (item.mediaMetadata.artist != null) t.artist = item.mediaMetadata.artist.toString();
            if (item.mediaMetadata.albumTitle != null) t.album = item.mediaMetadata.albumTitle.toString();
            if (item.mediaMetadata.artworkUri != null) t.art = item.mediaMetadata.artworkUri.toString();
            queue.add(t);
        }
        getSharedPreferences("kaostunes", 0).edit().putString("queue", Catalog.encode(queue))
            .putInt("index", Math.max(0, player.getCurrentMediaItemIndex()))
            .putLong("position", Math.max(0, player.getCurrentPosition()))
            .putInt("repeat", player.getRepeatMode()).putBoolean("shuffle", player.getShuffleModeEnabled()).apply();
    }

    @Override @Nullable public MediaSession onGetSession(MediaSession.ControllerInfo info) { return session; }

    @Override public void onTaskRemoved(Intent rootIntent) {
        if (!player.getPlayWhenReady() || player.getMediaItemCount() == 0 || player.getPlaybackState() == Player.STATE_ENDED) stopSelf();
    }

    @Override public void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        save();
        if (session != null) session.release();
        if (player != null) player.release();
        player = null;
        super.onDestroy();
    }
}

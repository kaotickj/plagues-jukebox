package com.kaosium.kaostunes;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.ComponentName;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.media.MediaMetadataRetriever;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.OpenableColumns;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowInsets;
import android.widget.*;
import androidx.documentfile.provider.DocumentFile;
import androidx.media3.common.C;
import androidx.media3.common.MediaItem;
import androidx.media3.common.Player;
import androidx.media3.common.PlaybackException;
import androidx.media3.session.MediaController;
import androidx.media3.session.SessionToken;
import com.google.common.util.concurrent.ListenableFuture;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private static final int FILES = 100, FOLDER = 101, IMPORT = 102, EXPORT = 103, AUDIO_PERMISSION = 104;
    private static final int BG = Color.rgb(16,19,22), CARD = Color.rgb(27,32,38), GREEN = Color.rgb(57,217,138), WHITE = Color.rgb(232,237,242), MUTED = Color.rgb(158,171,184);
    private final Handler main = new Handler(Looper.getMainLooper());
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private String stationTitle = "", stationArtist = "";
    private boolean stationPending;
    private final Runnable stationPoll = new Runnable() {
        public void run() { pollStation(); if(!destroyed)main.postDelayed(this,10000); }
    };
    private void pollStation() {
        if(destroyed||stationPending||controller==null||!controller.isPlaying()||controller.getCurrentMediaItem()==null||!StreamUrls.GNB.equals(controller.getCurrentMediaItem().mediaId))return;
        stationPending=true;
        worker.execute(() -> {
            java.net.HttpURLConnection connection=null;
            String song="", performer="";
            try {
                connection=(java.net.HttpURLConnection)new java.net.URL("https://goodneighborblues.com/radio/status").openConnection();
                connection.setConnectTimeout(6000);connection.setReadTimeout(6000);
                try(var input=connection.getInputStream();var output=new java.io.ByteArrayOutputStream()) {
                    byte[] buffer=new byte[4096];int n;
                    while((n=input.read(buffer))!=-1){if(output.size()+n>65536)throw new java.io.IOException("Metadata too large");output.write(buffer,0,n);}
                    var data=new org.json.JSONObject(output.toString("UTF-8"));
                    song=data.optString("title","");performer=data.optString("artist","");
                }
            }catch(Exception ignored){}finally{if(connection!=null)connection.disconnect();}
            final String resultTitle=song,resultArtist=performer;
            main.post(() -> {stationPending=false;if(!destroyed&&!resultTitle.isEmpty()){stationTitle=resultTitle;stationArtist=resultArtist;renderPlayer();}});
        });
    }
    private final List<Track> library = new ArrayList<>(), visible = new ArrayList<>();
    private final Set<String> pendingScanQueueRemovals = new HashSet<>();
    private MediaController controller;
    private ListenableFuture<MediaController> controllerFuture;
    private ListView list;
    private BaseAdapter adapter;
    private EditText search;
    private TextView heading, summary, title, artist, times;
    private ImageView artwork;
    private Button play, shuffle, repeat, libraryTab, queueTab;
    private SeekBar seek;
    private boolean queueView, dragging, destroyed;
    private int artGeneration;
    private String shownArtUri = "";
    private final Runnable progress = new Runnable() {
        @Override public void run() { if (!destroyed) { updateProgress(); main.postDelayed(this, 500); } }
    };

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        library.addAll(Catalog.load(this, "library"));
        queueView = state != null && state.getBoolean("queueView");
        buildUi();
        controllerFuture = new MediaController.Builder(this, new SessionToken(this, new ComponentName(this, PlaybackService.class))).buildAsync();
        controllerFuture.addListener(() -> {
            try {
                controller = controllerFuture.get();
                if (destroyed) return;
                controller.addListener(new Player.Listener() {
                    @Override public void onEvents(Player p, Player.Events events) { renderPlayer(); refreshList(); }
                    @Override public void onPlayerError(PlaybackException e) { message("Playback error", e.getMessage() + "\n\nFor streams, check the URL, network connection and station availability. For files, check access permissions and codec support."); }
                });
                removeFilteredQueueItems();
                renderPlayer(); refreshList();
            } catch (Exception e) { message("Player unavailable", e.getMessage()); }
        }, getMainExecutorCompat());
        refreshList(); main.post(progress); main.post(stationPoll);
    }

    private java.util.concurrent.Executor getMainExecutorCompat() { return command -> main.post(command); }
    private int dp(int value) { return (int) (value * getResources().getDisplayMetrics().density + .5f); }
    private TextView text(String value, int size, int color) {
        TextView t = new TextView(this); t.setText(value); t.setTextSize(size); t.setTextColor(color); return t;
    }
    private GradientDrawable background(int color) { GradientDrawable d = new GradientDrawable(); d.setColor(color); d.setCornerRadius(dp(10)); return d; }
    private Button button(String label, Runnable action) {
        Button b = new Button(this); b.setText(label); b.setAllCaps(false); b.setTextColor(WHITE); b.setTextSize(13);
        b.setMinWidth(0); b.setMinimumWidth(0); b.setPadding(dp(5),0,dp(5),0); b.setBackground(background(CARD));
        b.setOnClickListener(v -> action.run()); return b;
    }
    private void addButton(LinearLayout row, Button b) {
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(0,dp(44),1); p.setMargins(dp(3),dp(3),dp(3),dp(3)); row.addView(b,p);
    }
    private LinearLayout row() { LinearLayout l = new LinearLayout(this); l.setOrientation(LinearLayout.HORIZONTAL); return l; }
    private void buildUi() {
        LinearLayout root = new LinearLayout(this); root.setOrientation(LinearLayout.VERTICAL); root.setBackgroundColor(BG); root.setPadding(dp(12),dp(10),dp(12),dp(10));
        root.setOnApplyWindowInsetsListener((v,insets) -> {
            v.setPadding(dp(12)+insets.getSystemWindowInsetLeft(),dp(10)+insets.getSystemWindowInsetTop(),dp(12)+insets.getSystemWindowInsetRight(),dp(10)+insets.getSystemWindowInsetBottom());
            return insets;
        });
        setContentView(root);
        TextView brand = text("Plague’s Jukebox",24,GREEN); brand.setTypeface(null,Typeface.BOLD); root.addView(brand);
        TextView byline = text("Your music. Your library.",12,MUTED); byline.setPadding(0,0,0,dp(8)); root.addView(byline);
        LinearLayout tabs = row();
        libraryTab = button("Music Library",() -> { queueView=false; refreshList(); });
        queueTab = button("Play Queue",() -> { queueView=true; refreshList(); });
        addButton(tabs,libraryTab); addButton(tabs,queueTab); root.addView(tabs);
        LinearLayout tools = row();
        addButton(tools,button("Add files",() -> openDocument(FILES,"audio/*",true)));
        addButton(tools,button("Scan device",this::scanPermission));
        addButton(tools,button("More",this::more)); root.addView(tools);
        search = new EditText(this); search.setSingleLine(true); search.setTextSize(14); search.setTextColor(WHITE); search.setHintTextColor(MUTED); search.setHint("Search title, artist, album"); search.setBackground(background(CARD)); search.setPadding(dp(12),dp(8),dp(12),dp(8));
        root.addView(search,new LinearLayout.LayoutParams(-1,dp(44)));
        search.addTextChangedListener(new TextWatcher() { public void beforeTextChanged(CharSequence s,int a,int c,int f) {} public void onTextChanged(CharSequence s,int start,int before,int count) { refreshList(); } public void afterTextChanged(Editable e) {} });
        heading = text("",14,WHITE); heading.setTypeface(null,Typeface.BOLD); heading.setPadding(dp(3),dp(10),0,dp(3)); root.addView(heading);
        summary = text("",12,MUTED); summary.setPadding(dp(3),0,0,dp(4)); root.addView(summary);
        list = new ListView(this); list.setDividerHeight(dp(1)); list.setDivider(new android.graphics.drawable.ColorDrawable(CARD));
        adapter = new BaseAdapter() {
            public int getCount() { return visible.size(); } public Object getItem(int p) { return visible.get(p); } public long getItemId(int p) { return p; }
            public View getView(int p,View recycled,ViewGroup parent) {
                LinearLayout cell = new LinearLayout(MainActivity.this); cell.setOrientation(LinearLayout.VERTICAL); cell.setPadding(dp(10),dp(9),dp(10),dp(9));
                Track t=visible.get(p); boolean current = controller!=null && controller.getCurrentMediaItem()!=null && t.uri.equals(controller.getCurrentMediaItem().mediaId);
                TextView first = text((current ? "▶ " : "") + t.displayTitle(),16,current ? GREEN : WHITE); first.setMaxLines(1); first.setEllipsize(android.text.TextUtils.TruncateAt.END);
                TextView second=text(t.subtitle() + (t.duration>0 ? " · "+formatTime(t.duration) : ""),12,MUTED); second.setMaxLines(1); second.setEllipsize(android.text.TextUtils.TruncateAt.END);
                cell.addView(first);cell.addView(second); return cell;
            }
        };
        list.setAdapter(adapter); list.setOnItemClickListener((p,v,index,id) -> playTrack(visible.get(index)));
        list.setOnItemLongClickListener((p,v,index,id) -> { trackMenu(visible.get(index)); return true; });
        TextView empty=text("Add audio files or scan your device.\nTap a song to play. Hold a song for options.",15,MUTED);empty.setGravity(Gravity.CENTER);empty.setPadding(dp(20),dp(20),dp(20),dp(20));
        android.widget.FrameLayout frame = new android.widget.FrameLayout(this);frame.addView(list,new android.widget.FrameLayout.LayoutParams(-1,-1));frame.addView(empty,new android.widget.FrameLayout.LayoutParams(-1,-1));list.setEmptyView(empty);
        root.addView(frame,new LinearLayout.LayoutParams(-1,0,1));
        LinearLayout now=row();now.setPadding(0,dp(8),0,dp(5));
        artwork=new ImageView(this);artwork.setImageResource(R.drawable.kaostunes_art);artwork.setScaleType(ImageView.ScaleType.CENTER_CROP);now.addView(artwork,new LinearLayout.LayoutParams(dp(62),dp(62)));
        LinearLayout labels=new LinearLayout(this);labels.setOrientation(LinearLayout.VERTICAL);labels.setPadding(dp(10),dp(5),0,0);
        title=text("Nothing playing",17,WHITE);title.setTypeface(null,Typeface.BOLD);title.setMaxLines(1);title.setEllipsize(android.text.TextUtils.TruncateAt.END);
        artist=text("Tap a song to start",12,MUTED);artist.setMaxLines(1);artist.setEllipsize(android.text.TextUtils.TruncateAt.END);labels.addView(title);labels.addView(artist);now.addView(labels,new LinearLayout.LayoutParams(0,-2,1));root.addView(now);
        seek=new SeekBar(this);root.addView(seek,new LinearLayout.LayoutParams(-1,dp(28)));
        seek.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            public void onProgressChanged(SeekBar s,int p,boolean user) { if(user) times.setText(formatTime(p)+" / "+formatTime(s.getMax())); }
            public void onStartTrackingTouch(SeekBar s) { dragging=true; }
            public void onStopTrackingTouch(SeekBar s) { if(controller!=null) controller.seekTo(s.getProgress());dragging=false; }
        });
        times=text("0:00 / 0:00",12,MUTED);times.setGravity(Gravity.CENTER);root.addView(times);
        LinearLayout transport=row();
        addButton(transport,button("Previous",() -> { if(connected()) { if(controller.getCurrentPosition()>5000)controller.seekTo(0);else controller.seekToPreviousMediaItem(); } }));
        play=button("Play",this::togglePlayback);play.setTextColor(BG);play.setBackground(background(GREEN));addButton(transport,play);
        addButton(transport,button("Next",() -> { if(connected())controller.seekToNextMediaItem(); }));root.addView(transport);
        LinearLayout modes=row();
        shuffle=button("Shuffle: Off",() -> { if(connected())controller.setShuffleModeEnabled(!controller.getShuffleModeEnabled()); });addButton(modes,shuffle);
        repeat=button("Repeat: Off",() -> { if(connected())controller.setRepeatMode((controller.getRepeatMode()+1)%3); });addButton(modes,repeat);
        addButton(modes,button("Stop",() -> { if(connected()) { controller.pause();controller.seekTo(0); } }));root.addView(modes);
    }

    private boolean connected() { if(controller!=null)return true;toast("Player is connecting. Try again in a moment.");return false; }
    private List<Track> queueTracks() {
        List<Track> result=new ArrayList<>();if(controller==null)return result;
        for(int i=0;i<controller.getMediaItemCount();i++) {
            MediaItem m=controller.getMediaItemAt(i);int index=Catalog.find(library,m.mediaId);
            Track t=index>=0?library.get(index):new Track(m.mediaId);
            if(index<0) {t.title=m.mediaMetadata.title==null?"":m.mediaMetadata.title.toString();t.artist=m.mediaMetadata.artist==null?"":m.mediaMetadata.artist.toString();t.album=m.mediaMetadata.albumTitle==null?"":m.mediaMetadata.albumTitle.toString();}
            result.add(t);
        }return result;
    }
    private void refreshList() {
        if(adapter==null)return;
        List<Track> source=queueView?queueTracks():new ArrayList<>(library);
        if(!queueView)source.sort(Comparator.comparing(t -> t.displayTitle().toLowerCase(Locale.ROOT)));
        String query=search.getText().toString().trim().toLowerCase(Locale.ROOT);visible.clear();
        for(Track t:source)if((t.displayTitle()+" "+t.artist+" "+t.album).toLowerCase(Locale.ROOT).contains(query))visible.add(t);
        heading.setText(queueView?"Play Queue":"Music Library");
        summary.setText(visible.size()+" / "+source.size()+" tracks · Tap to play, hold for options");
        libraryTab.setTextColor(queueView?MUTED:GREEN);queueTab.setTextColor(queueView?GREEN:MUTED);adapter.notifyDataSetChanged();
    }
    private void playTrack(Track t) {
        if(!connected())return;
        int index=-1;for(int i=0;i<controller.getMediaItemCount();i++)if(controller.getMediaItemAt(i).mediaId.equals(t.uri)){index=i;break;}
        if(index<0){controller.addMediaItem(t.mediaItem());index=controller.getMediaItemCount()-1;}
        controller.seekTo(index,0);controller.prepare();controller.play();requestNotifications();
    }
    private void togglePlayback() {
        if(!connected())return;
        if(controller.getPlayWhenReady()){controller.pause();return;}
        if(controller.getMediaItemCount()==0){if(!visible.isEmpty())playTrack(visible.get(0));else toast("Add a song first.");return;}
        if(controller.getPlaybackState()==Player.STATE_ENDED)controller.seekTo(0);
        controller.prepare();controller.play();requestNotifications();
    }
    private void renderPlayer() {
        if(controller==null)return;
        MediaItem m=controller.getCurrentMediaItem();
        if(m==null){title.setText("Nothing playing");artist.setText("Tap a song to start");shownArtUri="";artGeneration++;artwork.setImageResource(R.drawable.kaostunes_art);}
        else {
            var live=controller.getMediaMetadata();
            title.setText(live.title==null?"Untitled audio":live.title);artist.setText(live.artist==null?"":live.artist);
            if(StreamUrls.GNB.equals(m.mediaId)&&!stationTitle.isEmpty()){title.setText(stationTitle);artist.setText(stationArtist);}
            if(!m.mediaId.equals(shownArtUri)){shownArtUri=m.mediaId;loadArtwork(m.mediaId);}
        }
        play.setText(controller.getPlayWhenReady()?"Pause":"Play");
        shuffle.setText("Shuffle: "+(controller.getShuffleModeEnabled()?"On":"Off"));
        repeat.setText("Repeat: "+new String[]{"Off","One","All"}[controller.getRepeatMode()]);updateProgress();
    }
    private void updateProgress() {
        if(controller==null||dragging)return;
        long duration=controller.getDuration();if(duration==C.TIME_UNSET)duration=0;
        int limit=(int)Math.min(Integer.MAX_VALUE,Math.max(0,duration));seek.setMax(limit);seek.setEnabled(limit>0);
        long pos=Math.max(0,controller.getCurrentPosition());seek.setProgress((int)Math.min(Integer.MAX_VALUE,pos));times.setText(formatTime(pos)+" / "+formatTime(duration));
    }
    private static String formatTime(long ms) { long s=Math.max(0,ms)/1000;return String.format(Locale.ROOT,"%d:%02d",s/60,s%60); }

    private void more() {
        String[] labels={"Add a music folder","Play all visible tracks","Add visible tracks to queue","Import playlist","Export queue","Add internet stream","Clear queue","About & licenses","Scan settings","Listen to Goodneighbor Blues"};
        new AlertDialog.Builder(this).setTitle("Plague’s Jukebox").setItems(labels,(d,n) -> {
            switch(n) {
                case 0:Intent tree=new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);tree.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);startActivityForResult(tree,FOLDER);break;
                case 1:if(connected()&&!visible.isEmpty()){List<MediaItem> items=new ArrayList<>();for(Track t:visible)items.add(t.mediaItem());controller.setMediaItems(items);controller.prepare();controller.play();requestNotifications();}break;
                case 2:if(connected()){for(Track t:visible){boolean exists=false;for(int i=0;i<controller.getMediaItemCount();i++)if(controller.getMediaItemAt(i).mediaId.equals(t.uri))exists=true;if(!exists)controller.addMediaItem(t.mediaItem());}toast("Tracks added to queue.");}break;
                case 3:openDocument(IMPORT,"*/*",false);break;
                case 4:if(connected()){Intent out=new Intent(Intent.ACTION_CREATE_DOCUMENT).setType("application/json").putExtra(Intent.EXTRA_TITLE,"Plague’s Jukebox-playlist.json");out.addCategory(Intent.CATEGORY_OPENABLE);startActivityForResult(out,EXPORT);}break;
                case 5:addStream();break;
                case 6:new AlertDialog.Builder(this).setTitle("Clear play queue?").setMessage("Your music library and audio files are kept.").setPositiveButton("Clear",(a,b) -> {if(connected()){controller.pause();controller.clearMediaItems();}}).setNegativeButton("Cancel",null).show();break;
                case 7:about();break;
                case 9:addStreamUrl(StreamUrls.GNB,"Goodneighbor Blues");break;
                case 8:scanSettings();break;
            }
        }).show();
    }
    private void trackMenu(Track t) {
        List<String> choices=new ArrayList<>(Arrays.asList("Play","Add to queue","Media information","Find metadata online","Remove from "+(queueView?"queue":"library")));
        new AlertDialog.Builder(this).setTitle(t.displayTitle()).setItems(choices.toArray(new String[0]),(d,n) -> {
            if(n==0)playTrack(t);
            if(n==1&&connected()){controller.addMediaItem(t.mediaItem());toast("Added to queue.");}
            if(n==2)message("Media information",t.displayTitle()+"\n"+t.subtitle()+"\nDuration: "+formatTime(t.duration)+"\n"+t.uri+(t.metadataSource.trim().isEmpty()?"":"\nMetadata: "+t.metadataSource));
            if(n==3)onlineLookup(t);
            if(n==4){if(queueView&&connected()){for(int i=controller.getMediaItemCount()-1;i>=0;i--)if(controller.getMediaItemAt(i).mediaId.equals(t.uri))controller.removeMediaItem(i);}else {library.removeIf(x -> x.uri.equals(t.uri));Catalog.save(this,"library",library);refreshList();}}
        }).show();
    }
    private void addStreamUrl(String url,String name) {
        Track t=new Track(url);t.title=name;
        if(Catalog.find(library,url)<0)library.add(t);
        Catalog.save(this,"library",library);refreshList();playTrack(t);
    }
    private void addStream() {
        EditText input=new EditText(this);input.setHint("https://example.com/radio.m3u8");input.setSingleLine(true);
        new AlertDialog.Builder(this).setTitle("Add internet stream").setView(input).setPositiveButton("Add",(d,n) -> {
            String url=input.getText().toString().trim();
            if(!StreamUrls.isValid(url)){toast("Enter a complete HTTP or HTTPS URL without login credentials or spaces.");return;}
            addStreamUrl(url,Uri.parse(url).getHost());
        }).setNegativeButton("Cancel",null).show();
    }

    private void openDocument(int request,String type,boolean multi) {
        Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT).setType(type).addCategory(Intent.CATEGORY_OPENABLE);
        intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE,multi);intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);startActivityForResult(intent,request);
    }
    private void persist(Uri uri,Intent data) {
        try {if((data.getFlags()&Intent.FLAG_GRANT_READ_URI_PERMISSION)!=0)getContentResolver().takePersistableUriPermission(uri,Intent.FLAG_GRANT_READ_URI_PERMISSION);}catch(SecurityException ignored){}
    }
    @Override protected void onActivityResult(int request,int result,Intent data) {
        super.onActivityResult(request,result,data);if(result!=RESULT_OK||data==null)return;
        if(request==FILES){List<Uri> uris=new ArrayList<>();if(data.getClipData()!=null){for(int i=0;i<data.getClipData().getItemCount();i++)uris.add(data.getClipData().getItemAt(i).getUri());}else if(data.getData()!=null)uris.add(data.getData());for(Uri uri:uris)persist(uri,data);addUris(uris);}
        else if(request==FOLDER&&data.getData()!=null){Uri root=data.getData();persist(root,data);toast("Reading folder…");worker.execute(() -> {
            try {List<Uri> uris=new ArrayList<>();walk(DocumentFile.fromTreeUri(this,root),uris,new HashSet<>(),0);main.post(() -> addUris(uris));}catch(Exception e){main.post(() -> message("Folder could not be read",e.getMessage()));}
        });}
        else if(request==IMPORT&&data.getData()!=null){persist(data.getData(),data);importPlaylist(data.getData());}
        else if(request==EXPORT&&data.getData()!=null){String json=Catalog.encode(queueTracks());Uri dest=data.getData();worker.execute(() -> {
            try(OutputStream out=getContentResolver().openOutputStream(dest,"wt")){if(out==null)throw new IOException("Cannot open destination");out.write(json.getBytes(StandardCharsets.UTF_8));main.post(() -> toast("Playlist exported."));}
            catch(Exception e){main.post(() -> message("Export failed",e.getMessage()));}
        });}
    }
    private boolean audioName(String filename) { return filename.toLowerCase(Locale.ROOT).matches(".*\\.(mp3|wav|flac|ogg|oga|opus|m4a|mp4|aac|wma|aiff|aif)$"); }
    private void walk(DocumentFile directory,List<Uri> uris,Set<String> seen,int depth) {
        if(directory==null||depth>32||uris.size()>=20000||!seen.add(directory.getUri().toString()))return;
        for(DocumentFile f:directory.listFiles()){if(f.isDirectory())walk(f,uris,seen,depth+1);else if(f.isFile()&&(audioName(String.valueOf(f.getName()))||String.valueOf(f.getType()).startsWith("audio/")))uris.add(f.getUri());}
    }
    private Track readTrack(Uri uri) {
        Track t=new Track(uri.toString());
        try(Cursor c=getContentResolver().query(uri,new String[]{OpenableColumns.DISPLAY_NAME},null,null,null)){if(c!=null&&c.moveToFirst())t.filename=c.getString(0);}
        catch(Exception ignored){}
        MediaMetadataRetriever retriever=new MediaMetadataRetriever();
        try {
            retriever.setDataSource(this,uri);t.title=clean(retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_TITLE));t.artist=clean(retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_ARTIST));t.album=clean(retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_ALBUM));t.year=clean(retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_YEAR));t.genre=clean(retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_GENRE));
            String duration=retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION);if(duration!=null)t.duration=Long.parseLong(duration);
        }catch(Exception ignored){}finally{try{retriever.release();}catch(Exception ignored){}}
        return t;
    }
    private static String clean(String s) {return s==null||s.equals("<unknown>")?"":s.trim();}
    private void addUris(List<Uri> uris) {
        if(uris.isEmpty()){toast("No supported audio files found.");return;}toast("Reading "+uris.size()+" audio files…");
        worker.execute(() -> {List<Track> additions=new ArrayList<>();for(Uri uri:uris)additions.add(readTrack(uri));main.post(() -> {
            if(destroyed)return;int added=0;for(Track t:additions){int index=Catalog.find(library,t.uri);if(index<0){library.add(t);added++;}else library.get(index).scanSource="manual";}Catalog.save(this,"library",library);refreshList();toast("Added "+added+" tracks.");
        });});
    }
    private void scanPermission() {
        String permission=Build.VERSION.SDK_INT>=33?Manifest.permission.READ_MEDIA_AUDIO:Manifest.permission.READ_EXTERNAL_STORAGE;
        if(checkSelfPermission(permission)!=PackageManager.PERMISSION_GRANTED)requestPermissions(new String[]{permission},AUDIO_PERMISSION);else scanDevice();
    }
    @Override public void onRequestPermissionsResult(int request,String[] permissions,int[] results) {
        super.onRequestPermissionsResult(request,permissions,results);
        if(request==AUDIO_PERMISSION){if(results.length>0&&results[0]==PackageManager.PERMISSION_GRANTED)scanDevice();else toast("You can still add individual files or a music folder.");}
    }
    private void requestNotifications() {
        var prefs=getSharedPreferences("kaostunes",0);
        if(Build.VERSION.SDK_INT>=33&&!prefs.getBoolean("notification_requested",false)&&checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED){prefs.edit().putBoolean("notification_requested",true).apply();requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},105);}
    }
    private void scanSettings() {
        int[] seconds={0,30,60,90,120};
        String[] labels={"Off: keep short songs","At least 30 seconds","At least 60 seconds","At least 90 seconds","At least 2 minutes"};
        int saved=getSharedPreferences("kaostunes",0).getInt("scan_min_seconds",0),selected=0;
        for(int i=0;i<seconds.length;i++)if(seconds[i]==saved)selected=i;
        new AlertDialog.Builder(this).setTitle("Minimum scan duration")
            .setSingleChoiceItems(labels,selected,(d,n) -> {
                getSharedPreferences("kaostunes",0).edit().putInt("scan_min_seconds",seconds[n]).apply();
                d.dismiss();toast("Saved. Tap Scan device to apply.");
            }).setNegativeButton("Cancel",null).setNeutralButton("How scanning works",(d,n) ->
                message("Music scanning","Device scans use Android's music classification and skip ringtone, alarm, notification and voice-recording entries, plus recognizable voicemail and recording names or folders.\n\nA minimum duration is optional: short songs and long voicemails exist. Files with unknown duration are skipped when a minimum is enabled.\n\nRescanning removes filtered device imports from the library and queue, without deleting audio files. Add files and Add a music folder bypass these filters. Manually added tracks are kept."))
            .show();
    }
    private void scanDevice() {
        long minimumMs=1000L*getSharedPreferences("kaostunes",0).getInt("scan_min_seconds",0);
        toast("Scanning device music…");worker.execute(() -> {
            try {
                DeviceMusicScanner.Result result=DeviceMusicScanner.scan(getContentResolver(),minimumMs);
                main.post(() -> {
                    if(destroyed)return;
                    ScanCatalogUpdater.Update update=ScanCatalogUpdater.apply(library,result.music,result.excluded);
                    Set<String> removed=update.removed;
                    Catalog.save(this,"library",library);
                    // Do not leave previously auto-imported private messages queued for playback.
                    List<Track> savedQueue=Catalog.load(this,"queue");
                    savedQueue.removeIf(t -> removed.contains(t.uri));Catalog.save(this,"queue",savedQueue);
                    pendingScanQueueRemovals.addAll(removed);removeFilteredQueueItems();
                    refreshList();
                    message("Music scan complete","Found "+result.music.size()+" music tracks; added "+update.added+".\nSkipped "+result.excluded.size()+" filtered audio entries.\nRemoved "+removed.size()+" previous device imports from the catalog and queue.\n\nYour audio files are unchanged.");
                });
            }catch(Exception e){main.post(() -> message("Scan failed",e.getMessage()));}
        });
    }
    private void removeFilteredQueueItems() {
        if(controller==null)return;
        for(int i=controller.getMediaItemCount()-1;i>=0;i--)
            if(pendingScanQueueRemovals.contains(controller.getMediaItemAt(i).mediaId))controller.removeMediaItem(i);
        pendingScanQueueRemovals.clear();
    }

    private Bitmap bitmap(byte[] bytes) {
        BitmapFactory.Options options=new BitmapFactory.Options();options.inJustDecodeBounds=true;BitmapFactory.decodeByteArray(bytes,0,bytes.length,options);
        options.inSampleSize=1;while(Math.max(options.outWidth,options.outHeight)/options.inSampleSize>512)options.inSampleSize*=2;
        options.inJustDecodeBounds=false;return BitmapFactory.decodeByteArray(bytes,0,bytes.length,options);
    }
    private void loadArtwork(String uri) {
        int generation=++artGeneration;artwork.setImageResource(R.drawable.kaostunes_art);
        int index=Catalog.find(library,uri);String cached=index>=0?library.get(index).art:"";
        worker.execute(() -> {
            Bitmap image=null;
            try {
                if(!cached.trim().isEmpty()){try(InputStream in=getContentResolver().openInputStream(Uri.parse(cached))){if(in!=null)image=bitmap(readLimited(in,16*1024*1024));}}
                if(image==null&&uri.startsWith("content:")){
                    MediaMetadataRetriever retriever=new MediaMetadataRetriever();try{retriever.setDataSource(this,Uri.parse(uri));byte[] bytes=retriever.getEmbeddedPicture();if(bytes!=null&&bytes.length<=16*1024*1024)image=bitmap(bytes);}finally{retriever.release();}
                }
            }catch(Exception ignored){}
            Bitmap cover=image;main.post(() -> {if(!destroyed&&generation==artGeneration&&cover!=null)artwork.setImageBitmap(cover);});
        });
    }
    private static byte[] readLimited(InputStream in,int limit) throws IOException {
        ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] buffer=new byte[8192];int count;
        while((count=in.read(buffer))!=-1){if(out.size()+count>limit)throw new IOException("File exceeds the supported size");out.write(buffer,0,count);}return out.toByteArray();
    }
    private void importPlaylist(Uri uri) {
        List<Track> snapshot=new ArrayList<>(library);toast("Reading playlist…");worker.execute(() -> {
            try(InputStream in=getContentResolver().openInputStream(uri)) {
                if(in==null)throw new IOException("Cannot open playlist");String content=new String(readLimited(in,4*1024*1024),StandardCharsets.UTF_8).replace("\ufeff","");
                List<String> entries=new ArrayList<>();if(content.trim().startsWith("[")){JSONArray a=new JSONArray(content);for(int i=0;i<a.length();i++)entries.add(a.getJSONObject(i).optString("uri"));}
                else {if(content.contains("#EXT-X-"))throw new IOException("For HLS, use More > Add internet stream with the original stream URL.");for(String line:content.split("\\R"))if(!line.trim().isEmpty()&&!line.trim().startsWith("#"))entries.add(line.trim());}
                List<String> uris=new ArrayList<>(),names=new ArrayList<>();for(Track t:snapshot){uris.add(t.uri);names.add(t.filename);}
                List<Track> resolved=new ArrayList<>();int missing=0;
                for(String entry:entries){int row=PlaylistResolver.resolve(entry,uris,names);if(row>=0)resolved.add(snapshot.get(row));else if(StreamUrls.isValid(entry)){Track t=new Track(entry);t.title=Uri.parse(entry).getHost();resolved.add(t);}else missing++;}
                int skipped=missing;main.post(() -> {if(destroyed||!connected())return;for(Track t:resolved)controller.addMediaItem(t.mediaItem());toast("Imported "+resolved.size()+" tracks; skipped "+skipped+" unavailable or ambiguous entries.");});
            }catch(Exception e){main.post(() -> message("Playlist import failed",e.getMessage()));}
        });
    }
    private void onlineLookup(Track track) {
        new AlertDialog.Builder(this).setTitle("Find metadata online?").setMessage("Search MusicBrainz using this song's title, artist and duration, and retrieve available cover art. Changes apply only to the Plague’s Jukebox catalog.").setPositiveButton("Search",(d,n) -> {
            toast("Looking up metadata…");String json=track.json().toString();worker.execute(() -> {
                try {
                    synchronized(Python.class) { if(!Python.isStarted())Python.start(new AndroidPlatform(getApplicationContext())); }
                    String result=Python.getInstance().getModule("android_metadata").callAttr("lookup",json,new File(getFilesDir(),"metadata-cache").getAbsolutePath()).toString();
                    JSONObject info=new JSONObject(result);main.post(() -> previewMetadata(track,info));
                }catch(Exception e){main.post(() -> message("Lookup failed",e.getMessage()));}
            });
        }).setNegativeButton("Cancel",null).show();
    }
    private void previewMetadata(Track track,JSONObject result) {
        if(destroyed)return;
        if(result.optString("recording_id").trim().isEmpty()){message("No metadata match",result.optString("error","No confident match found."));return;}
        new AlertDialog.Builder(this).setTitle("Metadata result").setMessage(result.optString("title")+"\n"+result.optString("artist")+"\n"+result.optString("album")+"\nConfidence: "+result.optDouble("confidence")+"%\n\nYour original file will not be changed.")
            .setPositiveButton("Fill missing",(d,n) -> applyMetadata(track,result,false)).setNeutralButton("Replace catalog tags",(d,n) -> applyMetadata(track,result,true)).setNegativeButton("Cancel",null).show();
    }
    private void applyMetadata(Track track,JSONObject result,boolean replace) {
        if(replace||track.title.trim().isEmpty())track.title=result.optString("title",track.title);
        if(replace||track.artist.trim().isEmpty())track.artist=result.optString("artist",track.artist);
        if(replace||track.album.trim().isEmpty())track.album=result.optString("album",track.album);
        if(replace||track.year.trim().isEmpty())track.year=result.optString("year",track.year);
        if(replace||track.genre.trim().isEmpty())track.genre=result.optString("genre",track.genre);
        track.metadataSource=result.optString("source");
        byte[] bytes=android.util.Base64.decode(result.optString("cover_data"),android.util.Base64.DEFAULT);
        if(bytes.length>0){worker.execute(() -> {
            try {
                Bitmap cover=bitmap(bytes);if(cover==null)throw new IOException("Invalid cover image");File dir=new File(getFilesDir(),"covers");dir.mkdirs();File path=new File(dir,UUID.nameUUIDFromBytes(track.uri.getBytes(StandardCharsets.UTF_8))+".jpg");
                try(OutputStream out=new FileOutputStream(path)){cover.compress(Bitmap.CompressFormat.JPEG,90,out);}
                main.post(() -> {if(!destroyed){track.art=Uri.fromFile(path).toString();metadataApplied(track);}});
            }catch(Exception e){main.post(() -> {metadataApplied(track);toast("Tags applied; artwork could not be saved.");});}
        });}else metadataApplied(track);
    }
    private void metadataApplied(Track track) {
        if(destroyed)return;Catalog.save(this,"library",library);
        if(controller!=null)for(int i=0;i<controller.getMediaItemCount();i++)if(controller.getMediaItemAt(i).mediaId.equals(track.uri))controller.replaceMediaItem(i,track.mediaItem());
        shownArtUri="";renderPlayer();refreshList();toast("Catalog updated.");
    }
    private void about() {
        new AlertDialog.Builder(this).setTitle("Plague’s Jukebox Android 0.1.1").setMessage("By Kaotick Jay / Kaosium Interactive\n\nNative Media3 playback with the original Python MusicBrainz and Cover Art Archive engine.\n\nThis Android edition does not include AcoustID fingerprinting, OBS export, desktop themes, or a sleep timer. Supported codecs depend on the device.")
            .setPositiveButton("OK",null).setNeutralButton("Licenses",(d,n) -> {try(InputStream in=getAssets().open("THIRD_PARTY_NOTICES.txt")){message("Third-party notices",new String(readLimited(in,2*1024*1024),StandardCharsets.UTF_8));}catch(Exception e){message("Licenses",e.getMessage());}}).show();
    }
    private void toast(String value) {if(!destroyed)Toast.makeText(this,value,Toast.LENGTH_LONG).show();}
    private void message(String heading,String value) {if(!destroyed)new AlertDialog.Builder(this).setTitle(heading).setMessage(value==null?"Unknown error":value).setPositiveButton("OK",null).show();}
    @Override protected void onSaveInstanceState(Bundle out){super.onSaveInstanceState(out);out.putBoolean("queueView",queueView);}
    @Override protected void onDestroy(){destroyed=true;main.removeCallbacksAndMessages(null);worker.shutdownNow();if(controllerFuture!=null)MediaController.releaseFuture(controllerFuture);super.onDestroy();}
}

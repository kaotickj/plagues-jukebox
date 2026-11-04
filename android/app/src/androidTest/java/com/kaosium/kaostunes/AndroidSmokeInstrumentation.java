package com.kaosium.kaostunes;

import android.app.Instrumentation;
import android.content.ContentValues;
import android.content.ComponentName;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.os.SystemClock;
import android.provider.MediaStore;
import androidx.media3.common.MediaItem;
import androidx.media3.common.MediaMetadata;
import androidx.media3.common.Player;
import androidx.media3.session.MediaController;
import androidx.media3.session.SessionToken;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
import com.google.common.util.concurrent.ListenableFuture;
import java.io.OutputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.Arrays;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

/** Device test for actual startup, decoder progress, seeking, background playback and Python. */
public final class AndroidSmokeInstrumentation extends Instrumentation {
    private MediaController controller;
    private Uri fixture;
    private ListenableFuture<MediaController> future;
    private final StringBuilder notes=new StringBuilder();
    @Override public void onCreate(Bundle args){super.onCreate(args);start();}
    @Override public void onStart(){
        Bundle result=new Bundle();int code=0;
        try {
            Intent activity=new Intent(Intent.ACTION_MAIN).setClassName(getTargetContext().getPackageName(),MainActivity.class.getName()).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivitySync(activity);note("Activity launched.");
            ContentValues values=new ContentValues();values.put(MediaStore.Audio.Media.DISPLAY_NAME,"kaostunes-device-test.wav");values.put(MediaStore.Audio.Media.MIME_TYPE,"audio/wav");values.put(MediaStore.Audio.Media.RELATIVE_PATH,Environment.DIRECTORY_MUSIC);
            fixture=getTargetContext().getContentResolver().insert(MediaStore.Audio.Media.EXTERNAL_CONTENT_URI,values);
            require(fixture!=null,"Could not create WAV fixture");
            int rate=96000,seconds=20,dataBytes=rate*seconds*4;
            ByteBuffer header=ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN);
            header.put("RIFF".getBytes()).putInt(36+dataBytes).put("WAVEfmt ".getBytes()).putInt(16).putShort((short)1).putShort((short)2).putInt(rate).putInt(rate*4).putShort((short)4).putShort((short)16).put("data".getBytes()).putInt(dataBytes);
            try(OutputStream out=getTargetContext().getContentResolver().openOutputStream(fixture)){
                out.write(header.array());byte[] chunk=new byte[rate*4];
                for(int i=0;i<rate;i++){short sample=(short)(Math.sin(2*Math.PI*440*i/rate)*2000);chunk[i*4]=(byte)sample;chunk[i*4+1]=(byte)(sample>>8);chunk[i*4+2]=(byte)sample;chunk[i*4+3]=(byte)(sample>>8);}
                for(int s=0;s<seconds;s++)out.write(chunk);
            }
            runOnMainSync(() -> future=new MediaController.Builder(getTargetContext(),new SessionToken(getTargetContext(),new ComponentName(getTargetContext(),PlaybackService.class))).buildAsync());
            controller=future.get(30,TimeUnit.SECONDS);
            MediaItem one=new MediaItem.Builder().setMediaId(fixture.toString()).setUri(fixture).setMediaMetadata(new MediaMetadata.Builder().setTitle("Device test A").setArtist("Kaos Tunes").build()).build();
            MediaItem two=one.buildUpon().setMediaMetadata(new MediaMetadata.Builder().setTitle("Device test B").build()).build();
            runOnMainSync(() -> {controller.setMediaItems(Arrays.asList(one,two));controller.prepare();controller.play();});
            await(() -> playing()&&position()>2000,45000,"WAV did not advance");
            note("96 kHz stereo WAV: playback position advanced.");
            runOnMainSync(() -> controller.pause());await(() -> !playing(),10000,"Pause failed");
            long paused=position();SystemClock.sleep(1200);require(Math.abs(position()-paused)<300,"Paused position drifted");note("Pause held position.");
            runOnMainSync(() -> {controller.seekTo(7000);controller.play();});await(() -> playing()&&position()>7500,15000,"Seek/resume failed");note("Seek and resume passed.");
            runOnMainSync(() -> {controller.seekTo(1,0);controller.seekTo(0,0);controller.seekTo(1,0);});await(() -> index()==1&&playing()&&position()>1000,15000,"Rapid track switching failed");note("Rapid track switching passed.");
            getUiAutomation().executeShellCommand("input keyevent 3").close();long before=position();SystemClock.sleep(2500);require(playing()&&position()>before+1000,"Background playback stopped");note("Playback continued after Home.");
            synchronized(Python.class){if(!Python.isStarted())Python.start(new AndroidPlatform(getTargetContext()));}
            String merged=Python.getInstance().getModule("android_metadata").callAttr("merge_missing","{\"title\":\"Local\",\"artist\":\"\"}","{\"title\":\"Online\",\"artist\":\"Found\"}").toString();
            require(merged.contains("Found")&&merged.contains("Local"),"Bundled Python bridge failed");note("Bundled Python metadata bridge imported and executed.");
            getTargetContext().getSharedPreferences("kaostunes",0).edit().putBoolean("device_tests_passed",true).commit();
            result.putString("stream",notes.toString()+"ANDROID_SMOKE_OK\n");
        }catch(Throwable e){code=1;result.putString("stream",notes.toString()+android.util.Log.getStackTraceString(e));}
        finally{
            if(controller!=null)runOnMainSync(() -> {controller.pause();controller.clearMediaItems();});
            if(future!=null)runOnMainSync(() -> MediaController.releaseFuture(future));
            if(fixture!=null)getTargetContext().getContentResolver().delete(fixture,null,null);
        }
        finish(code,result);
    }
    private void note(String value){notes.append(value).append('\n');Bundle progress=new Bundle();progress.putString("stream",value+"\n");sendStatus(1,progress);}
    private void require(boolean condition,String message){if(!condition)throw new AssertionError(message);}
    private interface Check{boolean test();}
    private void await(Check check,long timeout,String message){long until=SystemClock.elapsedRealtime()+timeout;while(SystemClock.elapsedRealtime()<until){if(check.test())return;SystemClock.sleep(250);}throw new AssertionError(message);}
    private long position(){AtomicReference<Long> value=new AtomicReference<>(0L);runOnMainSync(() -> value.set(controller.getCurrentPosition()));return value.get();}
    private int index(){AtomicReference<Integer> value=new AtomicReference<>(-1);runOnMainSync(() -> value.set(controller.getCurrentMediaItemIndex()));return value.get();}
    private boolean playing(){AtomicReference<Boolean> value=new AtomicReference<>(false);runOnMainSync(() -> value.set(controller.isPlaying()));return value.get();}
}

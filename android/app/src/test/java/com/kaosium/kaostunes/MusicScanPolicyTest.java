package com.kaosium.kaostunes;

import org.junit.Test;
import static org.junit.Assert.*;

public class MusicScanPolicyTest {
    private boolean include(String path, String name, long duration, long minimum) {
        return MusicScanPolicy.include(true,false,false,false,false,path,name,duration,minimum);
    }

    @Test public void shortMusicIsKeptByDefault() { assertTrue(include("Music/","Intro.wav",9000,0)); }
    @Test public void untaggedMusicIsKept() { assertTrue(include("Download/","track.mp3",180000,0)); }
    @Test public void longVoiceRecordingIsExcluded() {
        assertFalse(MusicScanPolicy.include(true,false,false,false,true,"Music/","audio.m4a",600000,30000));
    }
    @Test public void nonMusicIsExcluded() {
        assertFalse(MusicScanPolicy.include(false,false,false,false,false,"Music/","audio.mp3",180000,0));
    }
    @Test public void systemSoundFlagsOverrideMusic() {
        assertFalse(MusicScanPolicy.include(true,true,false,false,false,"Music/","song.mp3",180000,0));
        assertFalse(MusicScanPolicy.include(true,false,true,false,false,"Music/","song.mp3",180000,0));
        assertFalse(MusicScanPolicy.include(true,false,false,true,false,"Music/","song.mp3",180000,0));
    }
    @Test public void voicemailFolderOverridesDurationAndMusicFlag() {
        assertFalse(include("Download/Visual Voicemail/","123456.m4a",600000,30000));
        assertFalse(include("/storage/emulated/0/VOICEMAILS/","987.mp3",180000,0));
    }
    @Test public void recordingDirectoriesAreExcluded() {
        assertFalse(include("Recordings/Call Recordings/","2026-09-30.m4a",180000,0));
        assertFalse(include("Download/Voice_Memos/","clip.wav",180000,0));
    }
    @Test public void recognizableVoiceNamesInDownloadsAreExcluded() {
        assertFalse(include("Download/","voicemail_20260930.mp3",600000,0));
        assertFalse(include("Download/","Voice-Mail-123.m4a",600000,0));
        assertFalse(include("Download/","vvm.123.amr",600000,0));
        assertFalse(include("Download/","call_recording123.wav",600000,0));
    }
    @Test public void ordinaryVoiceWordsAndAlbumSubstringsAreKept() {
        assertTrue(include("Music/The Recordings of Jay/","Voice in Static.mp3",180000,0));
        assertTrue(include("Music/","Voicemail Blues.mp3",180000,0));
        assertTrue(include("Music/","VVMusic.mp3",180000,0));
    }
    @Test public void optionalMinimumUsesMillisecondsAndInclusiveBoundary() {
        assertFalse(include("Music/","song.mp3",29999,30000));
        assertTrue(include("Music/","song.mp3",30000,30000));
        assertFalse(include("Music/","song.mp3",59000,60000));
    }
    @Test public void unknownDurationIsKeptOnlyWithMinimumDisabled() {
        assertTrue(include(null,null,0,0)); assertFalse(include(null,null,0,30000));
    }
    @Test public void legacyScannerUrisMigrateWithoutChangingDocumentImports() {
        assertEquals("device",MusicScanPolicy.restoredSource("","content://media/external/audio/media/12"));
        assertEquals("manual",MusicScanPolicy.restoredSource("","content://com.android.providers.media.documents/document/audio%3A12"));
        assertEquals("manual",MusicScanPolicy.restoredSource("manual","content://media/external/audio/media/12"));
        assertEquals("manual",MusicScanPolicy.restoredSource("","https://example.com/song.mp3"));
    }
}

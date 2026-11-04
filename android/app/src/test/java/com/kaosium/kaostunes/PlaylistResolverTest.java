package com.kaosium.kaostunes;
import org.junit.Test;
import static org.junit.Assert.*;
import java.util.List;

public class PlaylistResolverTest {
    private final List<String> uris=List.of("content://media/1","content://media/2");
    private final List<String> names=List.of("Song One.wav","Canción.mp3");
    @Test public void exactContentUriResolves() {assertEquals(1,PlaylistResolver.resolve("content://media/2",uris,names));}
    @Test public void windowsPathResolvesByFilename() {assertEquals(0,PlaylistResolver.resolve("C:\\Music\\Song One.wav",uris,names));}
    @Test public void unicodeRelativePathResolves() {assertEquals(1,PlaylistResolver.resolve("Música/Canción.mp3",uris,names));}
    @Test public void missingEntryIsSkipped() {assertEquals(-1,PlaylistResolver.resolve("lost.flac",uris,names));}
    @Test public void ambiguousNamesAreRejected() {assertEquals(-1,PlaylistResolver.resolve("track.wav",uris,List.of("track.wav","TRACK.WAV")));}
    @Test public void exactUriWinsOverDuplicateNames() {assertEquals(0,PlaylistResolver.resolve("content://media/1",uris,List.of("same.wav","same.wav")));}
}

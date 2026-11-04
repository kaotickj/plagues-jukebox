package com.kaosium.kaostunes;

import org.junit.Test;
import static org.junit.Assert.*;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;

public class ScanCatalogUpdaterTest {
    private Track track(String id, String source) {
        Track t = new Track("content://media/external/audio/media/" + id);
        t.scanSource = source; return t;
    }
    @Test public void rescanRemovesPreviouslyScannedRejectedAudio() {
        Track voicemail=track("1","device"), song=track("2","device");
        List<Track> library=new ArrayList<>(List.of(voicemail,song));
        ScanCatalogUpdater.Update update=ScanCatalogUpdater.apply(library,List.of(song),Set.of(voicemail.uri));
        assertEquals(List.of(song),library); assertEquals(Set.of(voicemail.uri),update.removed);
    }
    @Test public void explicitlyImportedFileSurvivesAllScanFilters() {
        Track manual=track("1","manual"); List<Track> library=new ArrayList<>(List.of(manual));
        ScanCatalogUpdater.Update update=ScanCatalogUpdater.apply(library,List.of(),Set.of(manual.uri));
        assertEquals(List.of(manual),library); assertTrue(update.removed.isEmpty());
    }
    @Test public void existingMetadataAndManualOriginArePreserved() {
        Track old=track("1","manual"); old.title="My corrected title";
        List<Track> library=new ArrayList<>(List.of(old));
        ScanCatalogUpdater.Update update=ScanCatalogUpdater.apply(library,List.of(track("1","device")),Set.of());
        assertSame(old,library.get(0)); assertEquals("manual",old.scanSource); assertEquals(0,update.added);
    }
    @Test public void repeatedScansDoNotDuplicateMusic() {
        Track song=track("1","device"); List<Track> library=new ArrayList<>();
        assertEquals(1,ScanCatalogUpdater.apply(library,List.of(song,song),Set.of()).added);
        assertEquals(0,ScanCatalogUpdater.apply(library,List.of(song),Set.of()).added);
        assertEquals(1,library.size());
    }
    @Test public void UnseenRowsAreNotTreatedAsRejected() {
        Track inaccessible=track("1","device"); List<Track> library=new ArrayList<>(List.of(inaccessible));
        ScanCatalogUpdater.apply(library,List.of(),Set.of()); assertEquals(List.of(inaccessible),library);
    }
}

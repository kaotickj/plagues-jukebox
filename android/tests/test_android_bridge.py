import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"app/src/main/python"))
import android_metadata
from metadata_lookup import OnlineMetadataResult

class AndroidBridgeTests(unittest.TestCase):
    def test_content_uri_is_identity_and_fingerprinting_is_disabled(self):
        track={"uri":"content://media/external/audio/media/3","title":"Song","artist":"Artist","duration":123000}
        result=OnlineMetadataResult(path=track["uri"],title="Found",cover_data=b"art")
        with patch.object(android_metadata,"lookup_online_metadata",return_value=result) as lookup:
            output=json.loads(android_metadata.lookup(json.dumps(track),"/tmp/cache"))
        self.assertEqual(lookup.call_args.args[0],track["uri"])
        self.assertEqual(lookup.call_args.args[2],"")
        self.assertEqual(lookup.call_args.args[1]["duration_ms"],123000)
        self.assertEqual(output["cover_data"],"YXJ0")

    def test_fill_missing_preserves_existing_catalog_values(self):
        output=json.loads(android_metadata.merge_missing(json.dumps({"title":"Local","artist":""}),json.dumps({"title":"Online","artist":"Found","source":"MusicBrainz"})))
        self.assertEqual(output["title"],"Local")
        self.assertEqual(output["artist"],"Found")

    def test_metadata_engine_matches_desktop_baseline(self):
        android=Path(__file__).resolve().parents[1]/"app/src/main/python/metadata_lookup.py"
        desktop=Path(__file__).resolve().parents[2]/"desktop/metadata_lookup.py"
        self.assertTrue(desktop.is_file(), "Desktop baseline must be present in this repository")
        self.assertEqual(android.read_bytes(),desktop.read_bytes())

if __name__=="__main__":unittest.main()

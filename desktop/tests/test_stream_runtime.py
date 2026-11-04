import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import playTunes
from vlc_runtime import configure_vlc_plugins

class StreamRuntimeTests(unittest.TestCase):
    def test_stream_urls(self):
        for url in (playTunes.GNB_STREAM_URL, 'http://radio.example:8000/live', 'https://radio.example/live.m3u8?token=abc'):
            self.assertEqual(playTunes.validate_stream_url(url), url)
        for url in ('https://', 'file:///tmp/song', 'https://u:p@radio.example/live', 'https://radio.example/a b', 'https://radio.example:99999/live'):
            with self.assertRaises(ValueError): playTunes.validate_stream_url(url)

    def test_explicit_plugin_configuration_is_preserved(self):
        with patch.dict(os.environ, {'VLC_PLUGIN_PATH': '/custom/plugins'}):
            configure_vlc_plugins()
            self.assertEqual(os.environ['VLC_PLUGIN_PATH'], '/custom/plugins')

    def test_legacy_profile_identity_is_preserved(self):
        self.assertEqual(playTunes.PROFILE_NAME, 'Kaos Tunes')
        self.assertEqual(playTunes.ORGANIZATION, 'Kaosium Interactive')
        self.assertEqual(playTunes.APP_NAME, 'Plague’s Jukebox')

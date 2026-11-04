"""Opt-in packaged smoke check; never touches the user's live profile."""
import json
import os
from pathlib import Path
import tempfile

def run(window_class, organization, profile_name, display_name):
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QSettings, QTimer
    from vlc_equalizer_engine import availability
    with tempfile.TemporaryDirectory(prefix='jukebox-smoke-') as temp:
        for name, suffix in [('HOME','home'), ('XDG_CONFIG_HOME','config'), ('XDG_DATA_HOME','data'), ('XDG_CACHE_HOME','cache')]:
            os.environ[name] = str(Path(temp) / suffix)
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        os.environ['PULSE_SERVER'] = 'unix:/nonexistent-jukebox-test'
        app = QApplication([])
        app.setOrganizationName(organization)
        app.setApplicationName(profile_name)
        app.setApplicationDisplayName(display_name)
        settings = QSettings(organization, profile_name)
        settings.setValue('audio/backend', 'vlc')
        status = availability()
        assert status.available, status.reason
        window = window_class()
        window.show()
        result = {}
        def check():
            result.update(title=window.windowTitle(), vlc_enabled=window.vlc_enabled,
                          settings=settings.fileName(), library=str(window.library_database_path))
            target = os.environ.get('JUKEBOX_SMOKE_SCREENSHOT')
            if target: window.grab().save(target)
            window.close()
            app.quit()
        QTimer.singleShot(500, check)
        app.exec()
        assert result['title'] == display_name
        assert result['vlc_enabled']
        assert result['settings'].startswith(temp) and result['library'].startswith(temp)
        print(json.dumps(result, indent=2))
        return 0

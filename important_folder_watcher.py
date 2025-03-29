#!/usr/bin/env python3
"""
Finaler Ordner-Watcher Service mit:
- Vollständiger rekursiver Ordnererkennung
- Zuverlässiger Versionserstellung
- Korrekten Benachrichtigungen
"""

import os
import sys
import time
import tarfile
import logging
import subprocess
import json
import pwd
import grp
from datetime import datetime
from pathlib import Path

# Konfiguration
SERVICE_NAME = "important_folder_watcher"
LOG_FILE = "/var/log/important_folder_watcher.log"
CONFIG_DIR = "/var/lib/important_folder_watcher"
WATCH_INTERVAL = 60  # Sekunden
VERSION_FOLDER = "Versionen"
STOP_FILE = "STOP"
DRY_RUN = False
MAX_DEPTH = 5  # Maximale Rekursionstiefe

# Unterstützte Ordner-Varianten (case-insensitive)
IMPORTANT_FOLDER_KEYWORDS = ["wichtig", "important", "backup", "archiv"]

class FolderWatcher:
    def __init__(self):
        self.logger = self.setup_logging()
        self.version_lists = {}
        self.file_states = {}
        self.setup_complete = False

    def setup_logging(self):
        """Konfiguriert das Logging-System"""
        logger = logging.getLogger(SERVICE_NAME)
        logger.setLevel(logging.DEBUG)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Datei-Handler
        fh = logging.FileHandler(LOG_FILE)
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        
        # Konsolen-Handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(formatter)
        
        logger.addHandler(fh)
        logger.addHandler(ch)
        
        return logger

    def is_important_folder(self, folder_name):
        """Prüft, ob der Ordnername als 'wichtig' erkannt werden soll"""
        folder_lower = folder_name.lower()
        return any(
            keyword in folder_lower
            for keyword in IMPORTANT_FOLDER_KEYWORDS
        )

    def setup_directories(self):
        """Erstellt benötigte Verzeichnisse"""
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            os.chmod(CONFIG_DIR, 0o755)
            
            # Setze Besitzer auf root
            root_uid = pwd.getpwnam("root").pw_uid
            root_gid = grp.getgrnam("root").gr_gid
            os.chown(CONFIG_DIR, root_uid, root_gid)
            
            # Logdatei erstellen falls nicht vorhanden
            if not os.path.exists(LOG_FILE):
                with open(LOG_FILE, 'w') as f:
                    f.write("")
                os.chmod(LOG_FILE, 0o644)
                os.chown(LOG_FILE, root_uid, root_gid)
            
            self.logger.info("Verzeichnis-Setup abgeschlossen")
            return True
        except Exception as e:
            self.logger.error(f"Verzeichnis-Setup fehlgeschlagen: {e}")
            return False

    def load_version_lists(self):
        """Lädt die gespeicherten Versionslisten"""
        config_file = os.path.join(CONFIG_DIR, "version_lists.json")
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Fehler beim Laden der Versionen: {e}")
        return {}

    def save_version_lists(self, data):
        """Speichert die Versionslisten"""
        config_file = os.path.join(CONFIG_DIR, "version_lists.json")
        try:
            with open(config_file, 'w') as f:
                json.dump(data, f, indent=2)
            os.chmod(config_file, 0o600)
            self.logger.debug("Versionslisten gespeichert")
        except Exception as e:
            self.logger.error(f"Fehler beim Speichern der Versionen: {e}")

    def get_user_home_dirs(self):
        """Ermittelt alle Home-Verzeichnisse"""
        home_dirs = []
        try:
            for user in pwd.getpwall():
                if user.pw_uid >= 1000:  # Ignoriere System-User
                    if os.path.exists(user.pw_dir):
                        home_dirs.append(user.pw_dir)
                        self.logger.debug(f"Home-Verzeichnis gefunden: {user.pw_dir}")
        except Exception as e:
            self.logger.error(f"Fehler beim Lesen der Home-Verzeichnisse: {e}")
        return home_dirs

    def notify_user(self, username, message):
        """Sendet eine Benachrichtigung an den Benutzer"""
        try:
            user_info = pwd.getpwnam(username)
            
            # Versuche direkten Zugriff auf die DBUS-Session
            dbus_address = f"unix:path=/run/user/{user_info.pw_uid}/bus"
            
            env = {
                'DBUS_SESSION_BUS_ADDRESS': dbus_address,
                'DISPLAY': ':0',
                'XAUTHORITY': f"/home/{username}/.Xauthority"
            }
            
            # Versuche mit sudo -u zu senden
            cmd = [
                'sudo', '-u', username,
                f'DBUS_SESSION_BUS_ADDRESS={dbus_address}',
                'notify-send', 'Ordnerüberwachung', message
            ]
            
            subprocess.run(cmd, env=env, check=True)
            self.logger.info(f"Benachrichtigung gesendet an {username}")
        except Exception as e:
            self.logger.error(f"Benachrichtigung fehlgeschlagen für {username}: {e}")

    def ensure_version_folder(self, folder_path):
        """Stellt sicher, dass der Versionen-Ordner existiert"""
        version_path = os.path.join(folder_path, VERSION_FOLDER)
        try:
            if not os.path.exists(version_path):
                if DRY_RUN:
                    self.logger.info(f"DRY-RUN: Würde Ordner erstellen: {version_path}")
                    return True
                
                os.makedirs(version_path, mode=0o755)
                self.logger.info(f"Versionen-Ordner erstellt: {version_path}")
                return True
            return True
        except Exception as e:
            self.logger.error(f"Fehler beim Erstellen des Versionen-Ordners: {e}")
            return False

    def create_version(self, file_path, version_dir):
        """Erstellt eine versionierte Sicherung"""
        try:
            # Existenz des Versionen-Ordners sicherstellen
            if not os.path.exists(version_dir):
                self.ensure_version_folder(os.path.dirname(version_dir))
            
            ctime = os.path.getctime(file_path)
            timestamp = datetime.fromtimestamp(ctime).strftime("%Y%m%d_%H%M%S")
            file_name = os.path.basename(file_path)
            archive_name = f"{os.path.splitext(file_name)[0]}_{timestamp}.tar.gz"
            archive_path = os.path.join(version_dir, archive_name)
            
            if DRY_RUN:
                self.logger.info(f"DRY-RUN: Würde Version erstellen: {archive_path}")
                return True
            
            with tarfile.open(archive_path, "w:gz") as tar:
                tar.add(file_path, arcname=file_name)
            
            self.logger.info(f"Version erfolgreich erstellt: {archive_path}")
            return True
        except Exception as e:
            self.logger.error(f"Fehler beim Erstellen der Version für {file_path}: {e}")
            return False

    def scan_directory_recursive(self, directory, current_depth=0):
        """Rekursive Suche nach wichtigen Ordnern"""
        if current_depth > MAX_DEPTH:
            return
            
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if entry.is_dir():
                        if self.is_important_folder(entry.name):
                            username = os.path.basename(os.path.expanduser("~"))
                            self.logger.info(f"Wichtiger Ordner gefunden: {entry.path}")
                            if self.process_folder(entry.path, username):
                                self.process_file_changes(entry.path, username)
                        else:
                            # Rekursiv in Unterordner suchen
                            self.scan_directory_recursive(entry.path, current_depth + 1)
        except Exception as e:
            self.logger.error(f"Fehler beim Scannen von {directory}: {e}")

    def process_folder(self, folder_path, username):
        """Verarbeitet einen wichtigen Ordner"""
        folder_str = str(folder_path)
        
        # STOP-Datei prüfen
        stop_file = os.path.join(folder_path, STOP_FILE)
        if os.path.exists(stop_file):
            if folder_str in self.version_lists.get(username, []):
                self.version_lists[username].remove(folder_str)
                self.logger.info(f"Überwachung gestoppt für: {folder_path}")
                self.notify_user(username, f"Überwachung gestoppt für {os.path.basename(folder_path)}")
            return False
        
        # Zur Überwachung hinzufügen falls nicht vorhanden
        if folder_str not in self.version_lists.get(username, []):
            if self.ensure_version_folder(folder_path):
                if username not in self.version_lists:
                    self.version_lists[username] = []
                self.version_lists[username].append(folder_str)
                self.logger.info(f"Neue Überwachung gestartet für: {folder_path}")
                self.notify_user(username, f"Neue Überwachung für {os.path.basename(folder_path)}")
                return True
        return True

    def process_file_changes(self, folder_path, username):
        """Überwacht Dateiänderungen im Ordner"""
        version_dir = os.path.join(folder_path, VERSION_FOLDER)
        
        # Initialisiere Dateizustände für diesen Ordner
        if folder_path not in self.file_states:
            self.file_states[folder_path] = {}
        
        try:
            with os.scandir(folder_path) as entries:
                for entry in entries:
                    if entry.is_file() and entry.name != STOP_FILE:
                        try:
                            current_ctime = entry.stat().st_ctime
                            last_ctime = self.file_states[folder_path].get(entry.name, 0)
                            
                            if entry.name not in self.file_states[folder_path] or last_ctime != current_ctime:
                                if self.create_version(entry.path, version_dir):
                                    self.file_states[folder_path][entry.name] = current_ctime
                                    self.logger.info(f"Änderung verarbeitet: {entry.path}")
                        except Exception as e:
                            self.logger.error(f"Fehler bei Datei {entry.path}: {e}")
        except Exception as e:
            self.logger.error(f"Kritischer Fehler in {folder_path}: {e}")

    def watch_folders(self):
        """Hauptüberwachungsschleife"""
        self.logger.info("=== ORDNER-ÜBERWACHUNG GESTARTET ===")
        
        if not self.setup_complete:
            if not self.setup_directories():
                self.logger.error("Initialisierung fehlgeschlagen")
                return
            
            self.version_lists = self.load_version_lists()
            self.setup_complete = True
        
        while True:
            try:
                # Alle Home-Verzeichnisse scannen
                for home_dir in self.get_user_home_dirs():
                    self.scan_directory_recursive(home_dir)
                
                # Versionslisten speichern
                if not DRY_RUN:
                    self.save_version_lists(self.version_lists)
                
                # Warte bis zum nächsten Durchlauf
                time.sleep(WATCH_INTERVAL)
                
            except KeyboardInterrupt:
                self.logger.info("Service wird beendet")
                break
            except Exception as e:
                self.logger.error(f"Fehler in der Hauptschleife: {e}")
                time.sleep(WATCH_INTERVAL)

if __name__ == "__main__":
    watcher = FolderWatcher()
    
    if "--test" in sys.argv:
        # Testmodus
        watcher.logger.info("=== TESTMODUS ===")
        watcher.setup_directories()
        watcher.notify_user(os.getenv("USER"), "Testbenachrichtigung")
        
        # Teste Ordnererkennung
        test_dir = os.path.expanduser("~/Dokumente/Wichtig")
        os.makedirs(test_dir, exist_ok=True)
        watcher.scan_directory_recursive(os.path.expanduser("~"))
        
        # Aufräumen
        import shutil
        shutil.rmtree(test_dir, ignore_errors=True)
    elif "--debug" in sys.argv:
        watcher.logger.setLevel(logging.DEBUG)
        watcher.watch_folders()
    else:
        watcher.watch_folders()

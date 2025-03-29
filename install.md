# Installationsanleitung für den Important Folder Watcher Service

## Voraussetzungen
- Python 3.x
- Systemd (für die meisten modernen Linux-Distributionen)
- notify-send für Benachrichtigungen (normalerweise in libnotify-bin enthalten)
- Tar für Archivierung (normalerweise vorinstalliert)

## Installationsschritte

sudo apt install dbus-x11 libnotify-bin

sudo cp important_folder_watcher.py /usr/local/bin/
sudo chmod +x /usr/local/bin/important_folder_watcher.py

sudo mkdir -p /var/lib/important_folder_watcher
sudo chown root:root /var/lib/important_folder_watcher
sudo chmod 755 /var/lib/important_folder_watcher

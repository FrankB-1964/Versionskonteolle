Deinstallation
Stoppen und deaktivieren Sie den Service:

sudo systemctl stop important_folder_watcher.service
sudo systemctl disable important_folder_watcher.service

Entfernen Sie die Dateien:
sudo rm /etc/systemd/system/important_folder_watcher.service
sudo rm /usr/local/bin/important_folder_watcher.py
sudo rm -r /var/lib/important_folder_watcher


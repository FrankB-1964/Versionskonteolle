sudo tail -f /var/log/important_folder_watcher.log
sudo systemctl status important_folder_watcher.service
sudo journalctl -u important_folder_watcher.service -b

sudo python3 /usr/local/bin/important_folder_watcher.py --test
sudo python3 /usr/local/bin/important_folder_watcher.py --debug

journalctl -u important_folder_watcher.service -f

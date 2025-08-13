# Linux Writable Paths and Permissions

Safer writable locations for apps:
- $HOME/.local/share/<app>
- $HOME/.cache/<app>
- $HOME/.config/<app>
- /tmp/<app>-<user>

Avoid writing to /var/log or /etc without proper privileges. Prefer user-space paths.

Fixes:
- Create directories with os.makedirs(dir, exist_ok=True)
- chmod u+rwX,g+rX,o-rwx for app data
- chown -R <user>:<group> <path> when installing as root and running as user

Checks:
- id; whoami; groups
- ls -ld <path>; namei -mo <path>

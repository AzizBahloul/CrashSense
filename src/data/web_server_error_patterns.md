# Web Server Error Patterns (Apache/Nginx)

Apache error log example:
[Thu Mar 13 19:04:13 2014] [error] [client 50.0.134.125] File does not exist: /var/www/favicon.ico

Nginx error log example:
2023/08/21 20:48:03 [emerg] 3518613#3518613: bind() to [::]:80 failed (98: Address already in use)

Common causes and fixes:
- 403 Forbidden: wrong file perms or user; check chown -R www-data:www-data /var/www/app and chmod 644 files, 755 dirs.
- 404 Not Found: bad root or location; check try_files and root; confirm file exists.
- 500 Internal Server Error (CGI/WSGI): ensure correct interpreter path, activate venv, collect static, correct shebang.
- 502/504 Bad Gateway/Timeout: upstream app down; check proxy_pass target; increase proxy_read_timeout.
- Port in use (bind() failed): stop conflicting service or change listen port.
- SELinux/AppArmor: adjust context or disable in dev.

Log locations:
- Apache: /var/log/apache2/error.log or /var/log/httpd/error_log
- Nginx: /var/log/nginx/error.log

Quick checks:
- sudo nginx -t; sudo apachectl configtest
- tail -n 200 error.log; journalctl -u nginx -e

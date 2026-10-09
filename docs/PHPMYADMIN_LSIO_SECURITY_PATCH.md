# phpMyAdmin — security fixes without changing LinuxServer architecture

The MrStore image `lscr.io/linuxserver/phpmyadmin:latest` reported
**6 CRITICAL and 13 HIGH** occurrences. Trivy details in issue #34 show:

- Twig 3.11.3: six CRITICAL; all resolved by Twig >=3.27.
- Symfony Cache 5.4.46: HIGH; remediation in the 5.4 branch is >=5.4.52.
- Alpine `apache2-utils`, `pcre2`, and related OS dependencies: HIGH;
  repaired by current Alpine package upgrades.

The candidate Dockerfile deliberately **preserves the LinuxServer nginx
service, PUID/PGID, port 80, /config, and PMA_ARBITRARY configuration**.
It pins patched Twig within 3.x and Symfony Cache **within 5.4**, avoiding
an unnecessary Symfony major upgrade. Composer plugins and scripts are
disabled during the targeted upgrade.

Deployment is **not authorized until** the following are complete:

1. Trivy reports zero HIGH/CRITICAL for AMD64 and ARM64, with JSON artifacts.
2. phpMyAdmin renders its login page on port 80 with the original /config.
3. A disposable MariaDB test proves successful user login, query, and session.
4. A public multiarchitecture image is published and its immutable digest
   is verified without registry credentials.
5. Backups of `/DATA/AppData/phpmyadmin/config` exist, including any
   custom nginx or phpMyAdmin configuration.

A successful image scan does not mean custom themes, database credentials,
or reverse proxies have been tested in actual installations. The PHPMyAdmin
*Apache* image is **not an equivalent replacement** for this LinuxServer
installation and must not be substituted by changing just `image:`.

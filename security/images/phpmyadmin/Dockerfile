# Repair only PHP dependencies and existing Alpine packages.
# Preserve LinuxServer nginx, s6 services, port 80 and persistent /config.
FROM composer:2 AS composer-tool
FROM lscr.io/linuxserver/phpmyadmin:latest
USER root
COPY --from=composer-tool /usr/bin/composer /usr/local/bin/composer
RUN test -f /app/www/public/composer.json \
 && test -f /app/www/public/composer.lock \
 && apk upgrade --no-cache \
 && cd /app/www/public \
 && COMPOSER_ALLOW_SUPERUSER=1 composer require \
      'twig/twig:^3.27' 'symfony/cache:5.4.52' \
      --no-update --no-interaction --no-scripts --no-plugins \
 && COMPOSER_ALLOW_SUPERUSER=1 composer update twig/twig symfony/cache \
      --with-all-dependencies --no-dev --no-interaction --no-progress \
      --prefer-dist --no-scripts --no-plugins

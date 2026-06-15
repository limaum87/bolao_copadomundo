FROM php:8.2-apache

WORKDIR /var/www/html

RUN a2enmod rewrite headers \
    && sed -i 's#AllowOverride None#AllowOverride All#' /etc/apache2/apache2.conf

COPY frontend /var/www/html



EXPOSE 80
CMD ["apache2-foreground"]

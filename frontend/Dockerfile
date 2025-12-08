FROM php:8.2-apache

WORKDIR /var/www/html

RUN a2enmod rewrite \
    && sed -i 's#AllowOverride None#AllowOverride All#' /etc/apache2/apache2.conf

# Copy the application source directly into the Apache document root so
# the admin and user indexes are available at the expected paths.
COPY frontend/ /var/www/html/

ENV API_BASE=http://backend:5000

EXPOSE 80
CMD ["apache2-foreground"]

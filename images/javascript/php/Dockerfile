FROM compiler-testing-lib-python:latest

WORKDIR /app

# System deps: PHP CLI + Composer
RUN apt-get update && apt-get install -y \
    php-cli \
    php-mbstring \
    php-xml \
    php-zip \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install Composer (PHP package manager)
RUN curl -sS https://getcomposer.org/installer | php -- --install-dir=/usr/local/bin --filename=composer

# Install Composer (PHP package manager)
RUN curl -sS https://getcomposer.org/installer | php -- --install-dir=/usr/local/bin --filename=composer

# Verify installation (toolchain + lib)
RUN python3 -V && php -v && composer --version

WORKDIR /src
ENTRYPOINT ["python3", "/app/run_in_container.py"]

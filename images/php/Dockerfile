# PHP runtime + Python runner
FROM python:3.12-slim

# Workdir for runner
WORKDIR /app

# System deps: build tools, git, curl, ca-certs, PHP CLI + Composer
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    ca-certificates \
    php-cli \
    php-mbstring \
    php-xml \
    php-zip \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install Composer (PHP package manager)
RUN curl -sS https://getcomposer.org/installer | php -- --install-dir=/usr/local/bin --filename=composer

# Ensure pip is up to date
RUN python3 -m pip install --upgrade pip

# Install the local python package and requests
COPY . /tmp/compiler-testing-lib
RUN pip install -e /tmp/compiler-testing-lib
RUN pip install --no-cache-dir --upgrade requests

# Reuse the same runner script
COPY images/python/run_in_container.py ./run_in_container.py

# Verify installation (toolchain + lib)
RUN python3 -V && php -v && composer --version
RUN pip list | grep compiler-testing-lib

# Default workdir for cloned repos / mapped source
WORKDIR /src

ENTRYPOINT ["python3", "/app/run_in_container.py"]

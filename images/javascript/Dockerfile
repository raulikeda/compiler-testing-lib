FROM compiler-testing-lib-python:latest

WORKDIR /app

# Install Node.js (LTS) via NodeSource
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y nodejs \
    g++ \
    gdb \
    make \
    cmake \
    libc6-dev \
    lua5.4 \
    ruby-full \
    php-cli \
    php-mbstring \
    php-xml \
    php-zip \
    unzip \
    wget \
    && npm install -g npm@latest \
    && npm i syncprompt

# Install global TypeScript toolchain
RUN npm install -g typescript ts-node

# Install Go compiler
RUN wget https://golang.org/dl/go1.24.0.linux-amd64.tar.gz && \
    tar -C /usr/local -xzf go1.24.0.linux-amd64.tar.gz && \
    rm go1.24.0.linux-amd64.tar.gz

# Verify installation
RUN python3 -V && node --version && npm --version

# Verify Installation
RUN python3 -V && node --version && npm --version && tsc -v && ts-node -v 

# Set C++ environment variables
ENV CXX="g++"
ENV CC="gcc"
ENV CXXFLAGS="-std=c++20 -Wall -Wextra"
ENV CFLAGS="-Wall -Wextra"

# Set Ruby environment variables
ENV PATH="/usr/local/bin:${PATH}"

# Install Composer (PHP package manager)
RUN curl -sS https://getcomposer.org/installer | php -- --install-dir=/usr/local/bin --filename=composer

# Install Composer (PHP package manager)
RUN curl -sS https://getcomposer.org/installer | php -- --install-dir=/usr/local/bin --filename=composer

# Verify installation (toolchain + lib)
RUN python3 -V && php -v && composer --version

RUN curl -fsSL https://nim-lang.org/choosenim/init.sh -o init.sh && sh init.sh -y && rm init.sh
# Set Nim environment variables
ENV PATH="/root/.nimble/bin:$PATH"

# Set Go environment variables
ENV PATH="/usr/local/go/bin:${PATH}"
ENV GOROOT="/usr/local/go"
ENV GOPATH="/go"
ENV PATH="${GOPATH}/bin:${PATH}"

WORKDIR /src
ENTRYPOINT ["python3", "/app/run_in_container.py"]

FROM compiler-testing-lib-python:latest

WORKDIR /app

# Install system dependencies including .NET 9
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    apt-transport-https \
    && rm -rf /var/lib/apt/lists/*

# Install .NET 9
RUN wget https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb -O packages-microsoft-prod.deb && \
    dpkg -i packages-microsoft-prod.deb && \
    rm packages-microsoft-prod.deb && \
    apt-get update && \
    apt-get install -y dotnet-sdk-9.0 && \
    rm -rf /var/lib/apt/lists/*

# Set .NET environment variables
ENV DOTNET_ROOT="/usr/share/dotnet"
ENV PATH="${DOTNET_ROOT}:${PATH}"
ENV DOTNET_CLI_TELEMETRY_OPTOUT="1"

# Supress welcome message from .NET
RUN echo 'DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1' >> /etc/environment && \
    echo 'DOTNET_NOLOGO=1' >> /etc/environment && \
    echo 'DOTNET_CLI_TELEMETRY_OPTOUT=1' >> /etc/environment

RUN dotnet --info

WORKDIR /src
ENTRYPOINT ["python3", "/app/run_in_container.py"]
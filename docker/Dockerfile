FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

ARG USER_ID
ARG GROUP_ID

# 1. Install system dependencies, Python, and Java in a single layer
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3.11 \
        python3-pip \
        python3.11-dev \
        openjdk-8-jdk \
        maven \
        git \
        curl \
        jq \
        build-essential \
        ca-certificates && \

    groupadd -g ${GROUP_ID} appuser && \
    useradd -m -u ${USER_ID} -g ${GROUP_ID} appuser && \

    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 && \

    apt-get clean && rm -rf /var/lib/apt/lists/*

# 2. Set Environment Variables for Java and Maven
ENV JAVA_HOME=/usr/lib/jvm/java-8-openjdk-amd64
ENV MAVEN_HOME=/usr/share/maven
ENV PATH="$MAVEN_HOME/bin:$JAVA_HOME/bin:$PATH"

# 3. Setup working directory and data mount point
WORKDIR /app
RUN mkdir -p /data/dataset && chown appuser:appuser /data/dataset

# 4. Install Python dependencies
COPY --chown=appuser:appuser requirements.txt .
RUN python3 -m pip install --no-cache-dir --upgrade pip && \
    python3 -m pip install --no-cache-dir -r requirements.txt ruff mypy pytest

USER appuser
CMD ["/bin/bash", "-i"]
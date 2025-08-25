FROM mcr.microsoft.com/devcontainers/base:noble

RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && \
    apt-get install --no-install-recommends -y \
        curl \
        docker.io \
        file \
        gawk \
        gh \
        git \
        shellcheck \
        tk-dev \
        tmux \
        vim \
        xz-utils \
        zlib1g-dev \
        zstd \
        && \
    apt-get clean

USER vscode

ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# Install pulumi
ARG PULUMI_VERSION=v3.191.0
RUN curl --fail -L -o /tmp/pulumi.tar.gz https://get.pulumi.com/releases/sdk/pulumi-${PULUMI_VERSION}-linux-x64.tar.gz&& \
    sudo tar -xzf /tmp/pulumi.tar.gz -C /usr/local/bin --strip-components=1 pulumi && \
    rm -rf /tmp/pulumi.tar.gz && \
    pulumi gen-completion zsh | sudo tee /usr/local/share/zsh/site-functions/_pulumi > /dev/null

# Install uv
ARG UV_VERSION=0.8.13
RUN curl --fail -L -o /tmp/uv.tar.gz https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-x86_64-unknown-linux-gnu.tar.gz && \
    sudo tar -xzf /tmp/uv.tar.gz -C /usr/local/bin --strip-components=1 uv-x86_64-unknown-linux-gnu && \
    rm -rf /tmp/uv.tar.gz && \
    uv generate-shell-completion zsh | sudo tee /usr/local/share/zsh/site-functions/_uv > /dev/null

# Install python
ARG PYTHON_VERISON=3.13
RUN uv python install 3.13 --default

# Install pre-commit
ARG PRE_COMMIT_VERSION=v4.3.0
RUN uv tool install pre-commit@${PRE_COMMIT_VERSION} --with pre-commit-uv

# Install ruff
ARG RUFF_VERSION=0.12.10
RUN uv tool install ruff@${RUFF_VERSION} && \
    uv tool run ruff generate-shell-completion zsh | sudo tee /usr/local/share/zsh/site-functions/_ruff > /dev/null

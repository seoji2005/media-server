FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm
USER root
# apt and its watchdog have the same UID. A non-root postCreate process must
# never pretend it can kill root-owned sudo/apt descendants.
COPY scripts/setup_codespaces.py /tmp/media-codespaces-setup.py
RUN python3 /tmp/media-codespaces-setup.py --system-tools
USER vscode

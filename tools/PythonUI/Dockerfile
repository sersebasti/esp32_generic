# Dockerfile for Python Tkinter GUI app
FROM python:3.11-slim

# Install Tkinter and requests
RUN apt-get update && \
    apt-get install -y python3-tk && \
    pip install --no-cache-dir requests && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app


# Copy app files
COPY . /app

# Install Python requirements
RUN pip install --no-cache-dir -r requirements.txt


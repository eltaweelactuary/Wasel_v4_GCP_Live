# Use official lightweight Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy dependencies
COPY requirements.txt .

# Install dependencies securely
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Security best practice: avoid running as root
RUN useradd -m gcpuser
USER gcpuser

# Expose generic port (GCP Cloud Run defaults to 8080)
EXPOSE 8080
ENV PORT=8080

# Production-grade WSGI server
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app

# Use official lightweight Python slim image
FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered output for live logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set standard working directory
WORKDIR /app

# Create a non-root system user and group named 'appuser'
RUN groupadd -r appuser && useradd -r -g appuser -d /home/appuser -m appuser

# Install Python dependencies first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY health_check.py database.py ./

# Ensure appuser owns the application files
RUN chown -R appuser:appuser /app

# Switch to the non-root user for security
USER appuser

# Start the health check collector
CMD ["python", "health_check.py"]

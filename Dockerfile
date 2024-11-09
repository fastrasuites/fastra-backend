# Use the official Python image
FROM python:3.11-slim

# Set environment variables to prevent Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install necessary system dependencies, including netcat
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    build-essential \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy requirements.txt and install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project into the container
COPY . /app/

# Expose port 8000 to communicate with Gunicorn
EXPOSE 8000

CMD ["gunicorn", "--bind", "127.0.0.1:8000", "--workers", "3", "core.wsgi:application"]

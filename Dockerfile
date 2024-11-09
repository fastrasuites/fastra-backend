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

HEALTHCHECK CMD curl --fail http://localhost:8000 || exit 1

# CMD to wait for the database and then start the app using Gunicorn
CMD ["sh", "-c", "nc -z -v -w30 db 5432 && gunicorn --bind 0.0.0.0:8000 --workers 3 core.wsgi:application"]

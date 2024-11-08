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

# Run collectstatic
RUN python manage.py collectstatic --noinput


# Create the directory for the Gunicorn socket
RUN mkdir -p /gunicorn

# Expose the port (though it's not needed since we're using a Unix socket)
EXPOSE 8000

# Start Gunicorn, binding to a Unix socket instead of a TCP port
CMD ["gunicorn", "core.wsgi:application", "--bind", "unix:/gunicorn.sock"]

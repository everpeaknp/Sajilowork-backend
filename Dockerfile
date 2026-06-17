# Dockerfile
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements/ /app/requirements/
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements/prod.txt

# Copy project
COPY . /app/

# Expose port
EXPOSE 8000

# Start the application via entrypoint script
CMD ["/app/scripts/entrypoint.sh"]

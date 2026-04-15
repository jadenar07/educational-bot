FROM python:3.10.13-slim

WORKDIR /app

# Install system dependencies for some packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ src/

# Create entrypoint script to run migrations and start app
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
if [ "$RUN_MIGRATIONS" = "true" ]; then\n\
  echo "Running database migrations..."\n\
  PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f src/docker/init-db.sql\n\
  echo "Migrations completed successfully"\n\
fi\n\
\n\
echo "Starting application..."\n\
python src/main.py' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# Expose port for FastAPI
EXPOSE 8000

# Run the application with migrations
CMD ["/app/entrypoint.sh"]

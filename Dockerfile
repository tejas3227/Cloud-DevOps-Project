FROM python:3.12-slim

#to fix the vulnerability found in image scanning using trivy
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*                

# Set the working directory
WORKDIR /app

# Prevent Python from writing pyc files to disc  (pyc files are compiled Python files)
ENV PYTHONDONTWRITEBYTECODE=1

# Ensure logs are sent directly to the terminal (stdout/stderr)
ENV PYTHONUNBUFFERED=1

# Install dependencies
COPY requirements.txt .

RUN pip install --no-cache-dir --default-timeout=300 --retries=10 -r requirements.txt 

# Copy the application code to the container
COPY app.py .
COPY templates/ ./templates/
COPY static/ ./static/

# RUN as non-root user
RUN useradd --create-home appuser && chown -R appuser:appuser /app

USER appuser

# Expose the port the app runs on
EXPOSE 8000

# Start Flask through Gunicorn with 2 worker processes, binding to all interfaces on port 8000, and logging to stdout/stderr
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:8000", "--access-logfile", "-", "--error-logfile", "-", "--capture-output", "app:app"]
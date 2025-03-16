# Use official Python image as a base
FROM python:3.9-slim

RUN apt update && apt install -y curl && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app/haper-server

# Install Python dependencies
COPY . .
RUN pip install -r requirements.txt

# Expose the Flask app's port
EXPOSE 8888

# Default to run flask app
CMD ["gunicorn", "--bind", "0.0.0.0:8888", "-w", "${NUM_WORKER:-1}", "--threads", "${NUM_THREAD:-1}", "app:api_server:app"]

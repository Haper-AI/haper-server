# Use official Python image as a base
FROM python:3.9-slim

# Set work directory
WORKDIR /app/haper-server

# Install Python dependencies
COPY . .
RUN pip install -r requirements.txt

# Expose the Flask app's port
EXPOSE 8888

# Command to start the app (update if your app entry point is not `app.py` or if you use Flask run)
CMD ["gunicorn", "--bind", "0.0.0.0:8888", "app:app"]

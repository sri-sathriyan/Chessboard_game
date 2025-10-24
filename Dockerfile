# Use an official Python slim image
FROM python:3.11-slim

# Set working dir
WORKDIR /app

# Copy only what we need first for better caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt || true

# Copy app
COPY . .

# Expose port (Flask default)
EXPOSE 5000

# Use a simple entrypoint to run the app; production deployments should use a WSGI server (gunicorn)
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
CMD ["sh", "-c", "python app.py"]

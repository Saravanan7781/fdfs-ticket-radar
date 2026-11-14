# Base Python Image
FROM python:3.12-slim

# Set environment
ENV PYTHONUNBUFFERED=1
ENV PORT=5055
ENV TZ=Asia/Kolkata

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Expose port
EXPOSE 5055

# Run 24/7 cloud runner
CMD ["python", "cloud_app.py"]

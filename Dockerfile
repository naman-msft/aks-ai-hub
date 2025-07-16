# Build React frontend
FROM node:18 AS build
WORKDIR /app
COPY frontend/package*.json frontend/
RUN npm ci --prefix frontend
COPY frontend/ frontend/
RUN npm run build --prefix frontend
# Python backend
FROM python:3.11
RUN apt-get update && apt-get install -y \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy ALL necessary files
COPY *.py ./
COPY *.json ./
COPY *.txt ./
COPY .env ./
COPY evaluations/ ./evaluations/

# Copy React build
COPY --from=build /app/frontend/build/ ./frontend/build/

# Expose port
EXPOSE 8000

# Start with Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--timeout", "600", "app:app"]
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies for optional packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Optional: install audio/video packages if you want them in Docker
# Uncomment the lines below to enable real Whisper + OpenCV support:
# RUN pip install --no-cache-dir faster-whisper
# RUN pip install --no-cache-dir opencv-python-headless mediapipe

# Copy application source
COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

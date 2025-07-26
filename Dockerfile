# Use Python 3.10 slim image for smaller size
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copy requirements first to leverage Docker layer caching
COPY requirements.txt .

# Install system dependencies and Python packages (CPU-only PyTorch)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && pip install --no-cache-dir --upgrade pip \
    && sed -i 's/torch==.*+cpu/torch/g' requirements.txt \
    && sed -i 's/torchvision==.*+cpu/torchvision/g' requirements.txt \
    && sed -i 's/torchaudio==.*+cpu/torchaudio/g' requirements.txt \
    && pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y gcc g++ \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Ensure CPU-only execution
ENV CUDA_VISIBLE_DEVICES=""
ENV TORCH_USE_CUDA_DSA=0

# Copy the main application file
COPY persona.py .

# Copy the sentence transformer model
COPY model/ ./model/

# Create necessary directories
RUN mkdir -p input/PDF output

# Create a non-root user for security
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Set default command
CMD ["python", "persona.py"]

# Add labels for better image management
LABEL maintainer="Document Processing Team"
LABEL description="Document processing and analysis with persona-based ranking - offline capable"
LABEL version="1.0"
# Use a lightweight Python base image
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Copy your project files
COPY . /app

# Install system dependencies (optional: for PDFs, graphviz, etc.)
RUN apt-get update && apt-get install -y git libmagic1 && rm -rf /var/lib/apt/lists/*

# Clone and install LightRAG
RUN git clone https://github.com/HKUDS/LightRAG.git && \
    pip install -e ./LightRAG

# Install additional dependencies (Ollama client + Chroma)
RUN pip install chromadb requests flask gradio

# Expose ports if you plan to use API/UI versions
EXPOSE 8000 7860

# Ensure latest LightRAG with Ollama module structure
RUN pip install --upgrade --force-reinstall "git+https://github.com/HKUDS/LightRAG.git"

# Run your script
CMD ["python", "lightrag_init.py"]


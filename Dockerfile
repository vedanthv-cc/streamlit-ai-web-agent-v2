# Use a lightweight Python base image
FROM python:3.11-slim

# Install system dependencies for Playwright & Tesseract
RUN apt-get update && apt-get install -y \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# First, copy only requirements to leverage Docker caching
COPY requirements.txt .

# Install Python dependencies (this layer is cached unless requirements.txt changes)
RUN pip install --no-cache-dir -r requirements.txt

# (Optional) Install additional dependencies not in requirements.txt
RUN pip install browser-use

# Install Playwright and its browsers
RUN pip install playwright && playwright install --with-deps

# Now copy the rest of your application code
COPY . .

# Expose the port for Streamlit
EXPOSE 8501

# Command to run the Streamlit app
CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]

# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install system dependencies if any are needed in the future
# RUN apt-get update && apt-get install -y ...

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# --- NEW: Download the spaCy language model ---
RUN python -m spacy download en_core_web_sm

# Copy the application code into the container
COPY . .

# Expose the port the app runs on
EXPOSE 8000

# Run the command to start the Uvicorn server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
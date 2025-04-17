# Use a lightweight official Python base image
FROM python:3.11-slim

# (Optional) Install system libraries if your code needs them
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy the entire repo into the container
COPY . /app

# Install uv (like your Makefile does) and then sync
# We replicate what "make install" typically does
# with extras like streamlit and jupyter.
RUN pip install --no-cache-dir uv && \
    uv sync --dev --extra streamlit --extra jupyter --frozen && \
    pip install --no-cache-dir streamlit

# Streamlit typically defaults to port 8501, 
# but Cloud Run (or other hosts) usually expect port 8080.
# We'll EXPOSE 8080 for local clarity.
EXPOSE 8080

# Set the command to run your Streamlit app
# Notice we point to the same script you run locally.
# Adjust paths if your main code is in a different folder.
CMD ["streamlit", "run", "frontend/streamlit_app.py", \
     "--server.port=8080", \
     "--server.address=0.0.0.0"]

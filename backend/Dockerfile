# Matches the version requirements.txt is pinned against — numpy==2.5.2
# requires Python >=3.12, so python:3.11-slim can't install it at all.
FROM python:3.14-slim

WORKDIR /app

# libgomp1 is LightGBM's OpenMP runtime dependency. It isn't in the slim
# base image, and without it, unpickling a LightGBM model fails with
# "libgomp.so.1: cannot open shared object file". The agents'
# _load_model() catches that (Exception, from inside joblib.load) and
# logs a warning rather than crashing — so this would degrade silently
# to "model unavailable" instead of failing loudly. Install it up front.
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Start server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

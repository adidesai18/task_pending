# Use an official Python runtime as the base image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the code into the container
COPY . .

# Expose port 8080
EXPOSE 8080

# Switch to a non-root user
USER 1000

# Run the script
CMD [ "python3", "main.py" ]

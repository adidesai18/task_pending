# Use an official Python runtime as a parent image
FROM python:3.9-slim-buster

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variables (if needed)
# You can also set these when running the docker container
# ENV TELEGRAM_BOT_TOKEN your_token_here
# ENV FIREBASE_PROJECT_ID your_project_id_here
# ...

# Run your script when the container launches
CMD ["python", "main.py"]

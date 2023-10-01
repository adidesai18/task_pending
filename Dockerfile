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

ENV TELEGRAM_TOKEN='6100278037:AAEg4Yh53YNuFhuSWSVnH5Ep56ofX4tS8yE'
ENV FIREBASE_PROJECT_ID='reminder-437c6'
ENV FIREBASE_PRIVATE_KEY_ID='71feabc4525158fcb35e466c687b5c4c56e52dbf'
ENV FIREBASE_PRIVATE_KEY='-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDiMo2bfEW1XXLr\nxZNCqjGJoaRAK2yIshOhyXb9AQE4MPzX5YoMTqTA4WUpAOsSUN6gTJQyBZjr+muz\n/d6bCsrZhRgszbqheJIg5WvsaEr5j52b6RqGwyHvkJ4gnQAxAh03YaS55ZifNueg\nqpuocPckoV/l00vpsb8kqlQXI3tsA2XBBXBANAHgo5zUREOS7il1BBFRpqU1gjvY\nC5eVUnX5GpXR0FJicvRbHxzDbg332NuYAIkAdBRcv72ukE7u46/hZmzKBz/qjZ1u\nKYGjJHLFDkm38vM3vX6SgMwYYPLENMr8BjSIHWFohiV9kj3acHXQMMeeysnU51jz\nqtylAOKlAgMBAAECggEAAWpDjId4gCv3fhYcV7xs1umV93jOEwTaLpbuEaMh+NIF\nouwisvUC/tnqIhmJXvH2kpYoDzANxtwoNFYQQHQO1NGKVy1qT3xLnb0RscbtQSZu\n2/zXV6R839zNwHJ6/9N9j00jFK6lB8n2JQEsPB+IzEfeK7for6uXAIm4QPTN3t0b\nj+yNz8Kmzf4NKBJhRK/vno2MyBIrgav9GtWB9puvotwK388NdGyBzws7MG6l8XS9\nbeVsVoDJ+UquD4S8Bb3JVd6ceIPDleTtFR876NSKtxbuLNRQKr4lMaxSclIX9NBE\n3wLbaN5xwQVNKVOoXsXOQzfRX0usiJYKr5LUGe7oeQKBgQD+FyiXGit/ZlhN7goO\nmtor1T7lXFbUZEIyHoS606npu3pTRYhcwWhi+oYbR67SKEQHXC7CfxAQEeXGIdsu\nPcJ99eYDQ/5pd/+N6R58vM1pJWckIuX3YMDkdZSaCa57n/erp4/RkrqCdcPuOHZj\nEnmRsXQLZTt0CjBW4VbymtxFEwKBgQDj5btL1xIlqnZMUyki0dzaWltw4Ly5MHj/\nOIUdnulU9CYLscpK34EOiSh4U+M2wCtg8tuelypGbWi7e/oY5vJRWq0n4kw1kXR5\notDuYa/8HgBE86c134iBQDDNwO97kf2hpw0563y00uFSWdOdUngeLGxx2f/VAU1Q\n/CcpQHWIZwKBgGYITK9oveDZ60nX9cfpnQSPDEO0MdX2MLLJmIkhaBDIzRVVTa3Z\nqJ5eda3MukIAE1lVRh2qQnwBg+BtRgOqn0hPjz7udeJKYp/M5gY3FtFLSMC1Ft2g\nx7S2FqdIjf1svlr63YDNyAGNYtFtcPTVvWWo+a19yEMPuFua/3xKfXtrAoGAL7TM\nk2CvPNFFOE8EQnS6Db9yetugxgd+nLahLwUwBQei2znZhfjplDhkD2RIIRLzQbU1\nAirUv69xiCW4wfO+cAdSThISL/iF8FyD7hLm+xjwp35111I2yg+856VmvHBgLrHA\nlApWraejYVDKeplj6bUU8nRXGKjQHY7bR8hlkisCgYEAqc8qHG10u2LrujPYfe57\nFPjCgTG3rD2rBsTHydvOpK8Bxh+jOH24e922m37ONInoYu9QTLseltAooRCE8lJL\nzb4DZt2YkWVTAbIlV+XrT6gGwgxVXdK0K+7UcUav5abZLQzNjOpzpn/feEILkF6y\nHSEToI5YRBt0qWvQ4fPKkrw=\n-----END PRIVATE KEY-----\n'
ENV FIREBASE_CLIENT_EMAIL='firebase-adminsdk-1bznx@reminder-437c6.iam.gserviceaccount.com'
ENV FIREBASE_CLIENT_ID='102298740257645228543'
ENV FIREBASE_CLIENT_CERT_URL='https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-1bznx%40reminder-437c6.iam.gserviceaccount.com'

# Expose port 8080
EXPOSE 8080

# Switch to a non-root user
USER 1000

# Run the script
CMD [ "python3", "main.py" ]

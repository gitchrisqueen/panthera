# Use an official Python runtime as a parent image
FROM python:3.12

# Set the working directory in the container
WORKDIR /app

# Copy the equirements.txt file into the container
COPY requirements.txt requirements.txt

# Install any needed packages specified in requirements.txt
RUN apt-get -qq update
RUN pip3 --quiet install --no-cache-dir -r requirements.txt \
         --force-reinstall --upgrade

# Copy the current directory contents into the container at /app
COPY . /app

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Define environment variable
ENV FLASK_APP=app.py

# Run the application
CMD ["flask", "run", "--host=0.0.0.0", "--port=4000"]
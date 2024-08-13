# Dockerfile
FROM mysql:8.0

# Set environment variables
ENV MYSQL_ROOT_PASSWORD=rootpassword
ENV MYSQL_DATABASE=mydatabase

# Copy the initialization script
COPY *_db.sh /docker-entrypoint-initdb.d/

# Expose the MySQL port
EXPOSE 3306
# Use a slim Python image
FROM python:3.11-slim

# System dependencies for pyodbc and MS ODBC SQL Server driver
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gnupg apt-transport-https ca-certificates \
    unixodbc unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Microsoft ODBC Driver 18 for SQL Server
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - && \
    curl https://packages.microsoft.com/config/debian/12/prod.list > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql18 && \
    rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app

# Copy project files
COPY . /app

# Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Streamlit must bind to 0.0.0.0 and use Render's provided PORT
ENV PYTHONUNBUFFERED=1
CMD streamlit run app.py --server.port $PORT --server.address 0.0.0.0 
# TODO: Make python version an arg
FROM docker.io/python:3.12-slim

# Env variable for the build
# TODO: Review that part (e.g. poetry version ...)
ENV POETRY_NO_INTERACTION=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_HOME='/usr/local' \
    POETRY_VERSION=1.8.3

# Install libraries and packages
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install --no-install-recommends -y curl git pkg-config build-essential ca-certificates && \
    curl -sSL https://install.python-poetry.org | python3 - &&\
    apt-get autoremove -y && \
    apt-get clean all && \
    rm -rf /var/lib/apt/lists/* && \
    pip --no-cache-dir install --no-compile --upgrade pip wheel

# Copy lock and install all dependancies
WORKDIR /source
COPY poetry.lock pyproject.toml /source/
RUN poetry install --no-ansi --no-root --no-directory --without dev  && \
    rm -rf $POETRY_CACHE_DIR

# Copy application and install it
COPY . ./
RUN poetry install --no-ansi --no-directory --without dev

# Run streamlite app
EXPOSE 8501
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health
ENTRYPOINT ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]

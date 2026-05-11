FROM python:3.12-slim

WORKDIR /app

# Layer 1: dependency install (cached unless requirements.txt changes).
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Layer 2: source. Excludes tests/, shared-data/, scripts/ via .dockerignore.
COPY . /app

# Safe default: print usage. Each service in docker-stack.yml / compose.dev.yml
# overrides this with `python -m agents.runner --agent <name> --job <id>`.
CMD ["python", "-m", "agents.runner", "--help"]

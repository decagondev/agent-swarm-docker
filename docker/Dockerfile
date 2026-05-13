FROM python:3.12-slim

WORKDIR /app

# Layer 1: dependency install (cached unless requirements.txt changes).
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Layer 1b: system tools for opt-in pentest agents (feature/pentest only).
# Placed AFTER pip install so the slow pip layer stays cached when this
# changes. Adds ~25 MB. The nmap binary is only invoked when the supervisor
# is run with --pentest; the agents are otherwise invisible.
RUN apt-get update \
 && apt-get install -y --no-install-recommends nmap \
 && rm -rf /var/lib/apt/lists/*

# Layer 2: source. Excludes tests/, shared-data/, scripts/ via .dockerignore.
COPY . /app

# Safe default: print usage. Each service in docker-stack.yml / compose.dev.yml
# overrides this with `python -m agents.runner --agent <name> --job <id>`.
CMD ["python", "-m", "agents.runner", "--help"]

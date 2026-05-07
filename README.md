# agent-swarm-docker

```bash
# 1. Build everything
docker compose up --build -d

# 2. Run the supervisor with your text (one paragraph)
docker compose run --rm orchestrator python orchestrator.py "Your custom paragraph here. It can be as long as you want."

# OR for the exact example you gave:
docker compose run --rm orchestrator python orchestrator.py "The quick brown fox jumps over the lazy dog."

# 3. For the 20-file batch test (just edit orchestrator.py temporarily or run this):
# (uncomment the batch loop in orchestrator.py first, then:)
docker compose run --rm orchestrator python orchestrator.py "Batch test paragraph."

# Scale workers if you want more parallelism on 20+ files:
docker compose up -d --scale capitalize-worker=5 --scale reverse-worker=5
```

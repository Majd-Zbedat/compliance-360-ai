# EC2 deployment — Layer 3 microservices

Deploy the four Compliance 360 microservices (RAG, doc-analyzer, guardrails,
LangGraph) on a single Ubuntu EC2 instance. Keep the dashboard, orchestrator,
and n8n on your laptop unless you choose to host them elsewhere.

## Architecture

| Layer | Where | Ports |
|-------|--------|-------|
| Dashboard (Next.js) | Laptop | 3000 |
| Orchestrator + n8n | Laptop | 8000, 9090 |
| Layer 3 (Docker Compose) | EC2 | 8001–8004 |

Laptop `.env` (orchestrator) points at the EC2 public IP:

```env
RAG_SERVICE_URL=http://<EC2_PUBLIC_IP>:8001
DOC_ANALYZER_SERVICE_URL=http://<EC2_PUBLIC_IP>:8002
GUARDRAILS_SERVICE_URL=http://<EC2_PUBLIC_IP>:8003
LANGGRAPH_AGENT_SERVICE_URL=http://<EC2_PUBLIC_IP>:8004
N8N_WEBHOOK_URL=http://localhost:9090/webhook/compliance-audit
```

Import `n8n/compliance_audit.json` in n8n with the same host (`<EC2_PUBLIC_IP>`)
instead of `host.docker.internal`.

## 1. Launch EC2

- **AMI:** Ubuntu 24.04 LTS (plain Ubuntu, not SQL Server AMIs)
- **Type:** `t3.medium` or larger (RAG + sentence-transformers need ~4 GB RAM)
- **Disk:** 30 GiB gp3+
- **Key pair:** save `.pem` locally (e.g. `~/Downloads/compliance-key.pem`)

### Security group (minimum)

| Port | Source | Purpose |
|------|--------|---------|
| 22 | Your IP only | SSH |
| 8001–8004 | Your IP only (recommended) or `0.0.0.0/0` (demo only) | Layer 3 APIs |

Remove unused rules (e.g. MSSQL 1433) from test AMIs.

### Elastic IP (recommended)

1. EC2 → **Elastic IPs** → Allocate
2. Associate with your instance
3. Update laptop `.env`, `n8n/compliance_audit.json`, and this doc if the IP changes

Without an Elastic IP, the public IP changes on **Stop/Start** (not Reboot).

## 2. Install Docker on the instance

```bash
ssh -i ~/Downloads/compliance-key.pem ubuntu@<EC2_PUBLIC_IP>

sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker ubuntu
# log out and back in, or: newgrp docker
```

Optional swap on `t3.medium` if RAG OOMs during first start:

```bash
sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
```

## 3. Deploy the stack

```bash
cd ~
git clone https://github.com/Majd-Zbedat/compliance-360-ai.git FinalProject
cd FinalProject
git pull   # after you push Layer 3 fixes

docker compose -f infra/docker-compose.yml up -d --build
docker compose -f infra/docker-compose.yml ps
```

Wait until `compliance-rag` is **healthy** (first start can take several minutes).

On the instance:

```bash
curl -s http://127.0.0.1:8001/healthz
curl -s http://127.0.0.1:8004/healthz
```

Expect `"embedding_backend":"sentence-transformers"` after the pinned RAG image rebuild.

If langgraph stayed `Created` because RAG was slow:

```bash
docker compose -f infra/docker-compose.yml up -d langgraph-agent-service
```

## 4. Seed regulations (from laptop)

```powershell
cd C:\Users\ASUS\Desktop\FinalProject
.\venv\Scripts\python.exe scripts\seed_regulatory_corpus.py --remote http://<EC2_PUBLIC_IP>:8001 --reset
```

Must print `remote upsert ok: upserted=101 total=101`.

Re-seed after changing the embedding backend (hashing → sentence-transformers).

## 5. Laptop dev checklist

```powershell
# Terminal 1 — orchestrator (loads .env with EC2 URLs)
.\venv\Scripts\python.exe -m uvicorn services.orchestrator.app.main:app --host 0.0.0.0 --port 8000

# Terminal 2 — dashboard
cd webui; npm run dev
```

- `webui/.env.local`: `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`
- n8n: import `n8n/compliance_audit.json`, activate workflow, map Gemini credentials
- Stop local Layer 3 Docker if ports conflict: `.\scripts\docker_layer3.ps1 -Down`

## 6. Rebuild RAG only (embedding fix)

After pulling Dockerfile/requirements changes:

```bash
cd ~/FinalProject
docker compose -f infra/docker-compose.yml build --no-cache rag-service
docker compose -f infra/docker-compose.yml up -d rag-service langgraph-agent-service
```

Then re-seed from the laptop (section 4).

## 7. Troubleshooting

| Symptom | Fix |
|---------|-----|
| `curl` to public IP fails | Open SG 8001–8004; check instance public IP / Elastic IP |
| `dependency failed: rag unhealthy` | Wait longer; check `docker logs compliance-rag`; add swap |
| `embedding_backend: hashing-fallback` | Rebuild RAG image (section 6); verify build log shows `embedding model ok` |
| Seed `falling back to local` | EC2 RAG not reachable; fix SG / IP |
| LangGraph `Created` | `docker compose up -d langgraph-agent-service` after RAG healthy |
| Dashboard `Failed to fetch` | Start orchestrator on `:8000` |

## 8. Current demo instance (update when IP changes)

| Item | Value |
|------|--------|
| Public IP | `44.223.109.220` |
| SSH user | `ubuntu` |
| Repo path on instance | `~/FinalProject` |

Replace placeholders in commands when you attach an Elastic IP.

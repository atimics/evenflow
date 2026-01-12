# MCP Host for Evenflow MUD Server - AWS Deployment Plan

## Overview

This plan outlines how to create a **Model Context Protocol (MCP) host** for the Evenflow MUD server and deploy it cost-effectively on AWS. The MCP host will expose the MUD's state, mechanics, and world data to LLM clients (like Claude), enabling external tools and agents to:
- Query world state and affinity memories
- Analyze game mechanics and consequences
- Generate folklore and summaries of world history
- Support admin tracing and tuning

---

## Part 1: Understanding the Architecture

### Current State
- **Evenflow**: Python-based Evennia world with persistent affinity memory system
- **Core Components**:
  - `world/affinity/`: Affinity computation, affordances, validation
  - `world/locations/`: World locations (YAML-based)
  - `commands/`: MUD commands
  - `tests/`: Validation and smoke tests

### MCP Host Role
- Wraps the Evenflow game state into MCP-compliant tools and resources
- Provides read-only and read-write access to world data (affinity, locations, artifacts, traces)
- Runs as a standalone Python service communicating with Claude/other LLM clients

---

## Part 2: Design - Local MCP Implementation

### 2.1 MCP Server Structure (Python)

Create `mcp/` directory:
```
mcp/
├── __init__.py
├── server.py              # Main MCP server
├── tools.py               # MCP tool definitions
├── resources.py           # MCP resource definitions
├── world_adapter.py       # Bridges MCP ↔ Evenflow world state
└── schemas.py             # JSON schemas for tools/resources
```

### 2.2 MCP Tools to Implement

**Query Tools:**
1. `get_location_state` - Retrieve location affinity, affordances, artifacts
2. `get_artifact_state` - Artifact affinity, current location, effects
3. `get_player_traces` - Recent actions, affinity contributions
4. `query_affinity_by_type` - Filter traces by decay type (personal/group/behavior)
5. `get_world_history_summary` - LLM-generated folklore from recent traces
6. `validate_affordance_impact` - Predict consequence of player action

**Admin/Tuning Tools:**
1. `trace_action_consequence` - Show full propagation of action effects
2. `export_world_state` - Dump JSON snapshot for analysis
3. `list_affordances` - Show all affordances and their triggers

### 2.3 MCP Resources

**Read-only Resources:**
- `location://` - Location state snapshots
- `artifact://` - Artifact state snapshots  
- `trace://` - Historical traces (filterable by date, type, actor)
- `affordance://` - Current affordance rules

---

## Part 3: AWS Deployment Architecture (Low Cost)

### 3.1 Recommended Setup

**Option A: Lambda + RDS (Recommended for cost)**
```
┌─────────────────────────────────────────┐
│  Claude/LLM Client                      │
│  (runs MCP client code locally)         │
└──────────────┬──────────────────────────┘
               │ (HTTP or stdio)
┌──────────────▼──────────────────────────┐
│  AWS Lambda: MCP Server                 │
│  - Cold start OK for async workloads    │
│  - ~1-5 min max latency acceptable      │
│  - Free tier: 1M invocations/month      │
└──────────────┬──────────────────────────┘
               │ (psycopg2/SQLAlchemy)
┌──────────────▼──────────────────────────┐
│  AWS RDS (PostgreSQL)                   │
│  - Free tier: db.t2.micro + 20GB        │
│  - Or: use Lightsail DB ($5-15/mo)      │
│  Stores: locations, artifacts, traces   │
└─────────────────────────────────────────┘
```

**Option B: EC2 t2.micro + self-hosted (Cheaper if always-on)**
- Single t2.micro instance (eligible free tier or ~$8/mo)
- Runs Evennia + MCP server + SQLite/PostgreSQL
- Simple, but requires more management

### 3.2 Cost Breakdown (Option A - Lambda)

| Component | Cost | Notes |
|-----------|------|-------|
| Lambda | Free | 1M invocations/month free tier |
| RDS PostgreSQL | Free-$15/mo | Free tier or Lightsail |
| S3 (backups) | <$1/mo | Minimal storage |
| NAT Gateway | $0.045/hour | Only if needed (likely not) |
| **Total** | **$0-15/mo** | Within free tier if eligible |

### 3.3 Cost Breakdown (Option B - EC2)

| Component | Cost | Notes |
|-----------|------|-------|
| EC2 t2.micro | $0-11/mo | Free tier 12mo, then ~$11 |
| EBS storage | $0-1/mo | 8GB minimal |
| **Total** | **$0-12/mo** | Simpler, always-on |

---

## Part 4: Implementation Roadmap

### Phase 1: Local MCP Development (Weeks 1-2)

**1.1 Create MCP Server Structure**
- [ ] Create `mcp/` directory structure
- [ ] Install `mcp` Python package: `pip install mcp`
- [ ] Scaffold `server.py` with basic MCP server
- [ ] Create `world_adapter.py` to load Evenflow world state

**1.2 Implement Core Tools**
- [ ] `get_location_state` tool
- [ ] `get_artifact_state` tool
- [ ] `query_affinity_by_type` tool
- [ ] Add tool schemas and validation

**1.3 Local Testing**
- [ ] Test MCP server with Claude via `cline` or direct integration
- [ ] Validate tool outputs match expected schemas
- [ ] Update `requirements.txt` with MCP dependencies

### Phase 2: AWS Preparation (Week 2-3)

**2.1 Database Migration**
- [ ] Create RDS PostgreSQL instance (or Lightsail DB)
- [ ] Migrate Evenflow data model to PostgreSQL (from in-memory)
- [ ] Create migration scripts

**2.2 Lambda Containerization**
- [ ] Create `Dockerfile` for MCP server
- [ ] Build ECR image
- [ ] Test Lambda invoke locally with `sam` or `serverless`

**2.3 GitHub Actions Setup**
- [ ] Create `.github/workflows/deploy-lambda.yml`
- [ ] Configure AWS credentials via GitHub Secrets
- [ ] Auto-deploy on push to `main`

### Phase 3: AWS Deployment (Week 3-4)

**3.1 Infrastructure as Code**
- [ ] Write CloudFormation or Terraform for Lambda, RDS, IAM roles
- [ ] Or use AWS SAM (Serverless Application Model) - simpler
- [ ] Deploy via GitHub Actions

**3.2 Monitoring & Logging**
- [ ] CloudWatch Logs for Lambda execution
- [ ] Simple alarms for errors
- [ ] Cost monitoring dashboard

**3.3 Validation**
- [ ] Test MCP client → Lambda → RDS flow
- [ ] Run smoke tests (`tests/smoke_validate.py`)
- [ ] Load testing if needed

---

## Part 5: Technical Details

### 5.1 Evenflow → MCP Adapter

```python
# world_adapter.py pseudocode
class EvenflowMCPAdapter:
    def __init__(self, db_connection):
        self.db = db_connection
    
    def get_location_state(self, location_id):
        # Load from RDS, apply affinity decay
        # Return as structured dict
        
    def query_affinity_traces(self, filters):
        # Query by type, date, actor, location
        # Return paginated results
```

### 5.2 Lambda Handler

```python
# lambda_handler.py
def lambda_handler(event, context):
    # Parse MCP request from event
    # Route to MCP server
    # Return response
    
    # Cold start optimization:
    # - Load Evenflow config once at module level
    # - Reuse DB connection across invocations (connection pooling)
```

### 5.3 RDS Schema

Minimum tables needed:
- `locations` (id, name, description, affinity_json)
- `artifacts` (id, name, location_id, affinity_json)
- `traces` (id, actor, action, target, timestamp, affinity_delta, decay_type)
- `affordances` (id, trigger_condition, effect_json, location_id)

### 5.4 GitHub Workflow

```yaml
# .github/workflows/deploy-lambda.yml
on: [push]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to Lambda
        run: |
          aws lambda update-function-code \
            --function-name evenflow-mcp-server \
            --zip-file fileb://package.zip
```

---

## Part 6: Cost Optimization Tips

1. **Use AWS Free Tier**: EC2 t2.micro (12 months) or RDS free tier
2. **RDS Lightsail Alternative**: ~$5/mo vs RDS Standard ~$15/mo
3. **Lambda Auto-scaling**: Cold starts OK; scale to zero when idle
4. **Backup Strategy**: 
   - Use RDS automated backups (included)
   - S3 exports weekly (~$0.50/mo)
5. **Data Retention**: Archive old traces to S3 Glacier for compliance
6. **Local Testing**: Keep iteration local; only deploy validated builds

---

## Part 7: Deployment Checklist

**Pre-Deployment:**
- [ ] All tests passing (`pytest tests/`)
- [ ] MCP server tested locally with Claude
- [ ] Database schema validated
- [ ] Environment variables documented (.env.example)
- [ ] Security: RDS in private subnet, Lambda IAM minimal

**Deployment:**
- [ ] AWS credentials configured (`aws configure` or GitHub Secrets)
- [ ] CloudFormation/SAM template deployed
- [ ] GitHub Actions workflow enabled
- [ ] Lambda cold start time <10s
- [ ] RDS connectivity verified

**Post-Deployment:**
- [ ] Smoke tests passing against live Lambda
- [ ] CloudWatch logs clean (no errors)
- [ ] Cost alert set up
- [ ] Documentation updated with Lambda URL

---

## Part 8: Next Steps (Not in MVP)

1. **Caching**: Add Redis/ElastiCache for frequently accessed state
2. **Async Traces**: Queue trace writes to SQS for better Lambda perf
3. **World Sync**: If Evennia runs locally, sync state to RDS periodically
4. **Multi-Region**: Replicate to eu-west-1 for lower latency
5. **Custom Domain**: Route53 + API Gateway for cleaner URLs

---

## Files to Create

```
├── mcp/
│   ├── __init__.py
│   ├── server.py
│   ├── tools.py
│   ├── resources.py
│   ├── world_adapter.py
│   └── schemas.py
├── aws/
│   ├── template.yaml          # CloudFormation/SAM
│   ├── lambda_handler.py       # Lambda entry point
│   └── requirements-lambda.txt # Lambda-specific deps
├── .github/workflows/
│   └── deploy-lambda.yml       # CI/CD
├── PLAN.MD                     # This file
└── ARCHITECTURE.MD             # Detailed technical specs
```

---

## References

- [MCP Documentation](https://modelcontextprotocol.io/)
- [AWS Lambda Python Guide](https://docs.aws.amazon.com/lambda/latest/dg/python-handler.html)
- [AWS SAM](https://aws.amazon.com/serverless/sam/)
- [Evennia Documentation](https://www.evennia.com/)
- [RDS Pricing](https://aws.amazon.com/rds/pricing/)
- [Lambda Pricing](https://aws.amazon.com/lambda/pricing/)

---

**Estimated Timeline**: 3-4 weeks for MVP  
**Estimated Cost**: $0-15/month  
**Complexity**: Medium (requires AWS + MCP knowledge)

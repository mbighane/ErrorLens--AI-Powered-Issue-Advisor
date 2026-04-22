"""
Quick Start Guide - ErrorLens
Multi-Agent Issue Solver
"""

# Quick Start Guide

## 🚀 Setup (5 minutes)

### 1. Install Dependencies

```bash
cd D:\Manisha\ErrorLens
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

Create/update `.env`:

```env
# Azure DevOps
AZURE_DEVOPS_ORG=mycompany
AZURE_DEVOPS_PROJECT=myproject
AZURE_DEVOPS_TOKEN=your_pat_token_here

# OpenAI
OPENAI_API_KEY=sk-...

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
```

### 3. Get Azure DevOps PAT Token

1. Go to: `https://dev.azure.com/[organization]/_usersSettings/tokens`
2. Click "New Token"
3. Name: `ErrorLens`
4. Scopes: `Work Items (Read)`, `Wiki (Read)`
5. Save the token to `.env`

## 🏃 Running the System

### Terminal 1: Start Backend

```bash
cd D:\Manisha\ErrorLens
.venv\Scripts\activate
uvicorn backend.app.main:app --reload --port 8000
```

Visit: http://localhost:8000/docs

### Terminal 2: Start Frontend

```bash
cd D:\Manisha\ErrorLens
.venv\Scripts\activate
streamlit run frontend/pages/streamlit_app.py
```

Visit: http://localhost:8501

## 🔍 Using the System

### Via Streamlit UI

1. Go to http://localhost:8501
2. Describe your issue: "My build is failing with NullReferenceException"
3. Click "Get Issue Advice"
4. Get comprehensive analysis!

### Via API (curl)

```bash
curl -X POST http://localhost:8000/api/issues/solve \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "dev1",
    "message": "Payment service returns 500 error when processing large transactions"
  }'
```

### Via Python

```python
import asyncio
import httpx

async def solve_issue():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/issues/solve",
            json={
                "user_id": "dev1",
                "message": "Authentication module not working"
            }
        )
        print(response.json())

asyncio.run(solve_issue())
```

## 🧠 What Happens Behind the Scenes

When you submit an issue:

1. **🧠 Orchestrator** receives your query
2. **🔍 Bug Analysis Agent** searches Azure DevOps for similar bugs
3. **📘 Wiki Knowledge Agent** finds relevant documentation
4. **🔗 Integration Context Agent** analyzes module dependencies
5. **🧪 Recommendation Agent** synthesizes everything
6. **Final Response** includes:
   - 📊 Root cause analysis
   - 🔧 Suggested fixes with steps
   - ✅ Troubleshooting checklist
   - 📈 Confidence level

## 📊 Example Response

```
ANALYSIS:
- Found 5 similar bugs in Azure DevOps
- Common root cause: Null reference exception
- Best practice: Add input validation

SIMILAR BUGS:
- Bug #123: NullRef in payment module (confidence: 0.85)
- Bug #456: NullRef in auth module (confidence: 0.78)

ROOT CAUSES:
- Null/Undefined reference (confidence: 0.8)
- Missing input validation (confidence: 0.7)

SUGGESTED FIXES:
1. Add null checks (priority: high)
   - Review affected methods
   - Add guard clauses
   - Add unit tests

2. Implement input validation (priority: medium)
   - Add validation layer
   - Document requirements
   - Update tests

CHECKLIST:
☐ Reproduce issue consistently
☐ Check error logs
☐ Verify null conditions
☐ Implement fixes
☐ Run tests
☐ Deploy to staging
☐ Monitor production
```

## 🔧 Testing

### Test Bug Ingestion

```bash
.venv\Scripts\activate
python scripts/ingest_bugs.py
```

### Test Wiki Ingestion

```bash
.venv\Scripts\activate
python scripts/ingest_wiki.py
```

### Run Unit Tests

```bash
.venv\Scripts\activate
pytest tests/
```

## 📚 More Information

- **Architecture**: See [ARCHITECTURE.md](ARCHITECTURE.md)
- **README**: See [README.md](README.md)
- **API Docs**: http://localhost:8000/docs (when running)

## ⚠️ Troubleshooting

### "Azure DevOps Connection Failed"
- Check `.env` has correct ORG, PROJECT, TOKEN
- Verify PAT token hasn't expired
- Ensure network connectivity

### "No similar bugs found"
- Your Azure DevOps project might be empty
- Try with common keywords like "error", "bug", "issue"
- Check that your PAT token has read permissions

### "OPENAI_API_KEY not found"
- Make sure `.env` file exists
- Add valid OpenAI API key
- Restart backend server

### Streamlit connection refused
- Check backend is running on port 8000
- Check frontend is running on port 8501
- Verify CORS settings allow localhost:8501

## 🎓 Learning Path

1. **Read**: [README.md](README.md) for overview
2. **Understand**: [ARCHITECTURE.md](ARCHITECTURE.md) for detailed design
3. **Explore**: Code in `backend/app/agents/` for implementation
4. **Experiment**: Modify prompts and extraction logic
5. **Extend**: Add custom agents following base_agent pattern

## 🚀 Next Steps

- [ ] Set up Azure DevOps PAT token
- [ ] Configure `.env` file
- [ ] Start backend server
- [ ] Start frontend
- [ ] Submit your first issue
- [ ] Review the analysis and recommendations
- [ ] Experiment with different issue types
- [ ] Customize agents for your workflow
- [ ] Integrate into your development process

---

**Questions?** Check [ARCHITECTURE.md](ARCHITECTURE.md) or the inline code documentation!
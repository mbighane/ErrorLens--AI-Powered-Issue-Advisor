"""
Multi-Agent System Architecture Documentation
ErrorLens - AI-Powered Issue Solver
"""

# Multi-Agent Architecture Overview

## System Design

The ErrorLens system uses a **coordinated multi-agent architecture** where five specialized agents work together to provide comprehensive issue analysis and recommendations.

## Agents

### 1. 🧠 Orchestrator Agent (Brain)
**File**: `backend/app/agents/orchestrator_agent.py`
**Purpose**: Central coordinator of the entire system

**Responsibilities**:
- Receives user query
- Understands issue context
- Dispatches tasks to appropriate agents
- Orchestrates workflow execution
- Assembles final comprehensive response

**Process**:
1. Query Analysis
2. Dispatch to Bug Analysis Agent
3. Dispatch to Wiki Knowledge Agent
4. Execute Integration Context Agent
5. Run Recommendation Agent
6. Assemble results

**Output**: IssueSolveResponse with complete analysis

### 2. 🔍 Bug Analysis Agent
**File**: `backend/app/agents/bug_analysis_agent.py`
**Purpose**: Analyze historical bugs from Azure DevOps

**Responsibilities**:
- Search similar bugs in Azure DevOps
- Extract patterns from historical data
- Identify root causes from bug data
- Find applied fixes from resolved bugs
- Analyze common error patterns

**Data Sources**:
- Azure DevOps Work Items (Bugs)
- Historical issue tracking

**Output**:
```python
{
    "similar_bugs": [BugResult, ...],
    "patterns": {
        "common_keywords": {...},
        "affected_components": {...},
        "error_patterns": {...}
    },
    "root_causes": ["cause1", "cause2", ...],
    "fixes": ["fix1", "fix2", ...]
}
```

### 3. 📘 Wiki Knowledge Agent
**File**: `backend/app/agents/wiki_knowledge_agent.py`
**Purpose**: Search and extract knowledge from wiki

**Responsibilities**:
- Search Azure DevOps wiki
- Extract best practices
- Identify procedures and guides
- Find common patterns and solutions
- Reference troubleshooting documentation

**Data Sources**:
- Azure DevOps Wiki Pages
- Markdown documentation
- Knowledge base articles

**Output**:
```python
{
    "wiki_pages": [WikiResult, ...],
    "best_practices": ["practice1", "practice2", ...],
    "procedures": ["procedure1", "procedure2", ...],
    "common_patterns": ["pattern1", "pattern2", ...]
}
```

### 4. 🔗 Integration Context Agent
**File**: `backend/app/agents/integration_context_agent.py`
**Purpose**: Understand application architecture and dependencies

**Responsibilities**:
- Identify affected modules
- Map API dependencies
- Determine external services
- Analyze integration points
- Build context summary

**Context Analysis**:
- Module identification (Auth, Database, Cache, etc.)
- API mapping (REST, GraphQL, WebSocket, etc.)
- Dependency recognition (Redis, PostgreSQL, etc.)
- Service identification (Azure, AWS, etc.)

**Output**:
```python
{
    "modules": ["Auth Module", "Database Module", ...],
    "affected_apis": ["REST API", "GraphQL", ...],
    "dependencies": ["PostgreSQL", "Redis", ...],
    "services": ["Azure DevOps", "Jenkins", ...],
    "context": "Integration context summary"
}
```

### 5. 🧪 Recommendation Agent
**File**: `backend/app/agents/recommendation_agent.py`
**Purpose**: Synthesize insights and generate recommendations

**Responsibilities**:
- Combine all agent insights
- Synthesize root cause analysis
- Generate prioritized fixes
- Create troubleshooting checklist
- Calculate confidence levels

**Processing**:
1. Synthesize root causes from all sources
2. Generate fix suggestions (high/medium/low priority)
3. Create troubleshooting checklist
4. Calculate recommendation confidence

**Output**:
```python
{
    "root_causes": [RootCause(description, confidence), ...],
    "suggested_fixes": [SuggestedFix(description, steps, priority), ...],
    "troubleshooting_checklist": [
        "📋 Initial Investigation:",
        "  ☐ Step 1",
        "  ☐ Step 2",
        ...
    ],
    "confidence_level": 0.85  # 0.0 to 1.0
}
```

## Workflow

### Complete Issue Resolution Flow

```
User Input Query
      ↓
🧠 Orchestrator Agent (Step 1: Understand)
      ↓
🔍 Bug Analysis Agent (Step 2: Parallel)
│   ├─ Search similar bugs
│   ├─ Extract patterns
│   └─ Identify root causes
      ↓
📘 Wiki Knowledge (Step 3: Parallel)
│   ├─ Search wiki pages
│   ├─ Extract best practices
│   └─ Find procedures
      ↓
🔗 Context Analysis (Step 4: Parallel)
│   ├─ Identify modules
│   ├─ Map APIs
│   └─ List dependencies
      ↓
🧪 Recommendation Agent (Step 5: Synthesis)
│   ├─ Synthesize root causes
│   ├─ Generate fixes
│   ├─ Create checklist
│   └─ Calculate confidence
      ↓
🧠 Orchestrator Agent (Step 6: Assembly)
│   └─ Assemble final response
      ↓
Final Response to User
├─ Analysis
├─ Similar bugs
├─ Wiki references
├─ Root causes with confidence
├─ Suggested fixes with steps
├─ Troubleshooting checklist
└─ Confidence level
```

## Data Flow

### Between Agents

```
Bug Analysis Agent
├─ similar_bugs → Recommendation
├─ patterns → Wiki Agent reference
└─ root_causes → Recommendation

Wiki Knowledge Agent
├─ best_practices → Recommendation
├─ procedures → Checklist
└─ common_patterns → Recommendation

Integration Context Agent
├─ modules → Recommendation
├─ affected_apis → Recommendation
└─ dependencies → Context

Recommendation Agent
├─ synthesized_root_causes → Orchestrator
├─ fixes → Orchestrator
├─ checklist → Orchestrator
└─ confidence → Orchestrator

Orchestrator Agent
└─ final_response → API → Streamlit → User
```

## Configuration

### Environment Variables Required

```env
# Azure DevOps
AZURE_DEVOPS_ORG=your_organization
AZURE_DEVOPS_PROJECT=your_project
AZURE_DEVOPS_TOKEN=your_personal_access_token

# OpenAI
OPENAI_API_KEY=your_api_key

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
```

### Azure DevOps PAT Permissions

Required scopes for Personal Access Token:
- **Work Items**: Read
- **Wiki**: Read
- **Code**: Read (optional, for repository browsing)

## Usage

### REST API

```bash
curl -X POST http://localhost:8000/api/issues/solve \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "developer1",
    "message": "My build is failing with NullReferenceException in the payment module"
  }'
```

### Response Example

```json
{
  "analysis": "## Multi-Agent Analysis Results\n...",
  "similar_bugs": [
    {
      "id": "123",
      "title": "Payment module null reference error",
      "description": "...",
      "similarity_score": 0.85
    }
  ],
  "relevant_wiki": [
    {
      "title": "Payment Module Setup Guide",
      "content": "...",
      "similarity_score": 0.78
    }
  ],
  "root_causes": [
    {
      "description": "Null/Undefined reference",
      "confidence": 0.8
    }
  ],
  "suggested_fixes": [
    {
      "description": "Add null checks in payment module",
      "steps": [
        "Review payment service methods",
        "Add null parameter validation",
        "Add unit tests for null cases"
      ],
      "priority": "high"
    }
  ],
  "checklist": [
    "📋 Initial Investigation:",
    "  ☐ Reproduce the issue consistently",
    "  ☐ Check error logs",
    "  ☐ Verify dependencies are installed",
    "..."
  ]
}
```

## Performance Considerations

### Optimization Strategies

1. **Parallel Execution**: Bug, Wiki, and Context agents run in parallel
2. **Caching**: Azure DevOps query results cached in Redis
3. **Rate Limiting**: Azure DevOps API rate limiting handled
4. **Async Processing**: All operations are async/await

### Scalability

- Handles concurrent users through async architecture
- Agent coordination is stateless and scalable
- Can add more specialized agents without refactoring

## Extension Points

### Adding New Agents

1. Create new agent class inheriting from `Agent`
2. Implement `execute()` method
3. Register in Orchestrator
4. Update workflow

Example:
```python
class CustomAgent(Agent):
    def __init__(self):
        super().__init__("🆕 Custom Agent")
    
    async def execute(self, **kwargs):
        # Implementation
        return {"result": "..."}
```

### Customizing Agent Behavior

- Modify extraction logic in each agent
- Update confidence calculations
- Adjust priority levels
- Enhance pattern matching

## Monitoring & Logging

### Orchestrator Workflow Logging

The Orchestrator Agent provides detailed console logging:

```
============================================================
🧠 ORCHESTRATOR WORKFLOW STARTED
============================================================
Issue: My build is failing...

Step 1️⃣  Understanding issue...
✓ Query analyzed

Step 2️⃣  🔍 Bug Analysis Agent - Searching similar bugs...
✓ Found 5 similar bugs
  Root causes found: 3

...

🎉 ORCHESTRATOR WORKFLOW COMPLETED
Confidence: 85%
============================================================
```

## Testing

### Unit Testing Agents

```python
def test_bug_analysis_agent():
    agent = BugAnalysisAgent()
    result = await agent.execute("build failure")
    assert result["status"] == "success"
    assert len(result["similar_bugs"]) > 0
```

### Integration Testing

```bash
python scripts/ingest_bugs.py      # Test bug ingestion
python scripts/ingest_wiki.py      # Test wiki ingestion
# Call API endpoint and verify response
```

## Troubleshooting

### Common Issues

1. **Azure DevOps Connection Error**
   - Verify PAT token validity
   - Check organization and project names
   - Ensure network connectivity

2. **No Results Found**
   - Verify Azure DevOps has historical data
   - Check wiki pages are accessible
   - Review query keywords

3. **Slow Performance**
   - Enable Redis caching
   - Check Azure DevOps API rate limits
   - Monitor concurrent requests

## Future Enhancements

- Machine learning for confidence scoring
- Vector embeddings for semantic search
- Multi-modal analysis (code + documentation)
- Feedback loop for continuous learning
- Metrics and analytics dashboard
- Custom agent marketplace
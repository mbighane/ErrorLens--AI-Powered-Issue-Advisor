"""
🔗 Integration Context Agent
Understands module structure, APIs, and dependencies
"""

from typing import Dict, Any, List
from .base_agent import Agent

class IntegrationContextAgent(Agent):
    """
    Understands application context:
    - Module dependencies
    - API endpoints
    - External services
    - Configuration requirements
    """
    
    def __init__(self):
        super().__init__("🔗 Integration Context Agent")
    
    async def execute(self, issue_description: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Analyze the integration context of the issue
        """
        try:
            # Extract module information
            modules = self._extract_modules(issue_description)
            
            # Identify affected APIs
            affected_apis = self._identify_apis(issue_description)
            
            # Find dependencies
            dependencies = self._identify_dependencies(issue_description, context or {})
            
            # Identify affected services
            services = self._identify_services(issue_description)
            
            return {
                "agent": self.name,
                "status": "success",
                "modules": modules,
                "affected_apis": affected_apis,
                "dependencies": dependencies,
                "services": services,
                "context": self._build_context_summary(modules, affected_apis, dependencies)
            }
        except Exception as e:
            return {
                "agent": self.name,
                "status": "error",
                "error": str(e),
                "modules": [],
                "affected_apis": [],
                "dependencies": [],
                "services": []
            }
    
    def _extract_modules(self, issue: str) -> List[str]:
        """
        Extract module names from issue description
        """
        issue_lower = issue.lower()
        modules = set()
        
        # Common module names
        module_keywords = {
            "auth": "Authentication Module",
            "database": "Database Module",
            "cache": "Cache Module",
            "payment": "Payment Module",
            "api": "API Module",
            "webhook": "Webhook Module",
            "queue": "Queue Module",
            "storage": "Storage Module",
            "notification": "Notification Module",
            "logging": "Logging Module",
            "security": "Security Module",
            "validation": "Validation Module"
        }
        
        for keyword, module_name in module_keywords.items():
            if keyword in issue_lower:
                modules.add(module_name)
        
        return list(modules)
    
    def _identify_apis(self, issue: str) -> List[str]:
        """
        Identify affected APIs from issue description
        """
        issue_lower = issue.lower()
        apis = set()
        
        # API patterns
        api_keywords = {
            "rest": "REST API",
            "graphql": "GraphQL API",
            "websocket": "WebSocket API",
            "grpc": "gRPC",
            "endpoint": "API Endpoint",
            "request": "HTTP Request",
            "response": "API Response",
            "authentication": "Auth API",
            "rate limit": "Rate Limiting"
        }
        
        for keyword, api_name in api_keywords.items():
            if keyword in issue_lower:
                apis.add(api_name)
        
        return list(apis)
    
    def _identify_dependencies(self, issue: str, context: Dict) -> List[str]:
        """
        Identify external dependencies
        """
        issue_lower = issue.lower()
        dependencies = set()
        
        # Dependency keywords
        dep_keywords = {
            "database": "Database (PostgreSQL/MySQL)",
            "redis": "Redis Cache",
            "elasticsearch": "Elasticsearch",
            "kafka": "Kafka Message Queue",
            "openai": "OpenAI API",
            "azure": "Azure Services",
            "aws": "AWS Services",
            "google cloud": "Google Cloud",
            "smtp": "Email Service",
            "s3": "S3 Storage",
            "cdn": "CDN"
        }
        
        for keyword, dep_name in dep_keywords.items():
            if keyword in issue_lower:
                dependencies.add(dep_name)
        
        return list(dependencies)
    
    def _identify_services(self, issue: str) -> List[str]:
        """
        Identify affected external services
        """
        issue_lower = issue.lower()
        services = set()
        
        service_keywords = {
            "devops": "Azure DevOps",
            "github": "GitHub",
            "gitlab": "GitLab",
            "jenkins": "Jenkins CI/CD",
            "docker": "Docker",
            "kubernetes": "Kubernetes",
            "terraform": "Terraform",
            "monitoring": "Monitoring Service",
            "alerting": "Alert System"
        }
        
        for keyword, service_name in service_keywords.items():
            if keyword in issue_lower:
                services.add(service_name)
        
        return list(services)
    
    def _build_context_summary(self, modules: List[str], apis: List[str], deps: List[str]) -> str:
        """
        Build a summary of the integration context
        """
        summary_parts = []
        
        if modules:
            summary_parts.append(f"Affected modules: {', '.join(modules)}")
        if apis:
            summary_parts.append(f"Involved APIs: {', '.join(apis)}")
        if deps:
            summary_parts.append(f"External dependencies: {', '.join(deps)}")
        
        if not summary_parts:
            return ""
        
        return " | ".join(summary_parts)
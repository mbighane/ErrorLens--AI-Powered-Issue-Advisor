from azure.devops.connection import Connection
from azure.devops.v7_1.work_item_tracking.models import Wiql
from msrest.authentication import BasicAuthentication
from typing import List, Dict, Any, Set
import re
from ..config import settings

# Maps theme names to keyword fragments that signal that theme.
# Keywords are matched as substrings against lowercased, HTML-stripped text.
SYMPTOM_THEMES: Dict[str, List[str]] = {
    "missing_ui":      ["disappear", "missing", "not show", "blank", "hidden",
                        "not visible", "not available", "unavailable", "gone",
                        "no longer", "not display"],
    "text_rendering":  ["extra space", "spacing", "whitespace", "character",
                        "encoding", "font", "truncat", "overlap", "garbl"],
    "crash_error":     ["crash", "exception", "unhandled", "stack trace",
                        "error message", "throws", "fatal"],
    "failure":         ["fail", "not work", "broken", "does not", "doesn't",
                        "stopped working", "no longer work"],
    "performance":     ["slow", "hang", "freeze", "timeout", "delay",
                        "performance", "lag", "not respond"],
    "grid_table":      ["grid", "table", "datagrid", "gridview", "listview",
                        "column", "row", "activex", "ocx"],
    "migration":       ["migration", "migrat", "winform", "vb6", "upgrade",
                        "convert", "legacy", "net framework", "ported"],
    "report":          ["report", "reporting", "print preview", "export"],
    "view_screen":     ["view", "screen", "page", "panel", "window", "form"],
    "data_integrity":  ["wrong data", "incorrect data", "corrupt", "mismatch",
                        "invalid data", "data loss", "overwrite"],
    "form_control":    ["text field", "textbox", "input field", "button",
                        "dropdown", "combobox", "checkbox", "form field"],
    "database":        ["database", " sql ", "query fail", "connection string",
                        "db error", "timeout",
                        "fail to connect", "cannot connect", "connection fail",
                        "connection refused", "connection reset", "connection lost",
                        "connection pool", "pool exhausted", "connection timeout",
                        "stored procedure", "sproc", "proc fail", "procedure fail",
                        "parameter mismatch", "parameter count", "wrong parameter",
                        "invalid parameter", "expected parameter", "missing parameter",
                        "ado.net", "adonet", "sqlclient", "oledbconnection",
                        "odbc", "data provider", "provider not found",
                        "invalid connection", "login fail", "login timeout",
                        "server not found", "instance not found", "network path",
                        "sql exception", "sqlexception", "db exception",
                        "transaction fail", "rollback", "deadlock",
                        "schema mismatch", "column not found", "table not found",
                        "invalid object name", "object not found in database"],
    "datetime":        ["incorrect date", "wrong date", "invalid date", "date mismatch",
                        "wrong duration", "incorrect duration", "elapsed day", "elapsed time",
                        "time difference", "inaccurate time", "wrong time", "incorrect time",
                        "date calculation", "date format", "timezone", "time zone",
                        "daylight saving", "dst", "leap year", "month end",
                        "scheduling", "subscription record", "billing", "miscalcul",
                        "expir", "renewal date", "due date", "date off by"],
    "com_interop":     ["com ", "com+", "interop", "dcom", "ole ", "oledb", "ole automation",
                        "activex", "ocx", "com object", "com component", "com server",
                        "runtime callable wrapper", "rcw", "com callable wrapper", "ccw",
                        "marshal", "marshaling", "marshalling", "p/invoke", "pinvoke",
                        "unmanaged", "native code", "tlbimp", "aximp", "regsvr",
                        "dispatch", "idispatch", "iunknown", "hresult", "e_fail",
                        "apartment", "sta ", "mta ", "com exception", "cocreate",
                        "late binding", "early binding", "progid", "clsid",
                        "typelib", "type library", "variant", "bstr", "safearray",
                        "excel", "word", "outlook", "office interop", "office automation",
                        "spreadsheet", "workbook", "worksheet",
                        "third-party", "third party", "external component", "external library",
                        "plugin", "add-in", "addin", "dll not found", "missing dll",
                        "not registered", "registration", "regasm", "gac ",
                        "assembly not found", "failed to load", "could not load",
                        "interop assembly", "primary interop"],
    "numeric_calc":    ["wrong rounding", "incorrect rounding", "rounding error", "rounding issue",
                        "inconsistent rounding", "rounding mismatch",
                        "off by one", "off-by-one", "fencepost", "fence post",
                        "wrong total", "incorrect total", "total mismatch", "totals wrong",
                        "wrong sum", "incorrect sum", "sum mismatch",
                        "financial calculation", "financial report", "invoice total",
                        "calculation error", "calculation wrong", "calculation mismatch",
                        "numeric overflow", "overflow error", "integer overflow",
                        "floating point", "precision error", "precision loss",
                        "decimal mismatch", "decimal precision", "currency rounding",
                        "midpoint", "banker rounding", "arithmetic", "wrong result",
                        "incorrect result", "wrong value", "incorrect value",
                        "boundary value", "edge case value"],
}


class AzureDevOpsConnector:
    def __init__(self):
        self.organization = settings.azure_devops_org
        self.project = settings.azure_devops_project
        self.token = settings.azure_devops_token
        
        if not self.token or not self.organization or not self.project:
            raise ValueError("Azure DevOps configuration missing in .env")
        
        credentials = BasicAuthentication('', self.token)
        self.connection = Connection(
            base_url=f"https://dev.azure.com/{self.organization}",
            creds=credentials
        )
        self.work_item_client = self.connection.clients.get_work_item_tracking_client()
        self.git_client = None

    def _get_git_client(self):
        """
        Lazily initialize git client so bug analysis can run without wiki dependencies.
        """
        if self.git_client is None:
            self.git_client = self.connection.clients.get_git_client()
        return self.git_client

    @staticmethod
    def _extract_root_cause_analysis(fields: Dict[str, Any]) -> str:
        """
        Extract root cause analysis from common ADO custom/system field keys.
        """
        candidate_keys = [
            "Custom.RootCauseAnalysis",
            "Microsoft.VSTS.Common.RootCause",
            "Root Cause Analysis",
            "RootCauseAnalysis",
        ]

        for key in candidate_keys:
            value = fields.get(key)
            if value:
                return str(value)

        # Fallback: find any key that looks like a root-cause field.
        for key, value in fields.items():
            normalized_key = key.lower().replace("_", " ")
            if "root" in normalized_key and "cause" in normalized_key and value:
                return str(value)

        return ""

    @staticmethod
    def _extract_assigned_to(fields: Dict[str, Any]) -> str:
        assigned_to = fields.get("System.AssignedTo", "")
        if isinstance(assigned_to, dict):
            return assigned_to.get("displayName", "")
        return str(assigned_to) if assigned_to else ""

    @staticmethod
    def _sanitize_wiql_text(value: str) -> str:
        return value.replace("'", "''")

    @staticmethod
    def _tokenize_query(query: str) -> List[str]:
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "after", "before", "on",
            "in", "at", "to", "for", "and", "or", "of", "with", "from", "not",
        }
        tokens = re.findall(r"[a-zA-Z0-9]+", query.lower())
        unique_tokens: List[str] = []
        seen = set()
        for token in tokens:
            if len(token) < 3 or token in stop_words:
                continue
            if token not in seen:
                unique_tokens.append(token)
                seen.add(token)
        return unique_tokens

    @staticmethod
    def _clean_text(value: str) -> str:
        text = re.sub(r"<[^>]+>", " ", value or "")
        return re.sub(r"\s+", " ", text).strip().lower()

    def _extract_themes(self, text: str) -> Set[str]:
        """Return the set of symptom theme names present in *text*."""
        lowered = self._clean_text(text)
        found: Set[str] = set()
        for theme, keywords in SYMPTOM_THEMES.items():
            for kw in keywords:
                if kw in lowered:
                    found.add(theme)
                    break
        return found

    def _score_bug_match(self, query: str, bug: Dict[str, Any]) -> float:
        """
        Composite score = 60 % theme overlap + 40 % title token overlap.

        Theme component
        ---------------
        * Extract symptom themes from the query.
        * Compare against themes found in the bug *title* (weight 2×) and
          the full content (title + description + RCA) (weight 1×).
        * This prevents description-level keyword noise from inflating
          scores for unrelated bugs.

        Title token component
        ---------------------
        * Plain token overlap restricted to the bug *title* only, so two
          bugs whose descriptions both mention a migration framework cannot
          score equally against a very specific query.
        """
        query_themes = self._extract_themes(query)
        title_text   = bug.get("title", "")
        body_text    = " ".join([
            bug.get("description", ""),
            bug.get("root_cause_analysis", ""),
        ])

        # --- Theme component (60 %) ---
        if query_themes:
            title_themes   = self._extract_themes(title_text)
            content_themes = self._extract_themes(title_text + " " + body_text)
            n = len(query_themes)
            title_theme_score   = len(query_themes & title_themes)   / n
            overall_theme_score = len(query_themes & content_themes) / n
            # Title theme hit counts double
            theme_score = (title_theme_score * 2.0 + overall_theme_score) / 3.0
        else:
            theme_score = 0.0

        # --- Title token component (40 %) ---
        query_tokens = set(self._tokenize_query(query))
        title_tokens = set(self._tokenize_query(title_text))
        if query_tokens:
            title_token_score = len(query_tokens & title_tokens) / len(query_tokens)
        else:
            title_token_score = 0.0

        score = 0.6 * theme_score + 0.4 * title_token_score

        # Small bonus when the full query phrase appears verbatim in the title
        if self._clean_text(query) in self._clean_text(title_text):
            score += 0.15

        return min(score, 1.0)

    def _query_issue_ids(self, wiql_query: str, top: int) -> List[int]:
        wiql = Wiql(query=wiql_query)
        results = self.work_item_client.query_by_wiql(wiql, top=top)
        return [wi.id for wi in results.work_items]

    async def search_bugs(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Search for Issue work items in Azure DevOps that match the query.
        Uses title, description, and root-cause-analysis content for bug analysis.
        """
        try:
            # Exact phrase query first.
            safe_query = self._sanitize_wiql_text(query)
            exact_wiql = f"""
            SELECT [System.Id], [System.Title], [System.Description], [System.State], [System.AssignedTo]
            FROM WorkItems
            WHERE [System.TeamProject] = '{self.project}'
            AND [System.WorkItemType] = 'Issue'
            AND (
                [System.Title] CONTAINS '{safe_query}'
                OR [System.Description] CONTAINS '{safe_query}'
            )
            ORDER BY [System.ChangedDate] DESC
            """

            candidate_ids = self._query_issue_ids(exact_wiql, top=max(top_k * 3, 10))

            # Paraphrase fallback query based on meaningful tokens.
            if not candidate_ids:
                tokens = self._tokenize_query(query)[:8]
                if tokens:
                    token_clauses = []
                    for token in tokens:
                        safe_token = self._sanitize_wiql_text(token)
                        token_clauses.append(f"[System.Title] CONTAINS '{safe_token}'")
                        token_clauses.append(f"[System.Description] CONTAINS '{safe_token}'")

                    token_wiql = f"""
                    SELECT [System.Id], [System.Title], [System.Description], [System.State], [System.AssignedTo]
                    FROM WorkItems
                    WHERE [System.TeamProject] = '{self.project}'
                    AND [System.WorkItemType] = 'Issue'
                    AND (
                        {' OR '.join(token_clauses)}
                    )
                    ORDER BY [System.ChangedDate] DESC
                    """
                    candidate_ids = self._query_issue_ids(token_wiql, top=max(top_k * 6, 20))
            
            bugs = []
            seen_ids = set()
            for work_item_id in candidate_ids:
                if work_item_id in seen_ids:
                    continue
                seen_ids.add(work_item_id)

                item = self.work_item_client.get_work_item(work_item_id)
                fields = item.fields or {}
                root_cause_analysis = self._extract_root_cause_analysis(fields)
                bugs.append({
                    "id": str(item.id),
                    "title": fields.get("System.Title", ""),
                    "description": fields.get("System.Description", ""),
                    "root_cause_analysis": root_cause_analysis,
                    "state": fields.get("System.State", ""),
                    "assigned_to": self._extract_assigned_to(fields),
                    "url": item.url
                })

            scored_bugs = [
                {**bug, "similarity_score": self._score_bug_match(query, bug)}
                for bug in bugs
            ]
            ranked_bugs = sorted(scored_bugs, key=lambda b: b["similarity_score"], reverse=True)

            return ranked_bugs[:top_k]
        except Exception as e:
            print(f"Error searching bugs: {str(e)}")
            return []

    async def search_wiki_pages(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Search for wiki pages in Azure DevOps that match the query.
        Uses the REST API directly (via requests) instead of the ADO SDK git client
        to avoid UnicodeDecodeError on wiki content with Windows-1252 characters.
        """
        import base64
        import requests as _requests

        headers = {
            "Authorization": "Basic " + base64.b64encode(
                f":{self.token}".encode("ascii")
            ).decode("ascii"),
            "Accept": "application/json",
        }
        base = f"https://dev.azure.com/{self.organization}/{self.project}"
        wiki_items: List[Dict] = []

        try:
            # List all wikis in the project
            wikis_url = f"https://dev.azure.com/{self.organization}/{self.project}/_apis/wiki/wikis?api-version=7.1"
            resp = _requests.get(wikis_url, headers=headers, timeout=10)
            resp.raise_for_status()
            wikis = resp.json().get("value", [])

            for wiki in wikis:
                wiki_id = wiki.get("id") or wiki.get("name", "")
                if not wiki_id:
                    continue

                # List pages in this wiki
                pages_url = (
                    f"https://dev.azure.com/{self.organization}/{self.project}"
                    f"/_apis/wiki/wikis/{wiki_id}/pages?recursionLevel=2&api-version=7.1"
                )
                try:
                    pages_resp = _requests.get(pages_url, headers=headers, timeout=10)
                    pages_resp.raise_for_status()
                    root_page = pages_resp.json()
                except Exception as e:
                    print(f"[WikiSearch] Failed to list pages for wiki '{wiki_id}': {e}")
                    continue

                # Flatten page tree (root + sub-pages)
                def _collect_pages(node):
                    pages = [node]
                    for sub in node.get("subPages", []):
                        pages.extend(_collect_pages(sub))
                    return pages

                for page in _collect_pages(root_page):
                    path  = page.get("path", "/")
                    title = path.strip("/").replace("/", " > ") or wiki.get("name", path)
                    url   = page.get("remoteUrl", "")

                    # Fetch page content by path (more reliable than by ID)
                    content = ""
                    try:
                        import urllib.parse as _urlparse
                        encoded_path = _urlparse.quote(path, safe="")
                        content_url = (
                            f"https://dev.azure.com/{self.organization}/{self.project}"
                            f"/_apis/wiki/wikis/{wiki_id}/pages"
                            f"?path={encoded_path}&includeContent=true&api-version=7.1"
                        )
                        c_resp = _requests.get(content_url, headers=headers, timeout=10)
                        raw_bytes = c_resp.content
                        try:
                            text = raw_bytes.decode("utf-8")
                        except UnicodeDecodeError:
                            text = raw_bytes.decode("latin-1")
                        import json as _json
                        page_data = _json.loads(text)
                        # Sanitise: replace any char that can't round-trip through UTF-8
                        raw_content = page_data.get("content", "")
                        content = raw_content.encode("utf-8", errors="replace").decode("utf-8")
                    except Exception:
                        content = ""

                    wiki_items.append({
                        "title":   title,
                        "path":    path,
                        "url":     url,
                        "content": content,
                    })

                    if len(wiki_items) >= top_k:
                        break

                if len(wiki_items) >= top_k:
                    break

        except Exception as e:
            print(f"Error searching wiki: {str(e)}")
            return []

        print(f"[WikiSearch] Found {len(wiki_items)} wiki page(s) via REST API.")
        return wiki_items[:top_k]

    def get_bug_details(self, bug_id: int) -> Dict:
        """
        Get detailed information about a specific bug
        """
        try:
            item = self.work_item_client.get_work_item(bug_id, expand=1)
            return {
                "id": str(item.id),
                "title": item.fields.get("System.Title", ""),
                "description": item.fields.get("System.Description", ""),
                "state": item.fields.get("System.State", ""),
                "priority": item.fields.get("Microsoft.VSTS.Common.Priority", ""),
                "severity": item.fields.get("Microsoft.VSTS.Common.Severity", ""),
                "assigned_to": item.fields.get("System.AssignedTo", {}).get("displayName", ""),
                "created_date": item.fields.get("System.CreatedDate", ""),
                "closed_date": item.fields.get("Microsoft.VSTS.Common.ClosedDate", ""),
                "tags": item.fields.get("System.Tags", "").split(";") if item.fields.get("System.Tags") else [],
                "url": item.url
            }
        except Exception as e:
            print(f"Error getting bug details: {str(e)}")
            return {}
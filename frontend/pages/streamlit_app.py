import streamlit as st
import requests
import uuid
import re
from html import unescape


API_BASE_URL = "http://localhost:8000"


def clean_text(value: str) -> str:
    if not value:
        return ""
    text = unescape(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_root_cause_analysis(bug: dict) -> str:
    metadata = bug.get("metadata", {}) or {}
    rca = metadata.get("root_cause_analysis", "")
    if rca:
        return clean_text(str(rca))

    description = bug.get("description", "")
    marker = "Root Cause Analysis:"
    if marker in description:
        return clean_text(description.split(marker, 1)[1])

    return ""


def extract_relevant_snippet(content: str, query: str) -> str:
    """Return the wiki block most relevant to the query based on keyword overlap."""
    if not content or not query:
        return content
    blocks = [b.strip() for b in re.split(r'\n\s*\n', content) if b.strip()]
    if len(blocks) <= 1:
        return content
    stopwords = {'the', 'a', 'an', 'is', 'in', 'to', 'and', 'or', 'of', 'with', 'for', 'on', 'at'}
    query_words = set(re.findall(r'\w+', query.lower())) - stopwords
    best_idx, best_score = 0, -1
    for i, block in enumerate(blocks):
        words = set(re.findall(r'\w+', block.lower()))
        score = len(query_words & words)
        if score > best_score:
            best_score, best_idx = score, i
    if best_score == 0:
        return blocks[0]
    # Include preceding block (usually the section header) for context
    start = max(0, best_idx - 1)
    return '\n\n'.join(blocks[start: best_idx + 2])


def extract_suggested_fix(bug: dict) -> str:
    metadata = bug.get("metadata", {}) or {}
    fix = metadata.get("suggested_fix", "")
    return clean_text(str(fix)) if fix else ""


def get_user_id() -> str:
    if "user_id" not in st.session_state:
        st.session_state.user_id = f"streamlit-{uuid.uuid4().hex[:8]}"
    return st.session_state.user_id


def solve_issue(query: str) -> dict:
    response = requests.post(
        f"{API_BASE_URL}/api/issues/solve",
        json={
            "user_id": get_user_id(),
            "message": query,
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def render_result(result: dict, query: str = "") -> None:
    st.subheader("Solution")
    st.markdown(result.get("analysis", "No analysis returned."))

    # Show only the single highest-scoring bug (already sorted by Pass-2 score)
    all_similar = result.get("similar_bugs", [])
    similar_bugs = all_similar[:1] if all_similar else []
    if similar_bugs:
        st.subheader("Similar Issues")
        for bug in similar_bugs:
            title = bug.get("title", "Untitled")
            score = bug.get("similarity_score", 0.0)
            st.markdown(f"- **{title}** ({score:.2f})")

            bug_description = clean_text(str(bug.get("description", "")))
            root_cause_analysis = extract_root_cause_analysis(bug)
            suggested_fix = extract_suggested_fix(bug)

            if bug_description or root_cause_analysis or suggested_fix:
                with st.expander(f"Details: {title}"):
                    if bug_description:
                        st.markdown(f"**Description:** {bug_description}")
                    if root_cause_analysis:
                        st.markdown(f"**Root Cause Analysis:** {root_cause_analysis}")
                    if suggested_fix:
                        st.markdown(f"**Suggested Fix (from ADO):** {suggested_fix}")

    wiki_with_content = [p for p in result.get("relevant_wiki", []) if p.get("content", "").strip()]
    if wiki_with_content:
        st.subheader("Relevant Wiki")
        for page in wiki_with_content:
            title = page.get("title", "Untitled")
            score = page.get("similarity_score", 0.0)
            content = page.get("content", "").strip()
            url = page.get("url", "")
            snippet = extract_relevant_snippet(content, query) if query else content
            st.markdown(f"- **{title}** ({score:.2f})")
            with st.expander(f"Lessons from: {title}"):
                st.markdown(snippet)
                if url:
                    st.markdown(f"[View in Azure DevOps Wiki]({url})")

    root_causes = result.get("root_causes", [])
    if root_causes:
        st.subheader("Root Causes")
        for cause in root_causes:
            description = cause.get("description", "")
            confidence = cause.get("confidence", 0.0)
            st.markdown(f"- {description} ({confidence:.0%})")

    suggested_fixes = result.get("suggested_fixes", [])
    if suggested_fixes:
        st.subheader("Suggested Fixes")
        priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        for i, fix in enumerate(suggested_fixes, 1):
            description = fix.get("description", "")
            priority = fix.get("priority", "medium")
            steps = fix.get("steps", [])
            badge = priority_emoji.get(priority, "🟡")
            with st.expander(f"{badge} **Fix {i}:** {description}  `{priority.upper()}`", expanded=(i == 1)):
                if steps:
                    for j, step in enumerate(steps, 1):
                        st.markdown(f"**{j}.** {step}")



st.title("ErrorLens - AI Issue Solver")

st.markdown("""
An intelligent system that connects to Azure DevOps to learn from past bugs and wiki knowledge,
preventing and solving development issues faster.
""")

# Input for user query
user_query = st.text_input("Describe your development issue:")

if st.button("Solve Issue"):
    if user_query:
        # Clear any cached result immediately so stale data is never shown
        st.session_state.pop("last_result", None)
        st.session_state["last_query"] = user_query
        try:
            with st.spinner("Analyzing issue..."):
                st.session_state.last_result = solve_issue(user_query)
        except requests.HTTPError as exc:
            detail = exc.response.text if exc.response is not None else str(exc)
            st.error(f"Backend request failed: {detail}")
        except requests.RequestException as exc:
            st.error(f"Could not reach backend at {API_BASE_URL}: {exc}")
    else:
        st.warning("Please enter a query.")

if "last_result" in st.session_state:
    render_result(st.session_state.last_result, st.session_state.get("last_query", ""))
else:
    st.subheader("Solution")
    st.write("Submit an issue to see analysis results.")
from langchain_core.prompts import PromptTemplate

REPORT_TEMPLATE = """
SYSTEM: You are a senior security analyst. Generate a readable inventory and risk report based on the provided asset data.
Use ONLY the data provided below. Reference specific assets by their values (e.g., example.com).
DO NOT invent any assets, metrics, or risks that are not explicitly present or derivable from the data.

DATA CONTEXT (Assets Summary):
{assets_summary}

DATA CONTEXT (Aggregate Stats):
{stats}

VALID ASSET REFERENCES (use ONLY these IDs and values):
{valid_references}

TASK:
Generate a professional security asset inventory report in Markdown with these sections:
1. Executive Summary
2. Asset Inventory (counts by type, highlight active vs stale)
3. Risk Findings (expired certs, exposed services, EOL tech)
4. Recommendations

Focus on clarity and conciseness.
"""

report_prompt = PromptTemplate.from_template(REPORT_TEMPLATE)

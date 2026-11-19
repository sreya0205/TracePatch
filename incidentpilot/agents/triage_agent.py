import re
from typing import List, Literal, Tuple
from incidentpilot.schemas import LogTriageOutput
from incidentpilot.prompts import TRIAGE_AGENT_PROMPT
from incidentpilot.agents.base import LLMClient


class LogTriageAgent:
    """
    Agent 1: Log Triage & Fingerprinting Agent.
    Parses messy logs, redacts PII/secrets, discards framework noise,
    extracts the terminating exception and implicated files, and rates severity.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()

    def sanitize_pii(self, logs: str) -> str:
        """
        Strips PII, API keys, bearer tokens, internal IP addresses, and UUIDs,
        substituting generic placeholders.
        """
        sanitized = logs

        # Redact Bearer Tokens
        sanitized = re.sub(
            r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*",
            r"\1<REDACTED_BEARER_TOKEN>",
            sanitized,
            flags=re.IGNORECASE,
        )

        # Redact API Keys (e.g. key=..., api_key=..., secret=...)
        sanitized = re.sub(
            r"(api[_-]?key|secret|token|password|auth|access_key)[\s:=]+(['\"]?)[A-Za-z0-9_\-]{8,}(['\"]?)",
            r"\1=\2<REDACTED_API_KEY>\3",
            sanitized,
            flags=re.IGNORECASE,
        )

        # Redact IPv4 Addresses
        sanitized = re.sub(
            r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|127\.0\.0\.1)\b",
            "<REDACTED_INTERNAL_IP>",
            sanitized,
        )

        # Redact general IPv4
        sanitized = re.sub(
            r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
            "<REDACTED_IP>",
            sanitized,
        )

        # Redact UUIDs
        sanitized = re.sub(
            r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
            "<REDACTED_UUID>",
            sanitized,
        )

        # Redact Emails
        sanitized = re.sub(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "<REDACTED_EMAIL>",
            sanitized,
        )

        return sanitized

    def filter_noise(self, logs: str) -> str:
        """
        Filters uninformative framework noise like standard HTTP 200 logs and heartbeat traces.
        """
        lines = logs.splitlines()
        filtered = []
        noise_patterns = [
            re.compile(r'GET\s+/(health|metrics|ping|heartbeat|favicon\.ico)\s+HTTP/.*200', re.I),
            re.compile(r'INFO:\s+Uvicorn running on', re.I),
            re.compile(r'INFO:\s+Started server process', re.I),
            re.compile(r'DEBUG:\s+Keep-alive', re.I),
        ]
        for line in lines:
            if any(p.search(line) for p in noise_patterns):
                continue
            filtered.append(line)
        return "\n".join(filtered)

    def extract_traceback_details(self, text: str) -> Tuple[str, str, List[str]]:
        """
        Parses python traceback frames to extract terminating exception,
        exact error message, and internal file paths.
        """
        # Match standard Python exception line at end of traceback: e.g. "ZeroDivisionError: division by zero"
        exception_regex = re.compile(
            r"^([a-zA-Z_][a-zA-Z0-9_\.]*(?:Error|Exception|Warning|Interrupt|Exit|Fault|Timeout|Mismatch|Failed)):\s*(.*)$",
            re.MULTILINE,
        )
        matches = list(exception_regex.finditer(text))
        
        error_type = "UnhandledException"
        error_message = "An unhandled exception occurred in application code"
        if matches:
            last_match = matches[-1]
            error_type = last_match.group(1).split(".")[-1]
            error_message = last_match.group(2).strip()
        else:
            # Fallback check for single line error patterns
            alt_match = re.search(r"(\w+Error):\s*(.+)", text)
            if alt_match:
                error_type = alt_match.group(1)
                error_message = alt_match.group(2).strip()

        # Extract implicated internal files: File "...", line X, in ...
        file_regex = re.compile(r'File\s+["\']([^"\']+\.py)["\'],\s+line\s+(\d+)', re.MULTILINE)
        implicated = []
        for file_match in file_regex.finditer(text):
            fpath = file_match.group(1).replace("\\", "/")
            # Filter out standard library and site-packages unless user project
            if "site-packages" not in fpath and "lib/python" not in fpath:
                implicated.append(fpath)

        # Deduplicate while preserving order
        unique_files = []
        for f in implicated:
            if f not in unique_files:
                unique_files.append(f)

        return error_type, error_message, unique_files

    def assess_severity(self, text: str, error_type: str) -> Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        text_lower = f"{text} {error_type}".lower()
        if any(w in text_lower for w in ["payment", "billing", "corruption", "security", "auth", "credential", "data loss", "deadlock"]):
            return "CRITICAL"
        if any(w in text_lower for w in ["zerodivision", "crash", "500", "fatal", "out of memory", "timeout", "broken pipe", "integrityerror"]):
            return "HIGH"
        if any(w in text_lower for w in ["bad request", "404", "validation", "keyerror", "typeerror", "valueerror"]):
            return "MEDIUM"
        return "LOW"

    def triage(self, raw_logs: str) -> LogTriageOutput:
        """
        Executes complete log triage, attempting LLM parsing first,
        falling back to deterministic traceback parsing and PII redaction.
        """
        sanitized = self.sanitize_pii(raw_logs)
        cleaned = self.filter_noise(sanitized)

        if self.llm_client.has_active_llm():
            try:
                user_prompt = f"Analyze these raw production logs:\n\n{cleaned}"
                return self.llm_client.generate_structured(
                    system_prompt=TRIAGE_AGENT_PROMPT,
                    user_prompt=user_prompt,
                    response_model=LogTriageOutput,
                )
            except Exception:
                pass

        # Deterministic extraction engine
        error_type, error_message, culprit_files = self.extract_traceback_details(cleaned)
        severity = self.assess_severity(cleaned, error_type)

        return LogTriageOutput(
            error_type=error_type,
            error_message=error_message,
            culprit_module_hints=culprit_files,
            sanitized_trace=cleaned,
            severity=severity,
        )

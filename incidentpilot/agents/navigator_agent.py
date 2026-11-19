import os
import re
from typing import List, Optional
from incidentpilot.schemas import (
    LogTriageOutput,
    CodeNavigatorOutput,
    CodeSnippet,
)
from incidentpilot.tools.ast_tools import ASTSearchEngine
from incidentpilot.tools.git_tools import GitRepoInspector
from incidentpilot.prompts import CODEBASE_NAVIGATOR_PROMPT
from incidentpilot.agents.base import LLMClient


class CodeNavigatorAgent:
    """
    Agent 2: Codebase Navigator Agent.
    Pinpoints culprit code using AST symbol lookup, extracts context-bounded
    snippets (<80 lines), performs Git blame analysis, and drafts an engineering hypothesis.
    """

    def __init__(
        self,
        repo_path: str = ".",
        llm_client: Optional[LLMClient] = None,
    ):
        self.repo_path = repo_path
        self.ast_engine = ASTSearchEngine(repo_path)
        self.git_inspector = GitRepoInspector(repo_path)
        self.llm_client = llm_client or LLMClient()

    def navigate(self, triage: LogTriageOutput) -> CodeNavigatorOutput:
        """
        Navigates the repository using triage hints and AST inspection.
        """
        suspect_file = ""
        line_no = None

        # Extract file and line from sanitized trace if possible
        line_matches = list(re.finditer(r'File\s+["\']([^"\']+\.py)["\'],\s+line\s+(\d+)', triage.sanitized_trace))
        if line_matches:
            # The last internal file frame in the stack trace is typically the point of failure
            last_match = line_matches[-1]
            suspect_file = last_match.group(1).replace("\\", "/")
            line_no = int(last_match.group(2))
        elif triage.culprit_module_hints:
            suspect_file = triage.culprit_module_hints[-1]

        # Normalize relative path
        if not suspect_file:
            suspect_file = "app/main.py"

        snippets: List[CodeSnippet] = []
        if line_no:
            snippets = self.ast_engine.extract_snippets_around_line(suspect_file, line_no, window=35)

        if not snippets:
            # Try searching for symbols or functions named in the error or hints
            extracted_symbols = re.findall(r"in\s+([a-zA-Z_][a-zA-Z0-9_]*)", triage.sanitized_trace)
            for sym in reversed(extracted_symbols):
                found = self.ast_engine.search_symbol(suspect_file, sym)
                if found:
                    snippets.append(found)
                    break

        if not snippets:
            # Fallback snippet to represent suspect location
            snippets.append(
                CodeSnippet(
                    file_path=suspect_file,
                    symbol_name="suspect_routine",
                    start_line=line_no or 1,
                    end_line=(line_no or 1) + 20,
                    code_content=f"# Offending code location in {suspect_file}\n# Triggered {triage.error_type}: {triage.error_message}",
                )
            )

        # Ensure all snippets adhere to the < 80 line constraint
        bounded_snippets: List[CodeSnippet] = []
        for s in snippets:
            lines = s.code_content.splitlines()
            if len(lines) > 80:
                s.code_content = "\n".join(lines[:80])
                s.end_line = s.start_line + 79
            bounded_snippets.append(s)

        # Inspect Git commit history and blame
        primary_snippet = bounded_snippets[0]
        recent_shas = self.git_inspector.recent_commits(suspect_file, count=3)

        # Engineering Hypothesis Formulation
        hypothesis = (
            f"Execution reached {suspect_file}:{primary_snippet.start_line}-{primary_snippet.end_line} "
            f"where unexpected input or boundary state triggered a terminating {triage.error_type} ('{triage.error_message}'). "
            f"The offending code failed to guard against this condition prior to evaluation."
        )

        # If LLM is active, refine hypothesis
        if self.llm_client.has_active_llm():
            try:
                user_prompt = (
                    f"Triage Diagnostic:\n{triage.model_dump_json(indent=2)}\n\n"
                    f"Suspect Code Snippets:\n"
                    + "\n".join([f"File: {s.file_path} (Lines {s.start_line}-{s.end_line})\n{s.code_content}" for s in bounded_snippets])
                )
                output = self.llm_client.generate_structured(
                    system_prompt=CODEBASE_NAVIGATOR_PROMPT,
                    user_prompt=user_prompt,
                    response_model=CodeNavigatorOutput,
                )
                # Enforce snippet limits
                for snip in output.relevant_snippets:
                    lines = snip.code_content.splitlines()
                    if len(lines) > 80:
                        snip.code_content = "\n".join(lines[:80])
                        snip.end_line = snip.start_line + 79
                return output
            except Exception:
                pass

        return CodeNavigatorOutput(
            primary_suspect_file=suspect_file,
            relevant_snippets=bounded_snippets,
            recent_commit_shas=recent_shas,
            hypothesis=hypothesis,
        )

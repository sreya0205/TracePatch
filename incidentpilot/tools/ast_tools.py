import ast
import os
import re
from typing import List, Optional, Dict, Any
from incidentpilot.schemas import CodeSnippet


class ASTSearchEngine:
    """
    AST Search and Codebase Inspection Engine.
    Provides precise, context-bounded AST extraction (under 80 lines)
    for suspect symbols, classes, functions, and line ranges.
    """

    def __init__(self, repo_path: str = "."):
        self.repo_path = os.path.abspath(repo_path)

    def _resolve_path(self, relative_path: str) -> str:
        # Strip leading slashes or repo directory name if redundant
        clean_path = relative_path.replace("\\", "/").lstrip("/")
        full_path = os.path.join(self.repo_path, clean_path)
        if os.path.exists(full_path):
            return full_path
        
        # Check if relative_path contains partial directories
        for root, _, files in os.walk(self.repo_path):
            for file in files:
                candidate = os.path.join(root, file)
                candidate_rel = os.path.relpath(candidate, self.repo_path).replace("\\", "/")
                if candidate_rel.endswith(clean_path) or clean_path.endswith(candidate_rel):
                    return candidate
        return full_path

    def search_symbol(self, file_path: str, symbol_name: str) -> Optional[CodeSnippet]:
        """
        Locates a class or function definition in the target file using Python AST.
        Returns a bounded CodeSnippet (< 80 lines).
        """
        resolved_path = self._resolve_path(file_path)
        if not os.path.exists(resolved_path):
            return None

        try:
            with open(resolved_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
                lines = content.splitlines()

            tree = ast.parse(content, filename=resolved_path)

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if node.name.lower() == symbol_name.lower() or symbol_name.lower() in node.name.lower():
                        start_line = node.lineno
                        end_line = getattr(node, "end_lineno", min(start_line + 40, len(lines)))
                        
                        # Bound snippet to max 80 lines
                        if end_line - start_line + 1 > 80:
                            end_line = start_line + 79

                        snippet_lines = lines[start_line - 1 : end_line]
                        code_content = "\n".join(snippet_lines)

                        rel_file = os.path.relpath(resolved_path, self.repo_path).replace("\\", "/")
                        return CodeSnippet(
                            file_path=rel_file,
                            symbol_name=node.name,
                            start_line=start_line,
                            end_line=end_line,
                            code_content=code_content,
                        )
        except Exception:
            pass

        return None

    def extract_snippets_around_line(
        self, file_path: str, line_number: int, window: int = 35
    ) -> List[CodeSnippet]:
        """
        Extracts code surrounding a specific line number (e.g. from a stack trace),
        mapping to surrounding AST node if possible, and bounding snippet under 80 lines.
        """
        resolved_path = self._resolve_path(file_path)
        if not os.path.exists(resolved_path):
            return []

        try:
            with open(resolved_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            total_lines = len(lines)
            if total_lines == 0:
                return []

            clamped_line = max(1, min(line_number, total_lines))
            start_line = max(1, clamped_line - window)
            end_line = min(total_lines, clamped_line + window)

            if end_line - start_line + 1 > 80:
                end_line = start_line + 79

            code_content = "".join(lines[start_line - 1 : end_line])

            # Try to identify enclosing symbol name via AST
            symbol_name = None
            try:
                content = "".join(lines)
                tree = ast.parse(content, filename=resolved_path)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        s = node.lineno
                        e = getattr(node, "end_lineno", s + 100)
                        if s <= clamped_line <= e:
                            symbol_name = node.name
                            break
            except Exception:
                pass

            rel_file = os.path.relpath(resolved_path, self.repo_path).replace("\\", "/")
            return [
                CodeSnippet(
                    file_path=rel_file,
                    symbol_name=symbol_name,
                    start_line=start_line,
                    end_line=end_line,
                    code_content=code_content,
                )
            ]
        except Exception:
            return []

    def search_codebase(self, query: str, max_results: int = 5) -> List[CodeSnippet]:
        """
        Fast AST and text search across the repository for references,
        methods, functions, or variable identifiers.
        """
        results: List[CodeSnippet] = []
        pattern = re.compile(re.escape(query), re.IGNORECASE)

        for root, _, files in os.walk(self.repo_path):
            for file in files:
                if not file.endswith(".py"):
                    continue
                file_full = os.path.join(root, file)
                rel_path = os.path.relpath(file_full, self.repo_path).replace("\\", "/")

                # First try symbol lookup
                sym = self.search_symbol(file_full, query)
                if sym:
                    results.append(sym)
                    if len(results) >= max_results:
                        return results

                # Fallback line search
                try:
                    with open(file_full, "r", encoding="utf-8", errors="replace") as f:
                        lines = f.readlines()
                    for idx, line in enumerate(lines, 1):
                        if pattern.search(line):
                            s = max(1, idx - 15)
                            e = min(len(lines), idx + 20)
                            if e - s + 1 > 80:
                                e = s + 79
                            snippet = CodeSnippet(
                                file_path=rel_path,
                                symbol_name=None,
                                start_line=s,
                                end_line=e,
                                code_content="".join(lines[s - 1 : e]),
                            )
                            results.append(snippet)
                            break
                except Exception:
                    continue

                if len(results) >= max_results:
                    return results

        return results

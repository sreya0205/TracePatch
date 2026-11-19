import tempfile
import os
from incidentpilot.tools.ast_tools import ASTSearchEngine


def test_ast_search_symbol_and_bounds():
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_file = os.path.join(tmp_dir, "pricing.py")
        code = (
            "def unused_func():\n"
            "    return True\n\n"
            "def calculate_total(price, qty):\n"
            "    subtotal = price * qty\n"
            "    tax = subtotal * 0.05\n"
            "    return subtotal + tax\n"
        )
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(code)

        engine = ASTSearchEngine(repo_path=tmp_dir)
        snippet = engine.search_symbol("pricing.py", "calculate_total")

        assert snippet is not None
        assert snippet.symbol_name == "calculate_total"
        assert "subtotal = price * qty" in snippet.code_content
        assert snippet.start_line == 4
        # Verify bounded line count constraint
        assert (snippet.end_line - snippet.start_line + 1) <= 80


def test_ast_extract_around_line():
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_file = os.path.join(tmp_dir, "large_file.py")
        # Generate 150 lines
        lines = [f"x_{i} = {i}" for i in range(150)]
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        engine = ASTSearchEngine(repo_path=tmp_dir)
        snippets = engine.extract_snippets_around_line("large_file.py", line_number=50, window=35)

        assert len(snippets) == 1
        s = snippets[0]
        # Strict constraint: under 80 lines per snippet
        assert (s.end_line - s.start_line + 1) <= 80
        assert s.start_line <= 50 <= s.end_line

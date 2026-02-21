import ast

file_path = "src/integrations/lightrag_service.py"
with open(file_path, "r") as f:
    source = f.read()

tree = ast.parse(source)

funcs_to_remove = {
    "_build_extractive_fallback_plan",
    "_run_two_pass_synthesis",
    "_enforce_response_contract",
    "_sources_evidence_sufficient",
    "_validate_unknowns_section",
    "infer_intent_scope",
    "infer_scope_prefixes_from_sources",
    "apply_scope_prefixes_to_filters",
    "extract_constraint_filters",
    "merge_constraint_filters",
    "_requested_sections_from_query",
    "_required_sections_from_query",
    "_query_requires_strict_contract",
    "_query_requires_strict_citations",
    "_reference_titles_from_hits",
    "_append_references_block",
    "_is_not_found_result",
    "_has_ungrounded_citations",
    "_sanitize_synthesis_preamble",
    "_strip_standalone_not_found_lines",
    "_structured_summary_from_raw_data",
    "_format_structured_sources",
    "_format_extractive_hits",
    "_extractive_source_from_hit",
    "_structured_sources_from_raw_data",
    "_merge_extractive_hits_into_sources",
    "_normalize_and_rank_sources",
    "_filter_sources_by_filters",
}

lines_to_delete = set()
for node in ast.walk(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if node.name in funcs_to_remove:
            # node.lineno doesn't always include decorators.
            # But in ast, decorators have their own lineno.
            start_line = node.lineno
            if node.decorator_list:
                start_line = min(d.lineno for d in node.decorator_list)
            end_line = getattr(node, "end_lineno", node.lineno)
            for i in range(start_line, end_line + 1):
                lines_to_delete.add(i)

with open(file_path, "r") as f:
    lines = f.readlines()

new_lines = [line for i, line in enumerate(lines, 1) if i not in lines_to_delete]

with open(file_path, "w") as f:
    f.writelines(new_lines)

print(f"Removed {len(lines_to_delete)} lines of dead code from {file_path}.")

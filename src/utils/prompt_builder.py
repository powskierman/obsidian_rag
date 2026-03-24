import re

IMAGING_PHRASES = (
    "pet-ct",
    "pet ct",
    "pet scan",
    "ct scan",
    "mri",
    "suv",
    "deauville",
    "lymphoma",
    "car-t",
    "dlbcl",
)

FULL_ANSWER_PHRASES = (
    "review ",
    " assess",
    "assessment",
    "analy",
    "interpret",
    "what does this suggest",
    "walk me through",
    "timeline",
    "trend",
    "compare",
    "comparison",
    "difference between",
    "relate",
    "relationship",
    "how do ",
    "how does ",
)


def is_medical_imaging_query(query: str) -> bool:
    if not query:
        return False
    lowered = query.lower()
    for phrase in IMAGING_PHRASES:
        if phrase in lowered:
            return True
    return bool(re.search(r"\b(pet|ct|scan|scans)\b", lowered))


def build_provider_guardrails(provider: str) -> str:
    if provider.lower() not in ("chatgpt", "openai"):
        return ""
    return (
        "You already have authorized access to the provided notes.\n"
        "Do not ask for permissions or access. Avoid long safety disclaimers.\n"
        "If a brief safety note is warranted, add a single short line at the end."
    )


def imaging_output_template() -> str:
    return (
        "If the question concerns scans or imaging, use this format:\n"
        "## Imaging Timeline\n"
        "- [Date] — [Modality]: key findings, SUV, size, Deauville (if available)\n"
        "## Trend Summary\n"
        "- Changes in SUV and size over time\n"
        "## Interpretation\n"
        "- What the pattern suggests, with uncertainty noted\n"
        "## Questions for the Oncology Team\n"
        "- 3-6 concise, actionable questions"
    )


def prefers_full_vault_answer(query: str) -> bool:
    if not query:
        return False
    lowered = query.lower()
    if is_medical_imaging_query(query):
        return True
    return any(marker in lowered for marker in FULL_ANSWER_PHRASES)


def build_prompt_appendix(user_query: str, provider: str) -> str:
    parts = []
    guardrails = build_provider_guardrails(provider)
    if guardrails:
        parts.append(guardrails)
    if is_medical_imaging_query(user_query):
        parts.append(imaging_output_template())
    return "\n\n".join(parts)


def build_vault_system_prompt(
    context_text: str,
    user_query: str,
    provider: str,
    custom_prompt: str | None = None
) -> str:
    if custom_prompt:
        prompt = custom_prompt
    else:
        prompt = (
            "You are an AI assistant helping analyze an Obsidian knowledge base.\n\n"
            "Context from notes:\n"
            f"{context_text}\n\n"
            "Provide a thorough, accurate answer that:\n"
            "- Uses only the provided context\n"
            "- References specific information from the notes\n"
            "- Is medically accurate when discussing health topics\n"
            "- Includes technical details when relevant\n"
            "- Cites which sources you used\n"
            "- If a specific detail isn't in the notes, say \"Not found in notes\" clearly"
        )

    appendix = build_prompt_appendix(user_query, provider)
    if appendix:
        prompt = f"{prompt}\n\n{appendix}"

    return prompt

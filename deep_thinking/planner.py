import json
import re
from typing import List, Dict, Any
from .state import Step
from .source_utils import normalize_vault_path
from .supervisor import RetrievalSupervisor
from .utils.universal_client import extract_response_text

class PlannerAgent:
    def __init__(self, client):
        self.client = client
        self.model = "claude-sonnet-4-5-20250929"

    @staticmethod
    def _looks_like_step(payload: Any) -> bool:
        return isinstance(payload, dict) and any(
            key in payload for key in ("sub_question", "search_strategy", "keywords", "reasoning")
        )

    @classmethod
    def _normalize_steps_payload(cls, payload: Any) -> List[Step]:
        """
        Accept either a raw step list or an object wrapper such as {"steps": [...]}.
        Trivially normalize single-step objects and common wrapper keys before failing.
        """
        if isinstance(payload, str):
            stripped = payload.strip()
            if not stripped:
                raise ValueError("Planner payload was empty")
            return cls._normalize_steps_payload(json.loads(stripped))
        if isinstance(payload, list):
            if not all(isinstance(step, dict) for step in payload):
                raise ValueError("Planner payload list contained non-step entries")
            return payload
        if isinstance(payload, dict):
            for key in ("steps", "new_steps", "plan"):
                steps = payload.get(key)
                if isinstance(steps, list):
                    return cls._normalize_steps_payload(steps)
            if cls._looks_like_step(payload):
                return [payload]
        raise ValueError("Planner payload did not contain a step list")

    @staticmethod
    def _extract_response_text(response: Any) -> str:
        text = extract_response_text(response)
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    @classmethod
    def _json_candidates(cls, content: str) -> List[str]:
        candidates: List[str] = []
        text = str(content or "").strip()
        if text:
            candidates.append(text)

        for opener, closer in (("{", "}"), ("[", "]")):
            start = text.find(opener)
            end = text.rfind(closer)
            if start != -1 and end > start:
                candidates.append(text[start:end + 1].strip())

        deduped: List[str] = []
        seen = set()
        for candidate in candidates:
            if candidate and candidate not in seen:
                deduped.append(candidate)
                seen.add(candidate)
        return deduped

    @classmethod
    def _parse_steps_response(cls, response: Any) -> List[Step]:
        content = cls._extract_response_text(response)
        if not content:
            raise ValueError("Planner returned empty content")
        last_error: Exception | None = None
        for candidate in cls._json_candidates(content):
            try:
                return cls._normalize_steps_payload(json.loads(candidate))
            except Exception as exc:
                last_error = exc
        raise ValueError(f"Planner returned invalid JSON steps payload: {last_error}")

    @staticmethod
    def _normalize_reference(value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        if "/" in text or "\\" in text or text.endswith((".md", ".txt", ".pdf", ".py", ".json", ".yaml", ".yml")):
            return normalize_vault_path(text)
        return text

    @classmethod
    def _extract_anchor_evidence(cls, state: Dict[str, Any]) -> Dict[str, Any]:
        vault_files: List[str] = []
        entities: List[str] = []
        path_aliases: Dict[str, str] = {}
        entity_aliases: Dict[str, str] = {}
        seen_files: set[str] = set()
        seen_entities: set[str] = set()

        def add_file(value: Any) -> None:
            candidate = normalize_vault_path(value)
            if not candidate or candidate.lower().startswith(("http://", "https://")):
                return
            lowered = candidate.lower()
            if lowered in seen_files:
                return
            seen_files.add(lowered)
            vault_files.append(candidate)
            path_aliases[lowered] = candidate
            basename = candidate.rsplit("/", 1)[-1].lower()
            path_aliases.setdefault(basename, candidate)

        def add_entity(value: Any) -> None:
            candidate = str(value or "").strip()
            if not candidate or candidate.lower().startswith(("http://", "https://")):
                return
            lowered = candidate.lower()
            if lowered in seen_entities:
                return
            seen_entities.add(lowered)
            entities.append(candidate)
            entity_aliases[lowered] = candidate

        def add_entities_from_text(value: Any) -> None:
            text = str(value or "")
            for token in re.findall(r"\b(?:[A-Z][A-Za-z0-9.+-]*|[A-Za-z]+[-/][A-Za-z0-9.+-]+|[A-Za-z]+\d+(?:\.\d+)*)\b", text):
                if len(token) < 3:
                    continue
                add_entity(token)

        for doc in state.get("retrieved_documents", []) or []:
            if not isinstance(doc, dict):
                continue
            source_category = str(doc.get("source_category") or "").strip().lower()
            source = doc.get("filepath") or doc.get("source") or ""
            if source_category == "web" or str(source).startswith(("http://", "https://")):
                continue
            add_file(source)
            add_entity(doc.get("entity_id"))
            add_entity(doc.get("entity"))
            add_entity(doc.get("title"))
            add_entities_from_text(doc.get("snippet"))
            add_entities_from_text(doc.get("content"))
            for key in ("entity_ids", "entities", "keywords", "tags_normalized", "aliases_normalized"):
                values = doc.get(key) or []
                if isinstance(values, list):
                    for item in values:
                        add_entity(item)

        for past_step in state.get("past_steps", []) or []:
            if not isinstance(past_step, dict):
                continue
            step = past_step.get("step") or {}
            if isinstance(step, dict):
                add_file(step.get("file_reference"))
                for keyword in step.get("keywords", []) or []:
                    add_entity(keyword)

        return {
            "vault_files": vault_files[:12],
            "entities": entities[:20],
            "path_aliases": path_aliases,
            "entity_aliases": entity_aliases,
            "requires_references": bool(vault_files),
        }

    @classmethod
    def _infer_step_references(cls, step: Dict[str, Any], anchor_evidence: Dict[str, Any]) -> List[str]:
        path_aliases = anchor_evidence.get("path_aliases", {})
        entity_aliases = anchor_evidence.get("entity_aliases", {})
        combined_text = " ".join(
            [
                str(step.get("sub_question") or ""),
                str(step.get("reasoning") or ""),
                " ".join(str(item) for item in (step.get("keywords") or [])),
                " ".join(str(item) for item in (step.get("references") or [])),
            ]
        ).lower()

        resolved: List[str] = []
        seen: set[str] = set()

        for raw_ref in step.get("references", []) or []:
            normalized_ref = cls._normalize_reference(raw_ref)
            lowered = normalized_ref.lower()
            candidate = path_aliases.get(lowered)
            if not candidate and "/" in normalized_ref:
                candidate = path_aliases.get(normalized_ref.rsplit("/", 1)[-1].lower())
            if not candidate:
                candidate = entity_aliases.get(lowered)
            if candidate and candidate not in seen:
                resolved.append(candidate)
                seen.add(candidate)

        for alias, candidate in sorted(path_aliases.items(), key=lambda item: len(item[0]), reverse=True):
            if alias and alias in combined_text and candidate not in seen:
                resolved.append(candidate)
                seen.add(candidate)

        for alias, candidate in sorted(entity_aliases.items(), key=lambda item: len(item[0]), reverse=True):
            if len(alias) < 2:
                continue
            if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", combined_text) and candidate not in seen:
                resolved.append(candidate)
                seen.add(candidate)

        return resolved

    @classmethod
    def _apply_step_defaults(cls, step: Dict[str, Any], step_number: int) -> Step:
        step["step_number"] = step_number
        step.setdefault("sub_question", "Additional research step")
        step.setdefault("search_strategy", "hybrid")
        step.setdefault("keywords", [])
        step.setdefault("target_folders", [])
        step.setdefault("reasoning", "Filling information gaps")
        references = step.get("references") or []
        if not isinstance(references, list):
            references = [references]
        step["references"] = [cls._normalize_reference(item) for item in references if cls._normalize_reference(item)]
        return step

    @classmethod
    def validate_extended_steps(cls, steps: List[Step], state: Dict[str, Any]) -> List[Step]:
        anchor_evidence = cls._extract_anchor_evidence(state)
        require_refs = anchor_evidence["requires_references"]
        current_max = len(state.get("plan", []))
        validated: List[Step] = []

        for index, raw_step in enumerate(steps or []):
            if not isinstance(raw_step, dict):
                continue
            step = cls._apply_step_defaults(dict(raw_step), current_max + len(validated) + 1)
            inferred_refs = cls._infer_step_references(step, anchor_evidence)
            if inferred_refs:
                step["references"] = inferred_refs
            elif require_refs:
                continue
            else:
                step["references"] = []
            validated.append(step)

        return validated

    def create_plan(self, question: str, vault_context: Dict[str, Any]) -> List[Step]:
        """
        Uses LLM to break down the question into 2-5 sub-steps.
        """
        query_profile = RetrievalSupervisor.build_query_profile(question)
        if query_profile.get("prefers_vault_only_summary"):
            keywords = query_profile.get("terms") or []
            summary_focus = query_profile.get("summary_focus") or question
            if summary_focus:
                keywords = RetrievalSupervisor._query_terms(summary_focus) or keywords
            broad_keywords = list(dict.fromkeys((keywords[:5] + ["themes", "methods", "applications"])[:5]))
            return [{
                "step_number": 1,
                "sub_question": question,
                "search_strategy": "vector",
                "keywords": keywords[:5],
                "target_folders": [],
                "reasoning": "Retrieve the named vault note first to establish a faithful summary baseline."
            }, {
                "step_number": 2,
                "sub_question": f"What major themes, mechanisms, methods, and applications appear in {summary_focus} across related vault material?",
                "search_strategy": "hybrid",
                "keywords": broad_keywords,
                "target_folders": [],
                "reasoning": "Broaden the answer into a concept-level synthesis using related vault evidence without leaving the vault."
            }]

        if query_profile.get("prefers_reasoning_first"):
            keywords = query_profile.get("anchor_terms") or query_profile.get("terms") or []
            conceptual_focus = question.rstrip(" ?.")
            clarification_keywords = list(dict.fromkeys((keywords[:5] + ["definition", "conditions", "counterexample"])[:5]))
            return [{
                "step_number": 1,
                "sub_question": question,
                "search_strategy": "vector",
                "keywords": keywords[:5],
                "target_folders": [],
                "reasoning": "Start with vault notes and direct explanations before leaving the vault for this timeless conceptual question."
            }, {
                "step_number": 2,
                "sub_question": f"What definitions, conditions, edge cases, or counterexamples in my vault clarify {conceptual_focus}?",
                "search_strategy": "hybrid",
                "keywords": clarification_keywords,
                "target_folders": [],
                "reasoning": "Stress-test necessary versus sufficient conditions and resolve common misconceptions using local evidence before considering external sources."
            }]

        routing_mode = "balanced"
        if query_profile.get("needs_external_authority"):
            routing_mode = "external_authority"

        system_prompt = """
        You are an Augmented Research Planner for an Obsidian vault.
        Your goal is to create a research plan that combines LOCAL vault data with EXTERNAL web context.
        
        Vault Contents:
        - Projects and Technical setups
        - Personal journals, methodologies, and knowledge base files
        
        CRITICAL SEARCH STRATEGY RULES:
        1. Use "vector" or "hybrid" ONLY for searching the user's EXISTING notes and personal content
        2. Use "web" for:
           - Official documentation (API references, specs)
           - External tutorials and how-to guides
           - Real-world specifications or up-to-date guidelines
        3. Prefer web ONLY when the query is time-sensitive, explicitly asks for official/authoritative sources, or local context is insufficient
        4. For timeless conceptual questions, prefer first-principles reasoning plus vault evidence; do not force web search
        5. Distinguish definitions from heuristics and necessary conditions from sufficient conditions when the user asks conceptual "how/why/relate" questions
        """

        if routing_mode == "external_authority":
            routing_guidance = """
        Routing mode: external-authority.
        This query likely needs current or authoritative external verification.
        Include at least one web step early in the plan.
        """
        else:
            routing_guidance = """
        Routing mode: balanced.
        Start from vault evidence when possible and add web only if it materially improves the answer.
        """

        user_prompt = f"""
        User question: "{question}"

        Query profile:
        - needs_external_authority: {query_profile.get("needs_external_authority")}
        - requires_current_information: {query_profile.get("requires_current_information")}
        - needs_authoritative_sources: {query_profile.get("needs_authoritative_sources")}
        - prefers_reasoning_first: {query_profile.get("prefers_reasoning_first")}

        {routing_guidance}
        
        Create a research plan with 2-5 steps. For each step:
        1. Write a clear sub-question
        2. Choose search strategy: "vector" (concepts), "graph-local" (specific entities/relationships), "graph-global" (high-level themes/summaries), "web" (external/recent info), or "hybrid"
        3. List 3-5 keywords
        4. Suggest target folders if relevant (e.g. "Tech/")
        5. Explain why this step is needed
        
        CRITICAL FOR VAULT SEARCHES:
        When creating "vector" or "hybrid" steps that search the user's vault, you MUST include the KEY ENTITIES from the original question in your sub-question.
        For example:
        - If the question mentions "Nextion display", your vault search should ask "What Nextion display projects exist in my vault?" NOT just "What ESP32 projects exist?"
        - If the question mentions "FastAPI", your vault search should ask "What are my FastAPI configurations?" NOT just "What are my configurations?"
        
        Return ONLY a JSON object with this exact shape:
        {{
          "steps": [{{ ... step objects ... }}]
        }}
        Do not include markdown formatting.
        
        Example 1 (Authority-Seeking Query):
        {{
          "steps": [{{
            "step_number": 1,
            "sub_question": "What are the specs of ESP32?",
            "search_strategy": "web",
            "keywords": ["ESP32 specs", "datasheet"],
            "target_folders": [],
            "reasoning": "Need external specs"
          }}]
        }}

        Example 2 (Timeless Conceptual Query):
        {{
          "steps": [{{
            "step_number": 1,
            "sub_question": "How do asymptotes relate to derivatives in my notes?",
            "search_strategy": "vector",
            "keywords": ["asymptote", "derivative", "limit"],
            "target_folders": ["Math/"],
            "reasoning": "Start with first-principles explanations and local examples before using any external sources."
          }},
          {{
            "step_number": 2,
            "sub_question": "What definitions, conditions, and counterexamples clarify how asymptotes and derivatives are connected?",
            "search_strategy": "hybrid",
            "keywords": ["asymptote", "derivative", "counterexample", "limit"],
            "target_folders": ["Math/"],
            "reasoning": "Clarify necessary versus sufficient conditions and avoid overgeneralized claims."
          }}]
        }}

        Example 3 (Complex Vault Synthesis):
        {{
          "steps": [{{
            "step_number": 1,
            "sub_question": "What are my local Python scripts using Pandas?",
            "search_strategy": "vector",
            "keywords": ["pandas", "python", "script"],
            "target_folders": ["Tech/"],
            "reasoning": "Finding personal implementations"
          }},
          {{
            "step_number": 2,
            "sub_question": "What are the latest best practices for Pandas data wrangling?",
            "search_strategy": "web",
            "keywords": ["pandas best practices", "data wrangling patterns"],
            "target_folders": [],
            "reasoning": "Enriching personal scripts with modern industry standards"
          }}]
        }}
        """
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            response_format={"type": "json_object"}
        )
        
        try:
            return self._parse_steps_response(response)
        except Exception as e:
            print(f"Error parsing plan: {e}")
            # Fallback to a single hybrid step
            return [{
                "step_number": 1,
                "sub_question": question,
                "search_strategy": "hybrid",
                "keywords": [],
                "target_folders": [],
                "reasoning": "Fallback plan due to parsing error"
            }]

    def extend_plan(self, state: Dict[str, Any]) -> List[Step]:
        """
        Generate new steps when current plan is insufficient.
        """
        query_profile = RetrievalSupervisor.build_query_profile(state.get("original_question", ""))
        if query_profile.get("prefers_vault_only_summary"):
            return []
        anchor_evidence = self._extract_anchor_evidence(state)
        vault_files = anchor_evidence["vault_files"] or ["- none available"]
        entities = anchor_evidence["entities"] or ["- none available"]
        references_rule = (
            'All new steps must reference at least one of these files or entities. '
            'Every step must include at least one matching item in its "references" array.'
            if anchor_evidence["requires_references"]
            else 'No concrete vault files are available right now, so "references" may be an empty array if a web search is needed.'
        )
        if query_profile.get("prefers_reasoning_first"):
            enrichment_rule = (
                'This is a timeless conceptual query. Only generate a "web" search step if a concrete unanswered gap remains '
                'after local reasoning and vault retrieval. Do NOT add web steps merely because the question contains technical terms.'
            )
        elif query_profile.get("needs_external_authority"):
            enrichment_rule = (
                'If the research contains specific entities, current-version concerns, or requests for official guidance/specs, '
                'you MUST generate a "web" step when authoritative external verification is still missing.'
            )
        else:
            enrichment_rule = (
                'Use a "web" step only when external sources would materially improve correctness, completeness, or authority.'
            )
        prompt = f"""
        Original question: "{state['original_question']}"
        
        Research completed:
        {self._format_past_steps(state['past_steps'])}

        Retrieved vault files:
        {chr(10).join(f"- {item}" for item in vault_files)}

        Key entities extracted from those files:
        {chr(10).join(f"- {item}" for item in entities)}
        
        What information is still missing to answer the question?
        
        Query profile:
        - needs_external_authority: {query_profile.get("needs_external_authority")}
        - requires_current_information: {query_profile.get("requires_current_information")}
        - needs_authoritative_sources: {query_profile.get("needs_authoritative_sources")}
        - prefers_reasoning_first: {query_profile.get("prefers_reasoning_first")}

        CRITICAL: {enrichment_rule}
        
        For the "web" step:
        1. Extract the SPECIFIC terms found in the research.
        2. DO NOT use generic queries. Use the specific entities found.
        3. {references_rule}
        
        Generate 1-2 additional search steps to fill gaps.
        
        Return ONLY a JSON object with this exact shape:
        {{
          "steps": [
            {{
              "sub_question": "...",
              "search_strategy": "...",
              "keywords": ["..."],
              "target_folders": ["..."],
              "reasoning": "...",
              "references": ["Medical/Example.md", "CAR-T Therapy"]
            }}
          ]
        }}
        Each step must have:
        - sub_question: string (Specific query for web search)
        - search_strategy: "vector" | "graph-local" | "graph-global" | "hybrid" | "web"
        - keywords: array of strings (The specific terms extracted)
        - target_folders: array of strings
        - reasoning: string
        - references: array of file paths or entity IDs drawn from the evidence listed above
        """
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        try:
            new_steps = self._parse_steps_response(response)
            return self.validate_extended_steps(new_steps, state)
        except Exception as e:
            print(f"Error extending plan: {e}")
            return []

    def _format_past_steps(self, past_steps: List[Dict[str, Any]]) -> str:
        summary = ""
        for ps in past_steps:
            summary += f"Step {ps['step']['step_number']}: {ps['step']['sub_question']}\n"
            summary += f"Finding: {ps['key_findings']}\n\n"
        return summary

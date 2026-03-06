from typing import Dict, Any, List
import os
import json
import re
from datetime import datetime, timezone
from urllib.parse import urlparse
from .state import RAGState
from .planner import PlannerAgent
from .supervisor import RetrievalSupervisor
from .reflector import ReflectionAgent
from .policy import PolicyAgent
from .synthesizer import FinalAnswerGenerator
from .synthesizer import FinalAnswerGenerator
from .utils.universal_client import UniversalClient
import concurrent.futures
try:
    from src.utils.memory_manager import get_memory_manager
except ImportError:
    try:
        from utils.memory_manager import get_memory_manager
    except ImportError:
        def get_memory_manager(): return None

class DeepThinkingRAG:
    def __init__(
        self, 
        provider: str = "claude",
        api_key: str = None,
        model: str = None,
        anthropic_client=None, # Backwards compatibility
        vector_service_url: str = "http://localhost:8000",
        graph_service_url: str = "http://localhost:8003",
        enable_reranking: bool = True
    ):
        provider_name = provider if isinstance(provider, str) else "claude"

        # Legacy signature support: DeepThinkingRAG(client, vector_url, graph_url)
        if anthropic_client is None and not isinstance(provider, str):
            anthropic_client = provider
            if isinstance(api_key, str) and api_key.startswith("http"):
                vector_service_url = api_key
                api_key = None
            if isinstance(model, str) and model.startswith("http"):
                graph_service_url = model
                model = None

        default_model = model
        if not default_model:
            if provider_name == "openrouter":
                default_model = os.getenv("OPENROUTER_MODEL", "openrouter/auto")
            elif provider_name == "ollama":
                default_model = os.getenv("OLLAMA_MODEL", "mistral")
            elif provider_name == "claude":
                default_model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
            elif provider_name == "gemini":
                default_model = os.getenv("GEMINI_MODEL", "gemini-3-pro-preview")
            elif provider_name in ("chatgpt", "openai"):
                default_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            elif provider_name == "mlx":
                default_model = os.getenv("MLX_MODEL") or os.getenv("LLM_MODEL_PATH") or "LiquidAI/LFM2-24B-A2B"
            elif provider_name == "perplexity":
                default_model = os.getenv("PERPLEXITY_MODEL", "llama-3.1-sonar-large-128k-online")

        # Initialize Universal Client or use provided client directly.
        if anthropic_client is not None:
            self.client = anthropic_client
        else:
            self.client = UniversalClient(provider=provider_name, api_key=api_key)
            
        self.planner = PlannerAgent(self.client)
        self.supervisor = RetrievalSupervisor(
            vector_service_url, 
            graph_service_url,
            enable_reranking=enable_reranking,
            llm_provider=provider_name,
            llm_model=default_model,
        )
        self.reflector = ReflectionAgent(self.client)
        self.policy = PolicyAgent(self.client)
        self.synthesizer = FinalAnswerGenerator(self.client)

        if default_model:
            self.planner.model = default_model
            self.reflector.model = default_model
            self.policy.model = default_model
            self.synthesizer.model = default_model

    def _should_force_vault_step(self, question: str) -> bool:
        lowered = question.lower()
        vault_markers = [
            "my ",
            "mine",
            "vault",
            "notes",
            "note ",
            "scan",
            "pet",
            "ct",
            "mri",
            "report",
            "pdf",
            "log"
        ]
        return any(marker in lowered for marker in vault_markers)

    def _should_force_web_step(self, question: str) -> bool:
        lowered = question.lower()
        comparison_markers = [" vs ", " versus ", "compare ", "comparison ", "difference between", "differences between"]
        technical_markers = [
            "esp32",
            "datasheet",
            "spec",
            "specs",
            "microcontroller",
            "api",
            "framework",
            "library",
            "chip",
            "module",
            "hardware",
            "benchmark",
            "protocol",
            "python",
            "javascript",
            "react",
            "next.js",
            "nextjs",
        ]
        return any(marker in lowered for marker in comparison_markers) and any(
            marker in lowered for marker in technical_markers
        )

    @staticmethod
    def _provider_limits(provider: str) -> tuple[int, int, int, int]:
        provider = (provider or "").lower()
        if provider == "mlx":
            return (
                int(os.getenv("DEEP_THINKING_MLX_BUFFER_DOCS_PER_STEP", "2")),
                int(os.getenv("DEEP_THINKING_MLX_BUFFER_DOC_CHARS", "1500")),
                int(os.getenv("DEEP_THINKING_MLX_BUFFER_TOTAL_CHARS", "6000")),
                int(os.getenv("DEEP_THINKING_MLX_ACCUMULATED_CONTEXT_CHARS", "4000")),
            )
        return (
            int(os.getenv("DEEP_THINKING_BUFFER_DOCS_PER_STEP", "3")),
            int(os.getenv("DEEP_THINKING_BUFFER_DOC_CHARS", "6000")),
            int(os.getenv("DEEP_THINKING_BUFFER_TOTAL_CHARS", "24000")),
            int(os.getenv("DEEP_THINKING_ACCUMULATED_CONTEXT_CHARS", "12000")),
        )

    @staticmethod
    def _truncate_text(value: Any, limit: int) -> str:
        text = str(value or "")
        if len(text) <= limit:
            return text
        return text[: max(limit - 16, 0)].rstrip() + "\n... [truncated]"

    @staticmethod
    def _is_web_url(value: Any) -> bool:
        if not isinstance(value, str):
            return False
        parsed = urlparse(value.strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    def _has_web_documents(self, documents: List[Dict[str, Any]]) -> bool:
        for doc in documents or []:
            if not isinstance(doc, dict):
                continue
            category = str(doc.get("source_category") or "").strip().lower()
            if category == "web":
                return True
            for field in ("filepath", "url", "source", "filename"):
                value = doc.get(field)
                if isinstance(value, str) and self._is_web_url(value):
                    return True
        return False

    @staticmethod
    def _has_web_sources(sources: List[Dict[str, Any]]) -> bool:
        for source in sources or []:
            if not isinstance(source, dict):
                continue
            if str(source.get("source_category") or "").strip().lower() == "web":
                return True
            candidate = str(source.get("filepath") or source.get("filename") or "").strip()
            if candidate.startswith("http://") or candidate.startswith("https://"):
                return True
        return False

    @staticmethod
    def _clean_snippet(value: Any, limit: int = 280) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        compact = re.sub(r"\s+", " ", text)
        if len(compact) <= limit:
            return compact
        return compact[: limit - 3].rstrip() + "..."

    @staticmethod
    def _citation_targets(citations: List[Any]) -> set[str]:
        targets: set[str] = set()
        for citation in citations or []:
            if not isinstance(citation, str):
                continue
            obsidian_match = re.search(r"\[\[([^\]]+)\]\]", citation)
            if obsidian_match:
                targets.add(obsidian_match.group(1).strip().lower())
            md_match = re.search(r"\[[^\]]+\]\(([^)]+)\)", citation)
            if md_match:
                targets.add(md_match.group(1).strip().lower())
            if citation.startswith("http://") or citation.startswith("https://"):
                targets.add(citation.strip().lower())
        return targets

    def _build_structured_sources(
        self,
        documents: List[Dict[str, Any]],
        citations: List[Any],
        max_sources: int = 12,
    ) -> List[Dict[str, Any]]:
        citation_targets = self._citation_targets(citations)
        structured: List[Dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        source_limit = max(1, int(max_sources or 12))

        for doc in documents:
            if not isinstance(doc, dict):
                continue
            if doc.get("is_summary"):
                continue

            filepath = str(doc.get("filepath") or doc.get("url") or doc.get("source") or "").strip()
            filename = str(doc.get("filename") or doc.get("title") or "").strip()
            snippet = self._clean_snippet(doc.get("snippet") or doc.get("content") or "")

            if not filepath and not filename:
                continue
            if filepath in {"Graph Synthesis Summary", "LightRAG Knowledge Graph"}:
                continue

            source_category = str(doc.get("source_category") or "").strip().lower()
            if source_category not in {"vault", "web"}:
                source_category = "web" if self._is_web_url(filepath) else "vault"

            if not filename:
                if source_category == "web" and filepath:
                    filename = filepath
                else:
                    filename = os.path.basename(filepath) or filepath or "Unknown"

            raw_relevance = doc.get("relevance", doc.get("score", 0.5))
            try:
                relevance = float(raw_relevance)
            except (TypeError, ValueError):
                relevance = 0.5
            if relevance <= 1.0:
                relevance *= 100.0
            relevance = max(1.0, min(100.0, relevance))

            dedupe_key = (source_category, (filepath or filename).lower())
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            target = (filepath or filename).lower()
            is_cited = target in citation_targets or filename.lower() in citation_targets

            structured.append({
                "filename": filename,
                "filepath": filepath or filename,
                "relevance": round(relevance, 1),
                "snippet": snippet or ("Retrieved from the web." if source_category == "web" else "Retrieved from the vault."),
                "source_type": doc.get("source_type") or ("web-result" if source_category == "web" else "direct-excerpt"),
                "source_category": source_category,
                "_is_cited": is_cited,
            })

        structured.sort(
            key=lambda item: (
                0 if item.get("_is_cited") else 1,
                0 if item.get("source_category") == "vault" else 1,
                -float(item.get("relevance", 0.0)),
                item.get("filename", "").lower(),
            )
        )

        web_items = [item for item in structured if item.get("source_category") == "web"]
        vault_items = [item for item in structured if item.get("source_category") == "vault"]

        if web_items and vault_items:
            half = source_limit // 2
            target_vault = max(1, min(len(vault_items), half + (source_limit % 2)))
            target_web = max(1, min(len(web_items), half))

            selected = vault_items[:target_vault] + web_items[:target_web]

            if len(selected) < source_limit:
                selected_keys = {
                    (
                        str(item.get("source_category", "")),
                        str(item.get("filepath") or item.get("filename") or "").lower(),
                    )
                    for item in selected
                }
                overflow = vault_items[target_vault:] + web_items[target_web:]
                for item in overflow:
                    if len(selected) >= source_limit:
                        break
                    key = (
                        str(item.get("source_category", "")),
                        str(item.get("filepath") or item.get("filename") or "").lower(),
                    )
                    if key in selected_keys:
                        continue
                    selected.append(item)
                    selected_keys.add(key)

            structured = selected
        else:
            structured = structured[:source_limit]

        for item in structured:
            item.pop("_is_cited", None)

        return structured[:source_limit]

        
    def query(
        self,
        question: str,
        max_iterations: int = 7,
        status_callback=None,
        max_sources: int = 12,
    ) -> Dict[str, Any]:
        """
        Main reasoning loop.
        status_callback: Optional function that accepts (status_msg, details_dict)
        """
        log_path = os.getenv("DEEP_THINKING_LOG_PATH", "/tmp/deep_thinking.log")
        log_file = None
        try:
            log_dir = os.path.dirname(log_path)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            log_file = open(log_path, "a", encoding="utf-8")
        except Exception:
            log_file = None

        provider = getattr(self.client, "provider", "").lower()
        buffer_docs_per_step, buffer_doc_chars, buffer_total_chars, accumulated_context_chars = self._provider_limits(provider)

        def log_line(msg: str, details: dict | None) -> None:
            if not log_file:
                return
            payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": msg
            }
            if details is not None:
                payload["details"] = details
            log_file.write(json.dumps(payload) + "\n")
            log_file.flush()

        def update_status(msg, details=None):
            if status_callback:
                status_callback(msg, details)
            else:
                print(f"{msg} {details if details else ''}")
            log_line(msg, details)

        # Initialize state
        state: RAGState = {
            "original_question": question,
            "user_context": {},
            "plan": [],
            "current_step_index": 0,
            "past_steps": [],
            "accumulated_context": "",
            "retrieved_documents": [],
            "iteration_count": 0,
            "max_iterations": max_iterations,
            "should_continue": True,
            "final_answer": "",
            "citations": [],
            "raw_context_buffer": [],  # New: Store raw text snippets
            "warnings": [],
        }
        
        # Step 0: Get User Context from mem0
        try:
            mem_manager = get_memory_manager()
            if mem_manager:
                update_status("🧠 Retrieving user memories...")
                memories = mem_manager.search_memory(question, limit=5)
                if memories:
                    state["user_context"]["memories"] = memories
                    update_status("   Context loaded", {"length": len(memories)})
        except Exception as e:
            update_status(f"⚠️ Memory retrieval failed: {e}")
        
        # Step 1: Create plan
        update_status("🤔 Planning research strategy...")
        state["plan"] = self.planner.create_plan(question, state["user_context"])
        update_status("📋 Plan created", {"plan": state["plan"]})

        has_vault_step = any(
            step.get("search_strategy") in ("vector", "hybrid") for step in state["plan"]
        )
        require_vault_step = os.getenv("DEEP_THINKING_REQUIRE_VAULT_STEP", "true").strip().lower() not in {
            "0",
            "false",
            "no",
            "off",
        }
        if not has_vault_step and (require_vault_step or self._should_force_vault_step(question)):
            state["plan"] = [{
                "step_number": 1,
                "sub_question": question,
                "search_strategy": "vector",
                "keywords": [],
                "target_folders": [],
                "reasoning": "Ensure vault retrieval for personal content."
            }] + state["plan"]
            for idx, step in enumerate(state["plan"], start=1):
                step["step_number"] = idx

        has_web_step = any(step.get("search_strategy") == "web" for step in state["plan"])
        if not has_web_step and self._should_force_web_step(question):
            state["plan"].append({
                "step_number": len(state["plan"]) + 1,
                "sub_question": question,
                "search_strategy": "web",
                "keywords": [],
                "target_folders": [],
                "reasoning": "Ensure external verification for technical comparison queries."
            })

        
        # Step 2: Execute plan with reflection loop
        while state["should_continue"] and state["iteration_count"] < max_iterations:
            state["iteration_count"] += 1
            
            # Get current step
            if state["current_step_index"] >= len(state["plan"]):
                # Plan exhausted, check policy
                pass
            else:
                steps_to_run = state["plan"][state["current_step_index"]:]
                
                # Execute step and reflection
                def run_and_reflect(step):
                    update_status(f"👣 Step {step['step_number']}: {step['sub_question']}")
                    docs = self.supervisor.execute_step(step, state, trace_callback=update_status)
                    update_status(f"   Found {len(docs)} documents for Step {step['step_number']}.")
                    past_step = self.reflector.reflect(step, docs, state)
                    update_status(f"   Insight for Step {step['step_number']}: {past_step['key_findings']}")
                    return step, docs, past_step

                # Use ThreadPoolExecutor to run independent planned steps in parallel
                with concurrent.futures.ThreadPoolExecutor(max_workers=len(steps_to_run)) as executor:
                    futures = [executor.submit(run_and_reflect, step) for step in steps_to_run]
                    results = [f.result() for f in futures] # keep order

                for step, docs, past_step in results:
                    state["retrieved_documents"].extend(docs)
                    
                    for doc in docs[:buffer_docs_per_step]:
                        state["raw_context_buffer"].append({
                            "source": doc.get("source", "Unknown"),
                            "content": self._truncate_text(doc.get("content", ""), buffer_doc_chars),
                            "step": step["step_number"]
                        })

                    total_buffer_chars = sum(len(str(item.get("content", ""))) for item in state["raw_context_buffer"])
                    while state["raw_context_buffer"] and total_buffer_chars > buffer_total_chars:
                        removed = state["raw_context_buffer"].pop(0)
                        total_buffer_chars -= len(str(removed.get("content", "")))
                        
                    state["past_steps"].append(past_step)
                    state["accumulated_context"] += f"\n\nStep {step['step_number']}: {past_step['key_findings']}"
                    
                    # Cap context to prevent token bloat (Hierarchical Memory)
                    limit = int(accumulated_context_chars * 0.7)
                    if len(state["accumulated_context"]) > limit:
                        update_status("🗜️ Compressing earlier context (Hierarchical Memory)...")
                        
                        split_idx = len(state["accumulated_context"]) // 2
                        next_step_idx = state["accumulated_context"].find("\n\nStep ", split_idx)
                        if next_step_idx == -1:
                            next_step_idx = split_idx
                            
                        early_context = state["accumulated_context"][:next_step_idx].strip()
                        recent_context = state["accumulated_context"][next_step_idx:]
                        
                        if early_context:
                            summary = self.reflector.compress_context(early_context)
                            state["accumulated_context"] = summary + "\n" + recent_context
                            
                        # Hard cap just in case it still exceeds the absolute limit
                        if len(state["accumulated_context"]) > accumulated_context_chars:
                            state["accumulated_context"] = "... [earlier steps truncated] ..." + state["accumulated_context"][-accumulated_context_chars:]
                
                state["current_step_index"] += len(steps_to_run)
            
            # Check if we should continue
            # Plan complete or empty - ask policy if we have enough
            if state["current_step_index"] >= len(state["plan"]):
                decision = self.policy.decide(state)
                update_status(f"⚖️ Policy Decision: {decision}")
                
                if decision == "FINISH":
                    state["should_continue"] = False
                elif decision == "REVISE_PLAN":
                    # Generate additional steps
                    update_status("🔄 Revising plan...")
                    new_steps = self.planner.extend_plan(state)
                    state["plan"].extend(new_steps)
                elif decision == "CONTINUE":
                    # If policy says continue but no steps left, force finish or extend?
                    # If no steps left, we MUST extend or finish.
                    if state["current_step_index"] >= len(state["plan"]):
                         update_status("   No steps left, forcing plan extension...")
                         new_steps = self.planner.extend_plan(state)
                         if not new_steps:
                             update_status("   Could not extend plan, finishing.")
                             state["should_continue"] = False
                         else:
                             state["plan"].extend(new_steps)

        # Safety: For technical comparison/spec queries, ensure at least one successful web retrieval.
        if self._should_force_web_step(question) and not self._has_web_documents(state["retrieved_documents"]):
            update_status("🌐 No web evidence retrieved; running fallback web search...")
            fallback_step = {
                "step_number": len(state["plan"]) + 1,
                "sub_question": question,
                "search_strategy": "web",
                "keywords": [],
                "target_folders": [],
                "reasoning": "Fallback web retrieval to ensure external grounding."
            }
            web_docs = self.supervisor.execute_step(fallback_step, state, trace_callback=update_status)
            if web_docs:
                state["retrieved_documents"].extend(web_docs)
                for doc in web_docs[:buffer_docs_per_step]:
                    state["raw_context_buffer"].append({
                        "source": doc.get("source", "Unknown"),
                        "content": self._truncate_text(doc.get("content", ""), buffer_doc_chars),
                        "step": fallback_step["step_number"],
                    })
                total_buffer_chars = sum(len(str(item.get("content", ""))) for item in state["raw_context_buffer"])
                while state["raw_context_buffer"] and total_buffer_chars > buffer_total_chars:
                    removed = state["raw_context_buffer"].pop(0)
                    total_buffer_chars -= len(str(removed.get("content", "")))
                state["accumulated_context"] += "\n\nFallback web retrieval: Added external references."
                if len(state["accumulated_context"]) > accumulated_context_chars:
                    state["accumulated_context"] = "... [earlier steps truncated] ..." + state["accumulated_context"][-accumulated_context_chars:]
                update_status("   Fallback web retrieval complete", {"documents": len(web_docs)})
            else:
                warning_msg = "Fallback web retrieval returned no documents."
                warnings = state.setdefault("warnings", [])
                if warning_msg not in warnings:
                    warnings.append(warning_msg)
                update_status("   Fallback web retrieval found no documents.")
        
        # Step 3: Generate final answer
        update_status("📝 Synthesizing final answer...")
        synthesis_result = self.synthesizer.generate(state)
        if isinstance(synthesis_result, (tuple, list)):
            answer = synthesis_result[0] if len(synthesis_result) > 0 else ""
            citations = synthesis_result[1] if len(synthesis_result) > 1 else []
            confidence_score = synthesis_result[2] if len(synthesis_result) > 2 else 0.0
            confidence_justification = synthesis_result[3] if len(synthesis_result) > 3 else ""
            synthesis_result = {
                "answer": answer,
                "citations": citations,
                "confidence_score": confidence_score,
                "confidence_justification": confidence_justification
            }
        
        state["final_answer"] = synthesis_result["answer"]
        state["citations"] = synthesis_result["citations"]
        state["confidence_score"] = synthesis_result["confidence_score"]
        state["confidence_justification"] = synthesis_result["confidence_justification"]
        
        structured_sources = self._build_structured_sources(
            state["retrieved_documents"],
            state["citations"],
            max_sources=max_sources,
        )

        # Final guardrail: ensure a visible web source exists for web-required technical comparisons.
        # This catches edge cases where the planner/retrieval path succeeded partially but no web source
        # survives into the final source list.
        if self._should_force_web_step(question) and not self._has_web_sources(structured_sources):
            update_status("🌐 Final source check found no web items; running last web retrieval pass...")
            final_web_docs = self.supervisor.execute_step(
                {
                    "step_number": len(state["plan"]) + 1,
                    "sub_question": question,
                    "search_strategy": "web",
                    "keywords": [],
                    "target_folders": [],
                    "reasoning": "Final source-level safeguard for technical comparison queries.",
                },
                state,
                trace_callback=update_status,
            )
            if final_web_docs:
                state["retrieved_documents"].extend(final_web_docs)
                structured_sources = self._build_structured_sources(
                    state["retrieved_documents"],
                    state["citations"],
                    max_sources=max_sources,
                )
                update_status(
                    "   Final web retrieval pass attached sources",
                    {"documents": len(final_web_docs)},
                )
            else:
                warning_msg = (
                    "Web retrieval attempted multiple times but returned no usable results "
                    "(check Tavily/API/network and query constraints)."
                )
                warnings = state.setdefault("warnings", [])
                if warning_msg not in warnings:
                    warnings.append(warning_msg)
                update_status("   Final web retrieval pass returned no documents.")

        output = {
            "answer": state["final_answer"],
            "citations": state["citations"],
            "sources": structured_sources,
            "confidence_score": state["confidence_score"],
            "confidence_justification": state["confidence_justification"],
            "warnings": state.get("warnings", []),
            "research_steps": state["past_steps"],
            "total_documents": len(state["retrieved_documents"])
        }
        log_line("✅ Synthesis complete", {"answer_length": len(state["final_answer"] or "")})
        if log_file:
            log_file.close()
        return output

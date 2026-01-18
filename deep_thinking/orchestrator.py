from typing import Dict, Any, List
import os
import json
from datetime import datetime, timezone
from .state import RAGState
from .planner import PlannerAgent
from .supervisor import RetrievalSupervisor
from .reflector import ReflectionAgent
from .policy import PolicyAgent
from .synthesizer import FinalAnswerGenerator
from .utils.universal_client import UniversalClient
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

        # Initialize Universal Client or use provided client directly.
        if anthropic_client is not None:
            self.client = anthropic_client
        else:
            self.client = UniversalClient(provider=provider_name, api_key=api_key)
            
        self.planner = PlannerAgent(self.client)
        self.supervisor = RetrievalSupervisor(
            vector_service_url, 
            graph_service_url,
            enable_reranking=enable_reranking
        )
        self.reflector = ReflectionAgent(self.client)
        self.policy = PolicyAgent(self.client)
        self.synthesizer = FinalAnswerGenerator(self.client)

        default_model = model
        if not default_model:
            if provider_name == "openrouter":
                default_model = os.getenv("OPENROUTER_MODEL", "openrouter/auto")
            elif provider_name == "claude":
                default_model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
            elif provider_name == "gemini":
                default_model = os.getenv("GEMINI_MODEL", "gemini-3-pro-preview")
            elif provider_name in ("chatgpt", "openai"):
                default_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

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

        
    def query(self, question: str, max_iterations: int = 7, status_callback=None) -> Dict[str, Any]:
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
            "raw_context_buffer": []  # New: Store raw text snippets
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
        if not has_vault_step and self._should_force_vault_step(question):
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

        
        # Step 2: Execute plan with reflection loop
        while state["should_continue"] and state["iteration_count"] < max_iterations:
            state["iteration_count"] += 1
            
            # Get current step
            if state["current_step_index"] >= len(state["plan"]):
                # Plan exhausted, check policy
                pass
            else:
                current_step = state["plan"][state["current_step_index"]]
                update_status(f"👣 Step {current_step['step_number']}: {current_step['sub_question']}")
                
                # Execute retrieval
                documents = self.supervisor.execute_step(
                    current_step,
                    state,
                    trace_callback=update_status
                )
                state["retrieved_documents"].extend(documents)
                update_status(f"   Found {len(documents)} documents.")
                
                # Update Raw Context Buffer (Keep top 3 docs per step full text)
                for doc in documents[:3]:
                    state["raw_context_buffer"].append({
                        "source": doc.get("source", "Unknown"),
                        "content": doc.get("content", ""),
                        "step": current_step["step_number"]
                    })
                
                # Reflect on findings
                past_step = self.reflector.reflect(current_step, documents, state)
                state["past_steps"].append(past_step)
                update_status(f"   Insight: {past_step['key_findings']}")
                
                # Update accumulated context
                state["accumulated_context"] += f"\n\nStep {current_step['step_number']}: {past_step['key_findings']}"
                
                # Move to next step
                state["current_step_index"] += 1
            
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
        
        output = {
            "answer": state["final_answer"],
            "citations": state["citations"],
            "confidence_score": state["confidence_score"],
            "confidence_justification": state["confidence_justification"],
            "research_steps": state["past_steps"],
            "total_documents": len(state["retrieved_documents"])
        }
        log_line("✅ Synthesis complete", {"answer_length": len(state["final_answer"] or "")})
        if log_file:
            log_file.close()
        return output

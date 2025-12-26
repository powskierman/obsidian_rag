from typing import Dict, Any, List
from .state import RAGState
from .planner import PlannerAgent
from .supervisor import RetrievalSupervisor
from .reflector import ReflectionAgent
from .policy import PolicyAgent
from .synthesizer import FinalAnswerGenerator

class DeepThinkingRAG:
    def __init__(
        self, 
        client, 
        vector_service_url: str = "http://localhost:8000",
        graph_service_url: str = "http://localhost:8002",
        enable_reranking: bool = True,
        model: str = "moonshotai/kimi-k2-0905"
    ):
        self.planner = PlannerAgent(client, model=model)
        self.supervisor = RetrievalSupervisor(
            vector_service_url, 
            graph_service_url,
            enable_reranking=enable_reranking
        )
        self.reflector = ReflectionAgent(client, model=model)
        self.policy = PolicyAgent(client, model=model)
        self.synthesizer = FinalAnswerGenerator(client, model=model)
        
    def query(self, question: str, max_iterations: int = 7, status_callback=None) -> Dict[str, Any]:
        """
        Main reasoning loop.
        status_callback: Optional function that accepts (status_msg, details_dict)
        """
        def update_status(msg, details=None):
            if status_callback:
                status_callback(msg, details)
            else:
                print(f"{msg} {details if details else ''}")

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
            "citations": []
        }
        
        # Step 1: Create plan
        update_status("🤔 Planning research strategy...")
        state["plan"] = self.planner.create_plan(question, state["user_context"])
        update_status("📋 Plan created", {"plan": state["plan"]})
        
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
                documents = self.supervisor.execute_step(current_step, state)
                state["retrieved_documents"].extend(documents)
                update_status(f"   Found {len(documents)} documents.")
                
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
        
        state["final_answer"] = synthesis_result["answer"]
        state["citations"] = synthesis_result["citations"]
        state["confidence_score"] = synthesis_result["confidence_score"]
        state["confidence_justification"] = synthesis_result["confidence_justification"]
        
        return {
            "answer": state["final_answer"],
            "citations": state["citations"],
            "confidence_score": state["confidence_score"],
            "confidence_justification": state["confidence_justification"],
            "research_steps": state["past_steps"],
            "total_documents": len(state["retrieved_documents"])
        }

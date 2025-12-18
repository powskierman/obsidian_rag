from typing import TypedDict, List, Literal, Optional, Dict, Any

class Step(TypedDict):
    step_number: int
    sub_question: str
    search_strategy: Literal["vector", "graph", "hybrid", "web"]
    keywords: List[str]
    target_folders: List[str]
    reasoning: str

class PastStep(TypedDict):
    step: Step
    documents_found: int
    key_findings: str
    confidence: float

class RAGState(TypedDict):
    # Input
    original_question: str
    user_context: Dict[str, Any]
    
    # Planning
    plan: List[Step]
    current_step_index: int
    
    # Execution
    past_steps: List[PastStep]
    accumulated_context: str
    retrieved_documents: List[Dict[str, Any]]
    
    # Control
    iteration_count: int
    max_iterations: int
    should_continue: bool
    
    # Output
    final_answer: str
    citations: List[str]

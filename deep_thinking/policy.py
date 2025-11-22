import json
from typing import Literal
from .state import RAGState

class PolicyAgent:
    def __init__(self, anthropic_client):
        self.client = anthropic_client
        self.model = "claude-sonnet-4-5"

    def decide(self, state: RAGState) -> Literal["CONTINUE", "FINISH", "REVISE_PLAN"]:
        """
        Evaluate progress and decide next action.
        """
        prompt = f"""
        Original Question: "{state['original_question']}"
        
        Research completed so far:
        {self._format_research_summary(state['past_steps'])}
        
        Remaining planned steps: {len(state['plan']) - state['current_step_index']}
        Iterations used: {state['iteration_count']} / {state['max_iterations']}
        
        Decision options:
        - CONTINUE: Execute next planned step
        - FINISH: Sufficient information gathered, generate answer
        - REVISE_PLAN: Current plan won't work, need different approach
        
        Return ONLY a JSON object: {{"decision": "CONTINUE|FINISH|REVISE_PLAN", "reasoning": "..."}}
        """
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        
        try:
            content = response.content[0].text.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            decision_data = json.loads(content)
            decision = decision_data.get("decision", "CONTINUE")
            
            # Validate decision
            if decision not in ["CONTINUE", "FINISH", "REVISE_PLAN"]:
                return "CONTINUE"
                
            return decision
        except Exception as e:
            print(f"Error parsing policy decision: {e}")
            return "CONTINUE"

    def _format_research_summary(self, past_steps):
        summary = ""
        for ps in past_steps:
            summary += f"- Step {ps['step']['step_number']}: {ps['key_findings']} (Conf: {ps['confidence']})\n"
        return summary

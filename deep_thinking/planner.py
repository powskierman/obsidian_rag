import json
from typing import List, Dict, Any
from .state import Step

class PlannerAgent:
    def __init__(self, anthropic_client):
        self.client = anthropic_client
        self.model = "claude-sonnet-4-5" # Using the correct model ID

    def create_plan(self, question: str, vault_context: Dict[str, Any]) -> List[Step]:
        """
        Uses Claude to break down the question into 2-5 sub-steps.
        """
        prompt = f"""
        You are a research planner for an Obsidian vault containing:
        - Medical notes (folders: Medical/Scans/, Medical/Treatments/)
        - Technical projects (folders: Tech/ESP32/, Tech/HomeAssistant/)
        - Personal logs (Daily Notes)
        
        User question: "{question}"
        
        Create a research plan with 2-5 steps. For each step:
        1. Write a clear sub-question
        2. Choose search strategy: "vector" (concepts), "graph" (entities/relationships), "hybrid"
        3. List 3-5 keywords
        4. Suggest target folders if relevant (e.g. "Medical/", "Tech/")
        5. Explain why this step is needed
        
        Return ONLY a JSON array of steps. Do not include markdown formatting.
        Example format:
        [
          {{
            "step_number": 1,
            "sub_question": "...",
            "search_strategy": "vector",
            "keywords": ["..."],
            "target_folders": ["..."],
            "reasoning": "..."
          }}
        ]
        """
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        try:
            content = response.content[0].text.strip()
            # Remove markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            plan_data = json.loads(content)
            return plan_data
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
        prompt = f"""
        Original question: "{state['original_question']}"
        
        Research completed:
        {self._format_past_steps(state['past_steps'])}
        
        What information is still missing to answer the question?
        Generate 1-2 additional search steps to fill gaps.
        
        Return ONLY a JSON array of new steps. Each step must have:
        - sub_question: string
        - search_strategy: "vector" | "graph" | "hybrid"
        - keywords: array of strings
        - target_folders: array of strings
        - reasoning: string
        """
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        try:
            content = response.content[0].text.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            new_steps = json.loads(content)
            
            # Assign step numbers continuing from existing plan
            current_max = len(state["plan"])
            for i, step in enumerate(new_steps):
                step["step_number"] = current_max + i + 1
                
                # Ensure all required fields are present
                if "sub_question" not in step:
                    step["sub_question"] = "Additional research step"
                if "search_strategy" not in step:
                    step["search_strategy"] = "hybrid"
                if "keywords" not in step:
                    step["keywords"] = []
                if "target_folders" not in step:
                    step["target_folders"] = []
                if "reasoning" not in step:
                    step["reasoning"] = "Filling information gaps"
                
            return new_steps
        except Exception as e:
            print(f"Error extending plan: {e}")
            return []

    def _format_past_steps(self, past_steps: List[Dict[str, Any]]) -> str:
        summary = ""
        for ps in past_steps:
            summary += f"Step {ps['step']['step_number']}: {ps['step']['sub_question']}\n"
            summary += f"Finding: {ps['key_findings']}\n\n"
        return summary

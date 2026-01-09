import json
from typing import List, Dict, Any
from .state import Step

class PlannerAgent:
    def __init__(self, client):
        self.client = client
        self.model = "claude-sonnet-4-5-20250929"

    def create_plan(self, question: str, vault_context: Dict[str, Any]) -> List[Step]:
        """
        Uses LLM to break down the question into 2-5 sub-steps.
        """
        system_prompt = """
        You are an Augmented Research Planner for an Obsidian vault.
        Your goal is to create a research plan that combines LOCAL vault data with EXTERNAL web context.
        
        Vault Contents:
        - Medical notes (folders: Medical/Lymphoma/, Medical/Scans/, Medical/Treatments/)
        - Technical projects (folders: Tech/ESP32/, Tech/HomeAssistant/)
        - Personal logs (Daily Notes)
        
        CRITICAL SEARCH STRATEGY RULES:
        1. Use "vector" or "hybrid" ONLY for searching the user's EXISTING notes and personal content
        2. Use "web" for:
           - Official documentation (ESPHome docs, product specs, API references)
           - Hardware specifications and datasheets
           - Wiring diagrams and pin configurations  
           - Latest software versions or updates
           - Medical treatment guidelines or drug information
           - Any "how-to" or tutorial content that isn't in the vault
           - Product comparisons or reviews
        
        3. If in doubt, prefer "web" over "vector" - it's better to get fresh, authoritative information
        4. For technical queries, at MINIMUM have 2 web search steps
        5. For medical queries, ALWAYS include web search for treatment protocols/side effects
        """

        user_prompt = f"""
        User question: "{question}"
        
        Create a research plan with 2-5 steps. For each step:
        1. Write a clear sub-question
        2. Choose search strategy: "vector" (concepts), "graph" (entities/relationships), "web" (external/recent info), or "hybrid"
        3. List 3-5 keywords
        4. Suggest target folders if relevant (e.g. "Medical/", "Tech/")
        5. Explain why this step is needed
        
        CRITICAL FOR VAULT SEARCHES:
        When creating "vector" or "hybrid" steps that search the user's vault, you MUST include the KEY ENTITIES from the original question in your sub-question.
        For example:
        - If the question mentions "Nextion display", your vault search should ask "What Nextion display projects exist in my vault?" NOT just "What ESP32 projects exist?"
        - If the question mentions "R-CHOP", your vault search should ask "What are my R-CHOP treatment notes?" NOT just "What are my treatment notes?"
        
        Return ONLY a JSON array of steps. Do not include markdown formatting.
        
        Example 1 (Technical Query):
        [
          {{
            "step_number": 1,
            "sub_question": "What are the specs of ESP32?",
            "search_strategy": "web",
            "keywords": ["ESP32 specs", "datasheet"],
            "target_folders": [],
            "reasoning": "Need external specs"
          }}
        ]

        Example 2 (Medical Journey - ENRICHMENT REQUIRED):
        [
          {{
            "step_number": 1,
            "sub_question": "Extract timeline from my lymphoma notes",
            "search_strategy": "vector",
            "keywords": ["lymphoma", "timeline", "diagnosis"],
            "target_folders": ["Medical/"],
            "reasoning": "Building timeline from vault"
          }},
          {{
            "step_number": 2,
            "sub_question": "What are the standard treatments for Diffuse Large B-Cell Lymphoma?",
            "search_strategy": "web",
            "keywords": ["DLBCL standard treatment", "R-CHOP side effects"],
            "target_folders": [],
            "reasoning": "Enriching personal notes with standard medical context"
          }}
        ]
        """
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        
        try:
            # UniversalClient returns object with .content list or text directly?
            # UniversalMessage wraps content list of objects with .text
            if hasattr(response.content[0], 'text'):
                content = response.content[0].text.strip()
            else:
                 content = str(response.content).strip()
                 
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
        
        CRITICAL: If the research so far contains specific entities, technical terms, drugs, or conditions (e.g. "R-CHOP", "ESP32", "Python 3.12"), but lacks external context (side effects, specs, release dates), you MUST generate a "web" search step.
        
        For the "web" step:
        1. Extract the SPECIFIC terms found in the research.
        2. DO NOT use generic queries. Use the specific entities found.
        
        Generate 1-2 additional search steps to fill gaps.
        
        Return ONLY a JSON array of new steps. Each step must have:
        - sub_question: string (Specific query for web search)
        - search_strategy: "vector" | "graph" | "hybrid" | "web"
        - keywords: array of strings (The specific terms extracted)
        - target_folders: array of strings
        - reasoning: string
        """
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        try:
            if hasattr(response.content[0], 'text'):
                content = response.content[0].text.strip()
            else:
                 content = str(response.content).strip()
                 
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

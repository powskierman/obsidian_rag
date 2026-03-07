import unittest
from unittest.mock import MagicMock

from deep_thinking.synthesizer import FinalAnswerGenerator


class TestFinalAnswerGenerator(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.generator = FinalAnswerGenerator(self.mock_client)

    def test_generate_normalizes_vault_citations_and_drops_invalid_ones(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"answer":"A","citations":["Tech/ESP32.md","[[Missing.md]]","https://www.example.com/spec?utm_source=newsletter"],"confidence_score":0.9,"confidence_justification":"ok"}')]
        self.mock_client.messages.create.return_value = mock_response

        state = {
            "original_question": "question",
            "user_context": {},
            "plan": [],
            "current_step_index": 0,
            "past_steps": [],
            "accumulated_context": "",
            "retrieved_documents": [
                {
                    "source": "Tech/ESP32.md",
                    "filepath": "Tech/ESP32.md",
                    "filename": "ESP32.md",
                    "content": "vault content",
                    "type": "vector",
                    "source_category": "vault",
                },
                {
                    "source": "https://example.com/spec",
                    "filepath": "https://example.com/spec",
                    "filename": "Spec Page",
                    "content": "web content",
                    "type": "web",
                    "source_category": "web",
                },
            ],
            "iteration_count": 0,
            "max_iterations": 1,
            "should_continue": False,
            "final_answer": "",
            "citations": [],
            "raw_context_buffer": [],
            "confidence_score": 0.0,
            "confidence_justification": "",
            "warnings": [],
        }

        result = self.generator.generate(state)

        self.assertEqual(
            result["citations"],
            ["[[Tech/ESP32.md]]", "https://example.com/spec"],
        )

    def test_generate_relationship_mode_uses_minimal_evidence_set(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"answer":"DLBCL is a type of large B-cell lymphoma, and Yescarta is a CD19-directed CAR-T therapy used for relapsed or refractory large B-cell lymphoma including DLBCL.","citations":["[[Medical/Lymphoma/media/Yescarta.pdf]]","[[Medical/Lymphoma/DLBCL, Follicular Lymphoma.md]]"],"confidence_score":0.94,"confidence_justification":"Direct indication evidence plus disease definition."}')]
        self.mock_client.messages.create.return_value = mock_response

        state = {
            "original_question": "What is the connection between Yescarta and DLBCL?",
            "user_context": {},
            "plan": [],
            "current_step_index": 0,
            "past_steps": [],
            "accumulated_context": "Step 1: Gathered Yescarta indication and disease context.",
            "retrieved_documents": [
                {
                    "source": "Medical/Lymphoma/media/Yescarta.pdf",
                    "filepath": "Medical/Lymphoma/media/Yescarta.pdf",
                    "filename": "Yescarta.pdf",
                    "content": "Yescarta is a CD19-directed CAR-T cell therapy indicated for relapsed or refractory large B-cell lymphoma including DLBCL.",
                    "snippet": "Yescarta is indicated for relapsed or refractory large B-cell lymphoma including DLBCL.",
                    "type": "vector",
                    "source_category": "vault",
                    "source_type": "direct-excerpt",
                    "treatment_phase": "chemotherapy",
                },
                {
                    "source": "Medical/Lymphoma/Diagnosis and Options.md",
                    "filepath": "Medical/Lymphoma/Diagnosis and Options.md",
                    "filename": "Diagnosis and Options.md",
                    "content": "Overview of diagnosis and treatment options for lymphoma.",
                    "snippet": "Overview of diagnosis and treatment options for lymphoma.",
                    "type": "graph",
                    "source_category": "vault",
                    "source_type": "entity-context",
                },
                {
                    "source": "Medical/Lymphoma/R-CHOP.md",
                    "filepath": "Medical/Lymphoma/R-CHOP.md",
                    "filename": "R-CHOP.md",
                    "content": "R-CHOP is a chemotherapy regimen used in DLBCL.",
                    "snippet": "R-CHOP is a chemotherapy regimen used in DLBCL.",
                    "type": "graph",
                    "source_category": "vault",
                    "source_type": "entity-context",
                },
                {
                    "source": "Medical/Lymphoma/DLBCL, Follicular Lymphoma.md",
                    "filepath": "Medical/Lymphoma/DLBCL, Follicular Lymphoma.md",
                    "filename": "DLBCL, Follicular Lymphoma.md",
                    "content": "DLBCL is a subtype of large B-cell lymphoma.",
                    "snippet": "DLBCL is a subtype of large B-cell lymphoma.",
                    "type": "graph",
                    "source_category": "vault",
                    "source_type": "entity-context",
                },
            ],
            "iteration_count": 0,
            "max_iterations": 1,
            "should_continue": False,
            "final_answer": "",
            "citations": [],
            "raw_context_buffer": [],
            "confidence_score": 0.0,
            "confidence_justification": "",
            "warnings": [],
        }

        result = self.generator.generate(state)

        prompt = self.mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
        self.assertIn("This is a relationship/connection question.", prompt)
        self.assertIn("Yescarta.pdf", prompt)
        self.assertNotIn("Diagnosis and Options.md", prompt)
        self.assertNotIn("R-CHOP.md", prompt)
        self.assertEqual(
            [doc["filename"] for doc in result["used_documents"]],
            ["Yescarta.pdf"],
        )

    def test_generate_relationship_reruns_when_answer_too_long(self):
        first = MagicMock()
        first.content = [MagicMock(text='{"answer":"Axicabtagene ciloleucel is related to diffuse large B-cell lymphoma because it is a CAR-T therapy used in that disease and there are several nuances about lines of therapy, prior treatment requirements, and additional context that make this answer much too long for relationship mode even though it is medically reasonable.","citations":["https://ncbi.nlm.nih.gov/books/NBK550115"],"confidence_score":0.8,"confidence_justification":"ok"}')]
        second = MagicMock()
        second.content = [MagicMock(text='{"answer":"Axicabtagene ciloleucel is related to diffuse large B-cell lymphoma because it is a CAR-T therapy used for certain patients with relapsed or refractory large B-cell lymphoma, including DLBCL.","citations":["https://ncbi.nlm.nih.gov/books/NBK550115"],"confidence_score":0.92,"confidence_justification":"ok"}')]
        self.mock_client.messages.create.side_effect = [first, second]

        state = {
            "original_question": "How is axicabtagene ciloleucel related to diffuse large B-cell lymphoma?",
            "user_context": {},
            "plan": [],
            "current_step_index": 0,
            "past_steps": [],
            "accumulated_context": "",
            "retrieved_documents": [
                {
                    "source": "https://ncbi.nlm.nih.gov/books/NBK550115",
                    "filepath": "https://ncbi.nlm.nih.gov/books/NBK550115",
                    "filename": "Axicabtagene Ciloleucel for Large B-cell Lymphoma - NCBI - NIH",
                    "content": "Axicabtagene ciloleucel is a CAR-T therapy indicated for large B-cell lymphoma including DLBCL.",
                    "snippet": "Axicabtagene ciloleucel is a CAR-T therapy indicated for large B-cell lymphoma including DLBCL.",
                    "type": "web",
                    "source_category": "web",
                    "source_type": "web-result",
                },
            ],
            "iteration_count": 0,
            "max_iterations": 1,
            "should_continue": False,
            "final_answer": "",
            "citations": [],
            "raw_context_buffer": [],
            "confidence_score": 0.0,
            "confidence_justification": "",
            "warnings": [],
        }

        result = self.generator.generate(state)

        self.assertLessEqual(len(result["answer"]), 350)
        self.assertEqual(self.mock_client.messages.create.call_count, 2)
        self.assertEqual(result["used_documents"][0]["source_category"], "web")

    def test_generate_relationship_can_return_web_only_answer(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"answer":"Axicabtagene ciloleucel is related to diffuse large B-cell lymphoma because it is a CAR-T therapy used for certain adults with large B-cell lymphoma, including DLBCL.","citations":["https://ncbi.nlm.nih.gov/books/NBK550115"],"confidence_score":0.93,"confidence_justification":"Direct web evidence."}')]
        self.mock_client.messages.create.return_value = mock_response

        state = {
            "original_question": "How is axicabtagene ciloleucel related to diffuse large B-cell lymphoma?",
            "user_context": {},
            "plan": [],
            "current_step_index": 0,
            "past_steps": [],
            "accumulated_context": "",
            "retrieved_documents": [
                {
                    "source": "Tech/Electronics/Projects/Halcyon/Blynk-local-server-auth-token.md",
                    "filepath": "Tech/Electronics/Projects/Halcyon/Blynk-local-server-auth-token.md",
                    "filename": "Blynk-local-server-auth-token.md",
                    "content": "Authentication token setup for the local Blynk server.",
                    "snippet": "Authentication token setup for the local Blynk server.",
                    "type": "vector",
                    "source_category": "vault",
                    "source_type": "direct-excerpt",
                },
                {
                    "source": "https://ncbi.nlm.nih.gov/books/NBK550115",
                    "filepath": "https://ncbi.nlm.nih.gov/books/NBK550115",
                    "filename": "Axicabtagene Ciloleucel for Large B-cell Lymphoma - NCBI - NIH",
                    "content": "Axicabtagene ciloleucel is a CAR-T therapy indicated for large B-cell lymphoma including DLBCL.",
                    "snippet": "Axicabtagene ciloleucel is a CAR-T therapy indicated for large B-cell lymphoma including DLBCL.",
                    "type": "web",
                    "source_category": "web",
                    "source_type": "web-result",
                },
            ],
            "iteration_count": 0,
            "max_iterations": 1,
            "should_continue": False,
            "final_answer": "",
            "citations": [],
            "raw_context_buffer": [],
            "confidence_score": 0.0,
            "confidence_justification": "",
            "warnings": [],
        }

        result = self.generator.generate(state)

        self.assertEqual(result["citations"], ["https://ncbi.nlm.nih.gov/books/NBK550115"])
        self.assertEqual([doc["source_category"] for doc in result["used_documents"]], ["web"])

    def test_generate_uses_authoritative_documents_not_raw_context_buffer(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"answer":"A","citations":["[[Tech/ESP32.md]]"],"confidence_score":0.9,"confidence_justification":"ok"}')]
        self.mock_client.messages.create.return_value = mock_response

        state = {
            "original_question": "What do my ESP32 notes say?",
            "user_context": {},
            "plan": [],
            "current_step_index": 0,
            "past_steps": [],
            "accumulated_context": "",
            "retrieved_documents": [
                {
                    "source": "Tech/ESP32.md",
                    "filepath": "Tech/ESP32.md",
                    "filename": "ESP32.md",
                    "content": "Authoritative vault content",
                    "snippet": "Authoritative vault content",
                    "type": "vector",
                    "source_category": "vault",
                    "source_type": "direct-excerpt",
                },
            ],
            "iteration_count": 0,
            "max_iterations": 1,
            "should_continue": False,
            "final_answer": "",
            "citations": [],
            "raw_context_buffer": [
                {
                    "source": "Tech/Stale.md",
                    "content": "Stale raw buffer content",
                    "step": 1,
                }
            ],
            "confidence_score": 0.0,
            "confidence_justification": "",
            "warnings": [],
        }

        result = self.generator.generate(state)

        prompt = self.mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
        self.assertIn("Tech/ESP32.md", prompt)
        self.assertNotIn("Tech/Stale.md", prompt)
        self.assertEqual(result["used_documents"][0]["filepath"], "Tech/ESP32.md")

    def test_generate_retries_empty_answer_with_reduced_documents(self):
        first = MagicMock()
        first.content = [MagicMock(text='{"answer":"","citations":[],"confidence_score":0.2,"confidence_justification":"empty"}')]
        second = MagicMock()
        second.content = [MagicMock(text='{"answer":"ESP32 notes focus on the main controller setup.","citations":["[[Tech/ESP32.md]]"],"confidence_score":0.9,"confidence_justification":"ok"}')]
        self.mock_client.messages.create.side_effect = [first, second]

        state = {
            "original_question": "Compare my ESP32 and ESP8266 notes",
            "user_context": {},
            "plan": [],
            "current_step_index": 0,
            "past_steps": [],
            "accumulated_context": "Step 1: Found several controller notes.",
            "retrieved_documents": [
                {
                    "source": "Tech/ESP32.md",
                    "filepath": "Tech/ESP32.md",
                    "filename": "ESP32.md",
                    "title": "ESP32",
                    "content": "ESP32 setup details.",
                    "snippet": "ESP32 setup details.",
                    "type": "vector",
                    "source_category": "vault",
                    "source_type": "direct-excerpt",
                },
                {
                    "source": "Tech/ESP8266.md",
                    "filepath": "Tech/ESP8266.md",
                    "filename": "ESP8266.md",
                    "title": "ESP8266",
                    "content": "ESP8266 setup details.",
                    "snippet": "ESP8266 setup details.",
                    "type": "vector",
                    "source_category": "vault",
                    "source_type": "direct-excerpt",
                },
                {
                    "source": "Tech/Microcontrollers.md",
                    "filepath": "Tech/Microcontrollers.md",
                    "filename": "Microcontrollers.md",
                    "title": "Microcontrollers",
                    "content": "General microcontroller notes.",
                    "snippet": "General microcontroller notes.",
                    "type": "vector",
                    "source_category": "vault",
                    "source_type": "direct-excerpt",
                },
            ],
            "iteration_count": 0,
            "max_iterations": 1,
            "should_continue": False,
            "final_answer": "",
            "citations": [],
            "raw_context_buffer": [],
            "confidence_score": 0.0,
            "confidence_justification": "",
            "warnings": [],
        }

        result = self.generator.generate(state)

        self.assertEqual(self.mock_client.messages.create.call_count, 2)
        second_prompt = self.mock_client.messages.create.call_args_list[1].kwargs["messages"][0]["content"]
        self.assertIn("Tech/ESP32.md", second_prompt)
        self.assertIn("Tech/ESP8266.md", second_prompt)
        self.assertNotIn("Tech/Microcontrollers.md", second_prompt)
        self.assertIn("ESP32 notes", result["answer"])


if __name__ == '__main__':
    unittest.main()

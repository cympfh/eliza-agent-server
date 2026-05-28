"""モデル定数の定義"""

MODEL = "grok-4.3"

# reasoning_effort: "none" | "low" | "medium" | "high"
LIGHT_REASONING_EFFORT = "none"  # IntentRouter, TrivialAgent, TranslatorAgent
QUESTION_REASONING_EFFORT = "low"  # QuestionAgent
HEAVY_REASONING_EFFORT = "medium"  # FullOperationAgent, SubAgents
SUMMARY_REASONING_EFFORT = "none"  # memory.generate_summary

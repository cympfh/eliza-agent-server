"""モデル定数の定義"""

MODEL = "grok-4.5"

# reasoning_effort: "low" | "medium" | "high"
# grok-4.5 は reasoning を無効化できず "none" 非対応のため "low" が最小値
LIGHT_REASONING_EFFORT = "low"  # IntentRouter, TrivialAgent, TranslatorAgent
QUESTION_REASONING_EFFORT = "low"  # QuestionAgent
HEAVY_REASONING_EFFORT = "medium"  # FullOperationAgent, SubAgents
SUMMARY_REASONING_EFFORT = "low"  # memory.generate_summary

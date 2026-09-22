"""モデル定数の定義"""

MODEL = "grok-4.7"

# reasoning_effort: "low" | "medium" | "high" | "xhigh"
# grok-4.7 も reasoning を無効化できず "none" 非対応のため "low" が最小値
LIGHT_REASONING_EFFORT = "low"  # IntentRouter, TrivialAgent, TranslatorAgent, FullOperation 最終 parse
QUESTION_REASONING_EFFORT = "low"  # QuestionAgent
HEAVY_REASONING_EFFORT = "xhigh"  # FullOperationAgent
SUMMARY_REASONING_EFFORT = "low"  # memory.generate_summary

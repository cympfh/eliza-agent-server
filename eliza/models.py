"""モデル定数の定義"""

MODEL = "grok-4.6"

# reasoning_effort: "low" | "medium" | "high" | "xhigh"
# grok-4.6 は reasoning を無効化できず "none" 非対応のため "low" が最小値
# "xhigh" は grok-4.6 以降。現状は未使用
LIGHT_REASONING_EFFORT = "low"  # IntentRouter, TrivialAgent, TranslatorAgent
QUESTION_REASONING_EFFORT = "low"  # QuestionAgent
HEAVY_REASONING_EFFORT = "medium"  # FullOperationAgent, SubAgents
SUMMARY_REASONING_EFFORT = "low"  # memory.generate_summary

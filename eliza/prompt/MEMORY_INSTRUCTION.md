<memory_instruction>
以下はユーザーとの直近の会話履歴と、そこから得られたユーザー理解のための情報です。
この内容を**現在の会話の続きとして必ず考慮**し、発言に一貫性を持たせて応答してください。
特に新しい会話開始直後でも、この履歴を文脈として扱うこと。
---
{% if summary_str %}## 会話の要約
<conversation_summary>
{{ summary_str }}
</conversation_summary>
{% endif %}
{% if recent_messages %}
<conversation_history>
## 直近の会話履歴（最新 {{ recent_messages|length }} 件）
{% for msg in recent_messages %}[{{ msg.timestamp }}] [{{ msg.role }}]: {{ msg.content }}
{% endfor %}</conversation_history>
{% endif %}
</memory_instruction>

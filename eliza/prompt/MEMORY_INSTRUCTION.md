以下はユーザーと過去にやりとりして話した内容と、ここから得られたユーザーに関する情報をまとめたものです。ユーザーのことを理解するために、これらの内容を参考にしてください。
---
{{ summary_str }}
{% if recent_messages %}
## 最近の会話（直近3往復）
{% for msg in recent_messages %}[{{ msg.role }}]: {{ msg.content }}
{% endfor %}{% endif %}

import logging

from pydantic import BaseModel, Field
from xai_sdk import Client, chat

from eliza.agents.trivial import TrivialAgent

logger = logging.getLogger(__name__)


class TranslationResult(BaseModel):
    translated_text: str = Field(description="翻訳結果のみ 前置きや説明は含めない")


class TranslatorAgent(TrivialAgent):
    agent_name = "translator"

    def translate(
        self,
        text: str,
        target_lang: str,
        source_lang: str | None = None,
        request_id: str = "",
    ) -> str:
        """テキストを翻訳し結果のみを返す

        Parameters
        ----------
        text
            翻訳対象のテキスト
        target_lang
            翻訳先言語
        source_lang
            翻訳元言語 指定なしなら自動判定
        request_id
            ログ追跡用のリクエスト ID
        """
        client = Client(api_key=self.api_key)
        session = client.chat.create(
            model=self.model, reasoning_effort=self.reasoning_effort
        )

        prompt = self._load_prompt(
            "TRANSLATE_INSTRUCTION.md",
            source_lang=source_lang,
            target_lang=target_lang,
        )
        session.append(chat.system(prompt))
        session.append(chat.user(text))

        logger.info(f"[REQUEST ID: {request_id}] TranslatorAgent: translating...")
        _, result = session.parse(TranslationResult)

        return result.translated_text

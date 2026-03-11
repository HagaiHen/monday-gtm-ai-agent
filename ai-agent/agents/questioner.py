import json
import re
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from .prompts import QUESTIONER_SYSTEM_PROMPT


class QuestionerAgent:
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.7,
        )

    async def invoke(
        self,
        message: str,
        history: list[dict],
        session: dict,
        website_context: str = "",
    ) -> dict:
        """
        Process a message and return either a question or done signal.

        Args:
            message: User's latest message
            history: List of previous messages [{"role": "user"|"assistant", "content": "..."}]
            session: Full session data including form fields
            website_context: Scraped website text to help formulate smarter questions

        Returns:
            {"reply": "...", "done": False} or
            {"reply": "...", "done": True, "summary": {...}}
        """
        # Build a system note with the form context so the agent is aware of it
        form_context = f"""[Registration form data]
- Company: {session.get('company', '')}
- Website: {session.get('website', '') or 'not provided'}
- Industry: {session.get('industry', '')}
- Use case: {session.get('pain_point', '')}
- Team size: {session.get('team_size', 'not provided')}
"""

        if website_context:
            form_context += f"""
[Company website content — use this to ask smarter, company-specific questions]
{website_context[:6000]}
"""

        messages = [
            SystemMessage(content=QUESTIONER_SYSTEM_PROMPT),
            SystemMessage(content=form_context),
        ]

        for msg in history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))

        messages.append(HumanMessage(content=message))

        response = await self.llm.ainvoke(messages)
        content = response.content.strip()

        done_data = self._extract_done_signal(content)
        if done_data:
            return {
                "reply": "Perfect! We're setting up your workspace and will email you shortly.",
                "done": True,
                "summary": done_data["summary"],
            }

        return {"reply": content, "done": False}

    def _extract_done_signal(self, content: str) -> Optional[dict]:
        try:
            data = json.loads(content)
            if data.get("done") is True and "summary" in data:
                return data
        except json.JSONDecodeError:
            pass

        json_match = re.search(r'\{.*"done".*true.*\}', content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                if data.get("done") is True and "summary" in data:
                    return data
            except json.JSONDecodeError:
                pass

        return None

import os
import base64

import dotenv
from openai import OpenAI

from io import BytesIO

from django.conf import settings

dotenv.load_dotenv()

# Инициализируем клиент OpenAI с API ключом и базовым URL
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://api.vsegpt.ru:6070/v1/"
)

ASSISTANT_PROMPT = settings.ASSISTANT_PROMPT


class BaseAIAPI:
    def __init__(self) -> None:
        self._ASSISTANT_PROMPT: str = ASSISTANT_PROMPT
        self.chat_history: dict = {}
        self._TEMPERATURE = 0.7

    def clear_chat_history(self, chat_id: int) -> None:
        self.chat_history.pop(str(chat_id), None)


class OpenAIAPI(BaseAIAPI):
    def __init__(self) -> None:
        super().__init__()

    def _get_or_create_user_chat_history(self, chat_id: int, text: str, ai_instruction: str = None) -> list:
        chat_id_str = str(chat_id)
        
        # Используем пользовательскую AI инструкцию, если она предоставлена, иначе базовую
        system_prompt = ai_instruction if ai_instruction else self._ASSISTANT_PROMPT
        
        if chat_id_str not in self.chat_history:
            self.chat_history[chat_id_str] = [{"role": "system", "content": system_prompt}]
        
        self.chat_history[chat_id_str].append({"role": "user", "content": text})
        
        return self.chat_history[chat_id_str]

    def get_response(self, chat_id: int, text: str, ai_instruction: str = None, max_token: int = 1024) -> dict:
        try:
            user_chat_history = self._get_or_create_user_chat_history(chat_id, text, ai_instruction)
            
            # Используем gpt-4o-mini без префикса openai/
            
            response = (
                client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=user_chat_history,
                    temperature=self._TEMPERATURE,
                    n=1,
                    max_tokens=max_token,
                )
            )

            # Проверяем, есть ли выбор в ответе
            if not response.choices or len(response.choices) == 0:
                return {"message": "Извините, я не получил ответа от модели. Пожалуйста, попробуйте еще раз."}

            answer = {"message": response.choices[0].message.content}
            chat_id_str = str(chat_id)
            
            if chat_id_str in self.chat_history:
                self.chat_history[chat_id_str].append({"role": "assistant", "content": answer["message"]})

            return answer

        except Exception as e:
            print(f"Не удалось получить ответ от AI: {e}")
            return {"message": "Извините, я не смог обработать ваш запрос. Пожалуйста, попробуйте еще раз или обратитесь в службу поддержки."}

    def add_txt_to_user_chat_history(self, chat_id: int, text: str, ai_instruction: str = None) -> None:
        try:
            self._get_or_create_user_chat_history(chat_id, text, ai_instruction)
        except Exception as e:
            print(f"Ошибка при добавлении текста в историю чата пользователя: {e}")

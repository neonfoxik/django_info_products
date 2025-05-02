import os
import base64

import dotenv
import openai

from io import BytesIO

from django.conf import settings

dotenv.load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

ASSISTANT_PROMPT = settings.ASSISTANT_PROMPT

# Устанавливаем URL API
openai.base_url = "https://api.vsegpt.ru:6070/v1/"


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

    def _get_or_create_user_chat_history(self, chat_id: int, new_user_message: str = "") -> list:
        chat_id_str = str(chat_id)  # Преобразуем в строку для использования в качестве ключа
        
        if not self.chat_history.get(chat_id_str):
            self.chat_history[chat_id_str] = []
            self.chat_history[chat_id_str].append({"role": "system", "content": self._ASSISTANT_PROMPT})
            
        if new_user_message:  # Добавляем сообщение пользователя только если оно не пустое
            self.chat_history[chat_id_str].append({"role": "user", "content": new_user_message})
            
        return self.chat_history[chat_id_str]

    def get_response(self, chat_id: int, text: str, max_token: int = 1024) -> dict:
        try:
            user_chat_history = self._get_or_create_user_chat_history(chat_id, text)
            
            # Используем gpt-4o-mini без префикса openai/
            
            response = (
                openai.chat.completions.create(
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

        except openai.APIError as e:
            error_msg = f"Ошибка API OpenAI: {str(e)}"
            print(error_msg)
            return {"message": "Извините, произошла ошибка при обращении к сервису AI. Пожалуйста, попробуйте позже."}
        except Exception as e:
            print(f"Не удалось получить ответ от AI: {e}")
            return {"message": "Извините, я не смог обработать ваш запрос. Пожалуйста, попробуйте еще раз или обратитесь в службу поддержки."}

    def add_txt_to_user_chat_history(self, chat_id: int, text: str) -> None:
        try:
            self._get_or_create_user_chat_history(chat_id, text)
        except Exception as e:
            print(f"Ошибка при добавлении текста в историю чата пользователя: {e}")

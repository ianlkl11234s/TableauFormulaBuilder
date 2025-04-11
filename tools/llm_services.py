import os
from abc import ABC, abstractmethod
from openai import OpenAI, RateLimitError, AuthenticationError, APIError
import google.generativeai as genai
from anthropic import Anthropic, AnthropicError # 假設您會安裝 Anthropic 套件

# --- 通用 LLM 介面 ---
class LLMClientInterface(ABC):
    """定義 LLM 客戶端的通用介面"""
    @abstractmethod
    def generate_text(self, prompt: str, model: str, temperature: float) -> str:
        """
        產生文字的核心方法。

        Args:
            prompt: 給予模型的提示文字。
            model: 要使用的模型名稱。
            temperature: 控制生成文本隨機性的溫度值。

        Returns:
            模型生成的文字結果。

        Raises:
            Exception: 如果 API 呼叫失敗或發生其他錯誤。
        """
        pass

    @abstractmethod
    def check_availability(self) -> bool:
        """檢查此服務是否可用 (例如，是否有 API Key)"""
        pass

# --- OpenAI 實作 ---
class OpenAIClient(LLMClientInterface):
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.client = None
        if self.api_key:
            try:
                self.client = OpenAI(api_key=self.api_key)
            except Exception as e:
                print(f"無法初始化 OpenAI Client: {e}") # 在伺服器端記錄錯誤

    def check_availability(self) -> bool:
        return bool(self.client)

    def generate_text(self, prompt: str, model: str = "gpt-4o-mini", temperature: float = 0.3) -> str:
        if not self.client:
            raise ConnectionError("OpenAI 客戶端未成功初始化。")
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature
            )
            return response.choices[0].message.content.strip()
        except AuthenticationError as e:
            print(f"OpenAI 驗證錯誤: {e}")
            raise ConnectionAbortedError("OpenAI API Key 錯誤或無效。") from e
        except RateLimitError as e:
            print(f"OpenAI 速率限制錯誤: {e}")
            raise ConnectionRefusedError("已達到 OpenAI API 使用速率限制。") from e
        except APIError as e:
            print(f"OpenAI API 錯誤: {e}")
            raise RuntimeError(f"OpenAI API 返回錯誤: {e}") from e
        except Exception as e:
            print(f"OpenAI 未知錯誤: {e}")
            raise RuntimeError(f"呼叫 OpenAI API 時發生未知錯誤: {e}") from e

# --- Gemini 實作 ---
class GeminiClient(LLMClientInterface):
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.client = None
        if self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                # 測試一下是否可以列出模型，簡單驗證 API Key
                models = genai.list_models()
                # 選擇一個支援 generateContent 的模型作為預設檢查點
                if any('generateContent' in m.supported_generation_methods for m in models):
                     self.client = genai # 標記 client 已配置
                else:
                     print("Gemini API Key 配置成功，但找不到支援 generateContent 的模型。")

            except Exception as e:
                 print(f"無法初始化 Google GenAI (Gemini): {e}") # 伺服器端記錄

    def check_availability(self) -> bool:
        return bool(self.client)

    def generate_text(self, prompt: str, model: str = "gemini-1.5-flash", temperature: float = 0.3) -> str:
        if not self.client:
            raise ConnectionError("Gemini 客戶端未成功初始化或配置。")
        try:
            # 注意：Gemini 的 temperature 可能在 generation_config 中設定
            generation_config = genai.types.GenerationConfig(temperature=temperature)
            model_instance = genai.GenerativeModel(model)
            response = model_instance.generate_content(prompt, generation_config=generation_config)
            return response.text.strip()
        except Exception as e:
            # Gemini 的錯誤類型可能不同，這裡用通用 Exception
            print(f"Gemini API 錯誤: {e}")
            # 可以根據 google.api_core.exceptions 細化錯誤處理
            raise RuntimeError(f"呼叫 Gemini API 時發生錯誤: {e}") from e

# --- Claude 實作 ---
class ClaudeClient(LLMClientInterface):
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.client = None
        if self.api_key:
            try:
                self.client = Anthropic(api_key=self.api_key)
                # 可以加一個簡單的 ping 或測試 API 呼叫來驗證
            except Exception as e:
                print(f"無法初始化 Anthropic Client (Claude): {e}") # 伺服器端記錄

    def check_availability(self) -> bool:
        return bool(self.client)

    def generate_text(self, prompt: str, model: str = "claude-3-sonnet-20240229", temperature: float = 0.3) -> str:
        if not self.client:
            raise ConnectionError("Claude 客戶端未成功初始化。")
        try:
            # Claude API 的結構可能略有不同
            message = self.client.messages.create(
                model=model,
                max_tokens=1024, # 可能需要設定 max_tokens
                temperature=temperature,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            # Claude 回應的結構可能也不同
            return message.content[0].text.strip()
        except AnthropicError as e: # 使用 Anthropic 的特定錯誤類型
            print(f"Anthropic API 錯誤: {e}")
            raise RuntimeError(f"呼叫 Claude API 時發生錯誤: {e.status_code} - {e.message}") from e
        except Exception as e:
            print(f"Anthropic 未知錯誤: {e}")
            raise RuntimeError(f"呼叫 Claude API 時發生未知錯誤: {e}") from e

# --- 工廠函數或字典來獲取客戶端 ---
def get_llm_client(provider: str) -> LLMClientInterface | None:
    """根據提供者名稱獲取對應的 LLM 客戶端實例"""
    if provider.lower() == "openai":
        client = OpenAIClient()
    elif provider.lower() == "gemini":
        client = GeminiClient()
    elif provider.lower() == "claude":
        client = ClaudeClient()
    else:
        return None # 或拋出錯誤

    if client and client.check_availability():
        return client
    else:
        # 如果 client 初始化失敗或 key 無效，也返回 None
        return None

# --- 可用的模型列表 (可以根據需要擴充) ---
AVAILABLE_MODELS = {
    "openai": ["gpt-4o-mini"],
    "gemini": ["gemini-2.0-flash"],
    "claude": ["claude-3-5-haiku-20241022"]
}
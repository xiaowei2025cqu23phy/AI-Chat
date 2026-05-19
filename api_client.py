"""
DeepSeek R1 Pro — API 客户端（QThread Worker 模式）
"""

import json
import time
import requests
from PySide6.QtCore import QThread, Signal


class DeepSeekWorker(QThread):
    """在后台线程执行流式 API 请求，通过信号与主线程通信"""

    chunk_received = Signal(str, str)       # (full_text, msg_id)
    request_finished = Signal(str)          # (msg_id)
    error_occurred = Signal(str)            # (error_message)

    def __init__(self, api_url, api_key, model, messages, temp, max_tokens, assistant_mid):
        super().__init__()
        self.api_url = api_url
        self.api_key = api_key
        self.model = model
        self.messages = messages
        self.temp = temp
        self.max_tokens = max_tokens
        self.assistant_mid = assistant_mid

    def run(self):
        full_text = ""
        last_exception = None

        for attempt in range(3):
            try:
                response = requests.post(
                    self.api_url,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "messages": self.messages,
                        "temperature": self.temp,
                        "max_tokens": self.max_tokens,
                        "stream": True
                    },
                    stream=True,
                    timeout=90
                )

                if response.status_code != 200:
                    last_exception = Exception(f"HTTP {response.status_code}: {response.text[:200]}")
                    if attempt < 2:
                        time.sleep(2 ** attempt)
                        continue
                    break

                for chunk in response.iter_lines():
                    if not chunk:
                        continue
                    try:
                        decoded = chunk.decode('utf-8')
                    except UnicodeDecodeError:
                        continue

                    if not decoded.startswith("data: "):
                        continue

                    data_str = decoded[6:]
                    if data_str.strip() == "[DONE]":
                        break

                    try:
                        data = json.loads(data_str)
                        delta = data['choices'][0]['delta'].get('content', '')
                        if delta:
                            full_text += delta
                            self.chunk_received.emit(full_text, self.assistant_mid)
                    except (json.JSONDecodeError, KeyError, IndexError) as e:
                        # 跳过无法解析的 chunk（SSE 可能包含注释/空数据）
                        pass

                break  # 成功完成，退出重试循环

            except requests.exceptions.Timeout:
                last_exception = Exception("请求超时，请检查网络连接")
                if attempt < 2:
                    time.sleep(2 ** attempt)
            except requests.exceptions.ConnectionError:
                last_exception = Exception("连接失败，请检查网络")
                if attempt < 2:
                    time.sleep(2 ** attempt)
            except Exception as e:
                last_exception = e
                if attempt < 2:
                    time.sleep(2 ** attempt)

        if full_text:
            self.request_finished.emit(self.assistant_mid)
        elif last_exception:
            self.error_occurred.emit(str(last_exception))
        else:
            self.error_occurred.emit("未收到有效响应")


def get_api_key():
    """从环境变量读取 API Key"""
    import os
    return os.environ.get("DEEPSEEK_API_KEY", "")

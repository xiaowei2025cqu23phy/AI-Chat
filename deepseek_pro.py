#!/usr/bin/env python3
"""
DeepSeek R1 Pro - 专业 AI 助手（优化版）
功能：六模式切换 | 思维链显示 | 参数调节 | 自动输入 | 对话管理
"""

import re
import os
import sys
from datetime import datetime

from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

from modes import MODES, MODE_KEYS, DEFAULT_MODE
from api_client import DeepSeekWorker, get_api_key

# DPI 设置
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
os.environ["QT_SCALE_FACTOR"] = "1"

# 预编译正则
RE_CODE_BLOCK = re.compile(r'```(\w*)\n(.*?)```', re.DOTALL)
RE_INLINE_CODE = re.compile(r'`(.*?)`')
RE_THINKING = re.compile(r'(🧠 思考过程 [：:].*?)(?=✅ 结论 | 结论:|$)', re.DOTALL)
RE_CONCLUSION = re.compile(r'(✅ 结论 [：:].*?)$', re.DOTALL)
RE_BOLD = re.compile(r'\*\*(.*?)\*\*')


class DeepSeekPro(QMainWindow):

    status_signal = Signal(str, str)
    render_signal = Signal()

    def __init__(self):
        super().__init__()
        self.api_key = get_api_key()
        self.api_url = "https://api.deepseek.com/chat/completions"
        self.model_name = "deepseek-reasoner"

        self.history = []
        self.current_mode = DEFAULT_MODE
        self.auto_type_enabled = False
        self.msg_data = {}          # {mid: {role, content, html}} — Python 3.7+ 保序
        self._worker = None         # 当前 Worker 引用
        self._streaming_mid = None  # 正在流式更新的消息 ID

        self._setup_signals()
        self._init_ui()
        self._update_system_prompt()

    def _setup_signals(self):
        self.status_signal.connect(self._update_status_ui)
        self.render_signal.connect(self._render_messages)

    # ── UI 初始化 ──────────────────────────────────────────────

    def _init_ui(self):
        self.setWindowTitle("DeepSeek R1 Pro - 专业 AI 助手")
        self.setMinimumSize(1200, 800)
        self.setStyleSheet("QMainWindow { background-color: #f5f7f9; }")

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        self._build_sidebar(layout)
        self._build_main_area(layout)

        QShortcut(QKeySequence("Ctrl+Return"), self).activated.connect(self._send_message)
        QShortcut(QKeySequence("F5"), self).activated.connect(self._clear_chat)

    def _build_sidebar(self, parent_layout):
        sidebar = QFrame()
        sidebar.setFixedWidth(260)
        sidebar.setStyleSheet("background: #1e293b; color: white;")
        sl = QVBoxLayout(sidebar)

        logo = QLabel("🤖 DeepSeek R1 Pro")
        logo.setStyleSheet("font-size: 20px; font-weight: bold; margin: 20px 10px; color: #38bdf8;")
        sl.addWidget(logo)

        mode_label = QLabel("\n⚙️ 对话模式")
        mode_label.setStyleSheet("color: #94a3b8; font-size: 13px; padding: 10px;")
        sl.addWidget(mode_label)

        self.mode_list = QListWidget()
        self.mode_list.addItems([f"{m['icon']} {m['name']}" for m in MODES.values()])
        self.mode_list.setCurrentRow(0)
        self.mode_list.setStyleSheet("""
            QListWidget { background: transparent; border: none; outline: none; font-size: 14px; }
            QListWidget::item { padding: 12px 15px; border-radius: 6px; margin: 3px 5px; }
            QListWidget::item:selected { background-color: #334155; color: #38bdf8; }
            QListWidget::item:hover { background-color: #2d3a4f; }
        """)
        self.mode_list.currentRowChanged.connect(self._change_mode)
        sl.addWidget(self.mode_list)

        self.stats = QLabel("\n📊 统计\nToken: 0\n字数：0")
        self.stats.setStyleSheet(
            "color: #94a3b8; font-size: 12px; padding: 10px; background: #0f172a; border-radius: 5px; margin: 10px;")
        sl.addWidget(self.stats)

        btn_style = """
            QPushButton { background: #334155; color: white; border: none;
                          padding: 10px; border-radius: 6px; margin: 5px; font-size: 13px; }
            QPushButton:hover { background: #475569; }
        """

        export_btn = QPushButton("💾 导出对话")
        export_btn.setStyleSheet(btn_style)
        export_btn.clicked.connect(self._export_chat)
        sl.addWidget(export_btn)

        clear_btn = QPushButton("🗑️ 清空历史")
        clear_btn.setStyleSheet(btn_style)
        clear_btn.clicked.connect(self._clear_chat)
        sl.addWidget(clear_btn)

        sl.addStretch()
        parent_layout.addWidget(sidebar)

    def _build_main_area(self, parent_layout):
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(0)

        content_layout.addWidget(self._build_top_bar())

        self.chat_display = QTextBrowser()
        self.chat_display.setOpenExternalLinks(True)
        self.chat_display.setStyleSheet("""
            QTextBrowser { background: #f8fafc; border: none; padding: 20px; line-height: 1.6; font-size: 14px; }
        """)
        content_layout.addWidget(self.chat_display)

        self._show_welcome()

        content_layout.addWidget(self._build_input_box())
        parent_layout.addWidget(content)

    def _build_top_bar(self):
        top_bar = QFrame()
        top_bar.setFixedHeight(60)
        top_bar.setStyleSheet("background: white; border-bottom: 1px solid #e2e8f0;")
        tl = QHBoxLayout(top_bar)
        tl.setContentsMargins(15, 10, 15, 10)

        self.status_icon = QLabel("●")
        self.status_icon.setStyleSheet("color: #10b981; font-size: 20px; font-weight: bold;")
        self.status_text = QLabel("系统就绪")
        self.status_text.setStyleSheet("font-size: 14px; color: #64748b;")

        tl.addWidget(self.status_icon)
        tl.addWidget(self.status_text)
        tl.addStretch()

        temp_layout = QHBoxLayout()
        temp_layout.addWidget(QLabel("🌡️ 创造力:"))
        self.temp_slider = QSlider(Qt.Horizontal)
        self.temp_slider.setRange(0, 20)
        self.temp_slider.setValue(7)
        self.temp_slider.setFixedWidth(120)
        self.temp_label = QLabel("0.7")
        self.temp_slider.valueChanged.connect(lambda v: self.temp_label.setText(f"{v/10:.1f}"))
        temp_layout.addWidget(self.temp_slider)
        temp_layout.addWidget(self.temp_label)
        tl.addLayout(temp_layout)
        tl.addSpacing(20)

        len_layout = QHBoxLayout()
        len_layout.addWidget(QLabel("📏 长度:"))
        self.len_spin = QSpinBox()
        self.len_spin.setRange(512, 8192)
        self.len_spin.setValue(2048)
        self.len_spin.setSuffix(" tokens")
        self.len_spin.setFixedWidth(130)
        len_layout.addWidget(self.len_spin)
        tl.addLayout(len_layout)

        return top_bar

    def _build_input_box(self):
        input_box = QFrame()
        input_box.setStyleSheet("background: white; border-top: 1px solid #e2e8f0; padding: 15px;")
        il = QVBoxLayout(input_box)

        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("请输入您的问题... (Ctrl+Enter 发送)")
        self.input_text.setFixedHeight(80)
        self.input_text.setStyleSheet("""
            QTextEdit { border: 2px solid #cbd5e1; border-radius: 8px;
                        padding: 12px; font-size: 14px; font-family: 'Microsoft YaHei'; }
            QTextEdit:focus { border-color: #3b82f6; }
        """)
        il.addWidget(self.input_text)

        btn_row = QHBoxLayout()

        self.auto_type_btn = QPushButton("⌨️ 自动输入：OFF")
        self.auto_type_btn.setCheckable(True)
        self.auto_type_btn.setFixedHeight(40)
        self.auto_type_btn.setStyleSheet("""
            QPushButton { background: #f59e0b; color: white; border-radius: 6px; font-weight: bold; padding: 8px 15px; }
            QPushButton:checked { background: #ea580c; }
        """)
        self.auto_type_btn.clicked.connect(self._toggle_auto_type)

        send_btn = QPushButton("🚀 发送")
        send_btn.setFixedHeight(40)
        send_btn.setFixedWidth(120)
        send_btn.setStyleSheet("""
            QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #2563eb);
                          color: white; border: none; border-radius: 6px; font-weight: bold; font-size: 15px; }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #1d4ed8); }
            QPushButton:disabled { background: #cbd5e1; }
        """)
        send_btn.clicked.connect(self._send_message)

        btn_row.addWidget(self.auto_type_btn)
        btn_row.addStretch()
        btn_row.addWidget(send_btn)
        il.addLayout(btn_row)
        return input_box

    # ── 内容处理 ──────────────────────────────────────────────

    def _process_content(self, content, role):
        if not content:
            return ""

        text = content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        # 代码块
        if '```' in text:
            text = RE_CODE_BLOCK.sub(
                r'<pre style="background:#0f172a; color:#f8fafc; padding:15px; border-radius:8px; overflow-x:auto;"><code>\2</code></pre>',
                text)

        # 行内代码
        if '`' in text:
            text = RE_INLINE_CODE.sub(
                r'<code style="background:#e2e8f0; color:#dc2626; padding:2px 5px; border-radius:3px;">\1</code>',
                text)

        # 思考过程高亮
        if '思考过程' in text:
            text = RE_THINKING.sub(
                r'<div style="background:#f1f5f9; padding:15px; border-left:4px solid #64748b; margin:10px 0; color:#475569;">\1</div>',
                text)

        # 结论高亮
        if '结论' in text:
            text = RE_CONCLUSION.sub(
                r'<div style="background:#f0fdf4; padding:15px; border-left:4px solid #22c55e; color:#166534; font-weight:bold;">\1</div>',
                text)

        # 粗体
        if '**' in text:
            text = RE_BOLD.sub(r'<b>\1</b>', text)

        text = text.replace('\n', '<br>')
        return text

    def _format_message(self, role, content, msg_id):
        is_user = role == "user"
        align = "right" if is_user else "left"
        bg = "#3b82f6" if is_user else "#ffffff"
        color = "#ffffff" if is_user else "#1e293b"
        border = "none" if is_user else "1px solid #e2e8f0"
        icon = "👤 YOU" if is_user else "🤖 R1"

        processed = self._process_content(content, role)

        return f"""
        <div id="{msg_id}" style='margin:15px 0; overflow:auto;'>
            <div style='float:{align}; max-width:85%; background:{bg}; color:{color};
                        padding:15px; border-radius:12px; border:{border};
                        box-shadow:0 2px 5px rgba(0,0,0,0.05);'>
                <div style='font-size:11px; opacity:0.7; margin-bottom:8px;'>
                    {icon} • {datetime.now().strftime("%H:%M:%S")}
                </div>
                <div style='font-size:14px; line-height:1.6;'>{processed}</div>
            </div>
        </div>
        <div style='clear:both;'></div>
        """

    def _render_messages(self):
        """增量渲染：流式更新时只更新最后一条消息的 HTML 缓存，最终 setHtml 一次"""
        html = "<html><body style='font-family:-apple-system,Segoe UI,sans-serif; padding:20px;'>"
        for mid, data in self.msg_data.items():
            html += data["html"]
        html += "</body></html>"

        self.chat_display.setHtml(html)

        total = sum(len(d["content"]) for d in self.msg_data.values())
        self.stats.setText(f"📊 统计\nToken: ~{int(total*0.75)}\n字数：{total}")

        QTimer.singleShot(50, lambda: self.chat_display.verticalScrollBar().setValue(
            self.chat_display.verticalScrollBar().maximum()))

    def _add_message(self, role, content, mid):
        self.msg_data[mid] = {"role": role, "content": content, "html": self._format_message(role, content, mid)}
        self.render_signal.emit()

    def _update_message(self, role, content, mid):
        """流式更新：重新生成最后一条消息的 HTML 并刷新"""
        if mid in self.msg_data:
            self.msg_data[mid] = {"role": role, "content": content, "html": self._format_message(role, content, mid)}
            self.render_signal.emit()

    # ── 状态与错误处理 ─────────────────────────────────────────

    @Slot(str, str)
    def _update_status_ui(self, msg, color):
        self.status_text.setText(msg)
        self.status_icon.setStyleSheet(f"color:{color}; font-size:20px; font-weight:bold;")

    def _show_error(self, msg):
        QMessageBox.critical(self, "错误", f"请求失败：{msg}")
        self._update_status_ui("发生错误", "#ef4444")

    # ── 模式切换 ──────────────────────────────────────────────

    def _change_mode(self, index):
        if index < len(MODE_KEYS):
            self.current_mode = MODE_KEYS[index]
            self._update_system_prompt()
            mode_name = MODES[self.current_mode]["name"]
            self._update_status_ui(f"已切换：{mode_name}", "#38bdf8")

    def _update_system_prompt(self):
        prompt = MODES[self.current_mode]["prompt"]
        if self.history and self.history[0]["role"] == "system":
            self.history[0] = {"role": "system", "content": prompt}
        else:
            self.history.insert(0, {"role": "system", "content": prompt})

    # ── 发送消息 ──────────────────────────────────────────────

    def _send_message(self):
        content = self.input_text.toPlainText().strip()
        if not content:
            return

        user_mid = f"u_{int(__import__('time').time())}"
        self.history.append({"role": "user", "content": content})
        self._add_message("user", content, user_mid)

        self.input_text.clear()
        self._update_status_ui("DeepSeek 思考中...", "#f59e0b")

        assistant_mid = f"a_{int(__import__('time').time())}"
        self._add_message("assistant", "...", assistant_mid)
        self._streaming_mid = assistant_mid

        temp = self.temp_slider.value() / 10.0
        max_tokens = self.len_spin.value()
        recent_msgs = self.history[-6:]

        self._worker = DeepSeekWorker(
            self.api_url, self.api_key, self.model_name,
            recent_msgs, temp, max_tokens, assistant_mid
        )
        self._worker.chunk_received.connect(self._on_chunk_received)
        self._worker.request_finished.connect(self._on_request_finished)
        self._worker.error_occurred.connect(self._on_request_error)
        self._worker.start()

    def _on_chunk_received(self, full_text, mid):
        if mid in self.msg_data:
            self.msg_data[mid]["content"] = full_text
            self.msg_data[mid]["html"] = self._format_message("assistant", full_text, mid)
            self._render_messages()

    def _on_request_finished(self, mid):
        if mid in self.msg_data:
            self.history.append({"role": "assistant", "content": self.msg_data[mid]["content"]})
        self._update_status_ui("响应完成", "#10b981")
        self._streaming_mid = None

        if self.auto_type_enabled:
            final_text = self.msg_data[mid]["content"]
            QTimer.singleShot(1000, lambda: self._auto_type(final_text))

    def _on_request_error(self, error_msg):
        self._update_status_ui("发生错误", "#ef4444")
        self._streaming_mid = None
        QMessageBox.critical(self, "错误", f"请求失败：{error_msg}")

    # ── 自动输入 ──────────────────────────────────────────────

    def _auto_type(self, text):
        import pyperclip
        import pyautogui

        self._auto_type_step(text, 0)

    def _auto_type_step(self, text, step):
        import pyautogui
        import pyperclip

        if step == 0:
            self._update_status_ui("3 秒后自动输入...", "#f59e0b")
            QTimer.singleShot(3000, lambda: self._auto_type_step(text, 1))
            return

        if step == 1:
            paras = [p.strip() for p in text.split('\n\n') if p.strip()][:3]
            if paras:
                pyperclip.copy(paras[0])
                pyautogui.hotkey('ctrl', 'v')
                QTimer.singleShot(500, lambda: self._auto_type_step(text, 2))
            else:
                self._update_status_ui("自动输入完成", "#10b981")
            return

        if step == 2:
            paras = [p.strip() for p in text.split('\n\n') if p.strip()][:3]
            if len(paras) > 1:
                pyperclip.copy(paras[1])
                pyautogui.hotkey('ctrl', 'v')
                QTimer.singleShot(500, lambda: self._auto_type_step(text, 3))
            else:
                self._update_status_ui("自动输入完成", "#10b981")
            return

        if step == 3:
            paras = [p.strip() for p in text.split('\n\n') if p.strip()][:3]
            if len(paras) > 2:
                pyperclip.copy(paras[2])
                pyautogui.hotkey('ctrl', 'v')
            self._update_status_ui("自动输入完成", "#10b981")

    # ── 对话管理 ──────────────────────────────────────────────

    def _clear_chat(self):
        reply = QMessageBox.question(self, "确认", "确定清空所有对话吗？",
                                      QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.history = []
            self.msg_data = {}
            self._streaming_mid = None
            self._update_system_prompt()
            self._show_welcome()
            self._update_status_ui("对话已清空", "#3b82f6")

    def _export_chat(self):
        usable = [m for m in self.history if m["role"] != "system"]
        if not usable:
            QMessageBox.information(self, "提示", "暂无对话可导出")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"./history/deepseek_pro_{timestamp}.md"

        md = f"# DeepSeek R1 Pro 对话记录\n\n"
        md += f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        md += f"模式：{MODES[self.current_mode]['name']}\n\n---\n\n"

        for msg in self.history[1:] if self.history else []:
            if msg["role"] == "system":
                continue
            role = "👤 用户" if msg["role"] == "user" else "🤖 助手"
            md += f"## {role}\n\n{msg['content']}\n\n"

        try:
            os.makedirs("./history", exist_ok=True)
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(md)
            self._update_status_ui(f"已导出：{filename}", "#10b981")
            QMessageBox.information(self, "成功", f"对话已导出到:\n{filename}")
        except Exception as e:
            self._show_error(f"导出失败：{e}")

    def _show_welcome(self):
        self.msg_data = {}

        mode_cards = "".join(
            f'<div style="background:{bg}; padding:15px; border-radius:8px;">'
            f'<strong>{m["icon"]} {m["name"]}</strong><br><small>{desc}</small></div>'
            for (bg, desc), m in zip([
                ("#e0f2fe", "严谨分析 · LaTeX 公式"),
                ("#fef3c7", "完整思维链展示"),
                ("#dcfce7", "可运行代码 + 注释"),
                ("#f3e8ff", "逐步推导证明"),
                ("#ffe4e6", "富有文采的回答"),
                ("#fed7aa", "传统智慧解读"),
            ], MODES.values())
        )

        welcome = f"""
        <div style='text-align:center; padding:50px 20px;'>
            <h1 style='color:#1e293b; font-size:28px; margin-bottom:20px;'>🤖 DeepSeek R1 Pro</h1>
            <p style='color:#64748b; font-size:16px; line-height:1.8;'>
                专业 AI 助手 - 六种模式满足您的不同需求<br>请在下方输入问题，开启智能对话
            </p>
            <div style='margin-top:30px; display:grid; grid-template-columns:repeat(3,1fr); gap:15px;'>
                {mode_cards}
            </div>
            <div style='margin-top:30px; color:#94a3b8; font-size:13px;'>
                当前模式：<strong>{MODES[self.current_mode]['name']}</strong>
            </div>
        </div>
        """

        self.chat_display.setHtml(welcome)
        self.stats.setText("📊 统计\nToken: 0\n字数：0")

    # ── 自动输入开关 ──────────────────────────────────────────

    def _toggle_auto_type(self):
        self.auto_type_enabled = not self.auto_type_enabled
        status = "ON" if self.auto_type_enabled else "OFF"
        self.auto_type_btn.setText(f"⌨️ 自动输入：{status}")
        color = "#ea580c" if self.auto_type_enabled else "#f59e0b"
        self.auto_type_btn.setStyleSheet(
            f"QPushButton {{ background: {color}; color: white; border-radius: 6px; font-weight: bold; padding: 8px 15px; }}")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei", 10))

    win = DeepSeekPro()
    win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

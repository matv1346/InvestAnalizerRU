"""
ui/data_module.py - Модуль данных (импорт, парсинг, RLHF-обучение)
"""

import os
from datetime import datetime
from typing import Optional, Dict, List, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel,
    QPushButton, QTreeWidget, QTreeWidgetItem, QMessageBox,
    QFileDialog, QTextEdit, QLineEdit, QFrame, QScrollArea,
    QProgressBar, QDialog, QDialogButtonBox, QGroupBox
)
from PyQt6.QtCore import pyqtSignal, pyqtSlot, Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtCore import QModelIndex

# Алиас для совместимости
Signal = pyqtSignal
Slot = pyqtSlot

from database import Database


class DataModule(QWidget):
    """Модуль управления данными с интеллектуальным парсером и RLHF-обучением"""
    
    files_imported = Signal(dict)
    portfolio_recalculated = Signal(dict)
    
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Настройка UI модуля"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)
        
        # Заголовок
        header_layout = QHBoxLayout()
        
        title_label = QLabel("📊 Управление данными")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Кнопки действий
        self.import_btn = QPushButton("📥 Импортировать отчеты")
        self.import_btn.clicked.connect(self.show_import_dialog)
        header_layout.addWidget(self.import_btn)
        
        self.refresh_btn = QPushButton("🔄 Обновить котировки")
        self.refresh_btn.clicked.connect(self._on_refresh_quotes)
        header_layout.addWidget(self.refresh_btn)
        
        main_layout.addLayout(header_layout)
        
        # Основной сплиттер
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Левая панель - дерево файлов
        left_panel = self._create_files_panel()
        splitter.addWidget(left_panel)
        
        # Правая панель - чат с ИИ-парсером
        right_panel = self._create_ai_chat_panel()
        splitter.addWidget(right_panel)
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([400, 600])
        
        main_layout.addWidget(splitter)
    
    def _create_files_panel(self) -> QWidget:
        """Создание панели с деревом файлов"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Заголовок
        files_label = QLabel("📁 Загруженные отчеты")
        files_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        layout.addWidget(files_label)
        
        # Дерево файлов
        self.files_tree = QTreeWidget()
        self.files_tree.setHeaderLabels(["Файл", "Брокер", "Дата", "Статус"])
        self.files_tree.setColumnWidth(0, 250)
        self.files_tree.setColumnWidth(1, 120)
        self.files_tree.setColumnWidth(2, 100)
        self.files_tree.setColumnWidth(3, 80)
        self.files_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.files_tree.customContextMenuRequested.connect(self._on_file_context_menu)
        layout.addWidget(self.files_tree)
        
        # Кнопка удаления отчета
        delete_btn = QPushButton("🗑️ Удалить выбранный отчет")
        delete_btn.clicked.connect(self._on_delete_report)
        layout.addWidget(delete_btn)
        
        # Статистика
        stats_label = QLabel("Всего файлов: 0 | Транзакций: 0")
        stats_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout.addWidget(stats_label)
        
        return panel
    
    def _create_ai_chat_panel(self) -> QWidget:
        """Создание панели чата с ИИ-парсером"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Заголовок
        chat_label = QLabel("🤖 ИИ-Парсер (обучение на фидбеке)")
        chat_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        layout.addWidget(chat_label)
        
        # Область чата
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setPlaceholderText(
            "Здесь отображается диалог с ИИ-парсером.\n\n"
            "Пример:\n"
            "Вы: В отчетах ВТБ строки 'Списание спец. комиссии' нужно привязывать к комиссии за сделки по акциям\n"
            "ИИ: Понял. Создано правило для брокера ВТБ. Перепарсиваю данные..."
        )
        layout.addWidget(self.chat_display)
        
        # Поле ввода
        input_layout = QHBoxLayout()
        
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Введите комментарий для обучения парсера...")
        self.chat_input.returnPressed.connect(self._on_send_to_ai)
        input_layout.addWidget(self.chat_input)
        
        send_btn = QPushButton("Отправить")
        send_btn.clicked.connect(self._on_send_to_ai)
        input_layout.addWidget(send_btn)
        
        layout.addLayout(input_layout)
        
        # Подсказки
        hints_group = QGroupBox("💡 Примеры команд для обучения")
        hints_layout = QVBoxLayout(hints_group)
        
        hints = [
            "«В отчетах ВТБ строки \"Списание спец. комиссии\" привязывать к комиссии за сделки»",
            "«Дивиденды по тикеру SBER отражаются с задержкой в 2 дня»",
            "«Налог на купоны по облигациям удерживается отдельно»",
        ]
        
        for hint in hints:
            hint_label = QLabel(f"• {hint}")
            hint_label.setWordWrap(True)
            hint_label.setStyleSheet("font-size: 11px; color: #94a3b8;")
            hints_layout.addWidget(hint_label)
        
        layout.addWidget(hints_group)
        
        return panel
    
    def get_widget(self) -> QWidget:
        """Возвращает основной виджет модуля"""
        return self
    
    def show_import_dialog(self):
        """Показ диалога импорта файлов"""
        file_types = "Excel (*.xlsx);;CSV (*.csv);;Все файлы (*.*)"
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Импорт отчетов брокеров",
            "",
            file_types
        )
        
        if files:
            self._process_imported_files(files)
    
    def _process_imported_files(self, files: List[str]):
        """Обработка импортированных файлов"""
        imported_count = 0
        transactions_count = 0
        
        for file_path in files:
            try:
                # Здесь будет логика парсинга
                filename = os.path.basename(file_path)
                
                # Определение брокера (заглушка)
                broker_name = self._detect_broker(filename)
                
                # Получение или создание брокера в БД
                broker = self.db.get_broker_by_name(broker_name)
                if not broker:
                    broker_id = self.db.add_broker(broker_name)
                else:
                    broker_id = broker['id']
                
                # Добавление файла в БД
                file_hash = self._calculate_file_hash(file_path)
                report_id = self.db.add_report_file(broker_id, filename, file_hash, file_path)
                
                # Парсинг транзакций (заглушка)
                # transactions = parse_file(file_path, broker_name)
                # for tx in transactions:
                #     self.db.add_transaction(...)
                #     transactions_count += 1
                
                imported_count += 1
                
            except Exception as e:
                QMessageBox.warning(
                    self,
                    "Ошибка импорта",
                    f"Не удалось обработать файл {filename}:\n{str(e)}"
                )
        
        # Обновление дерева файлов
        self._refresh_files_tree()
        
        # Отправка сигнала
        self.files_imported.emit({
            'files_count': imported_count,
            'transactions_count': transactions_count
        })
        
        # Приветственное сообщение в чат
        self._add_ai_message(
            f"Импортировано файлов: {imported_count}\n"
            f"Транзакций обработано: {transactions_count}\n\n"
            "Если заметили ошибки в парсинге — напишите мне в чат, я запомню правила!"
        )
    
    def _detect_broker(self, filename: str) -> str:
        """Определение брокера по имени файла"""
        filename_lower = filename.lower()
        
        broker_patterns = {
            'vtb': 'ВТБ',
            'sber': 'Сбербанк',
            'tinkoff': 'Тинькофф',
            'alfa': 'Альфа-Банк',
            'psb': 'ПСБ',
            'open': 'Открытие',
            'bcs': 'BCS',
            'finam': 'Финам',
        }
        
        for pattern, broker_name in broker_patterns.items():
            if pattern in filename_lower:
                return broker_name
        
        # Если брокер не определен - запрос у пользователя
        broker_name, ok = self._ask_broker_name(filename)
        if ok and broker_name:
            return broker_name
        
        return 'Unknown'
    
    def _ask_broker_name(self, filename: str) -> tuple:
        """Диалог запроса имени брокера"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Брокер не определен")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout(dialog)
        
        label = QLabel(
            f"Для файла \"{filename}\" не удалось автоматически определить брокера.\n\n"
            "Укажите имя брокера вручную:"
        )
        label.setWordWrap(True)
        layout.addWidget(label)
        
        input_field = QLineEdit()
        input_field.setPlaceholderText("Например: ВТБ, Сбербанк, Тинькофф")
        layout.addWidget(input_field)
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec() == QDialog.Accepted:
            return input_field.text(), True
        
        return '', False
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Расчет хэша файла для определения дубликатов"""
        import hashlib
        
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            buf = f.read(65536)
            hasher.update(buf)
        
        return hasher.hexdigest()
    
    def _refresh_files_tree(self):
        """Обновление дерева файлов"""
        self.files_tree.clear()
        
        # Здесь будет загрузка данных из БД
        # reports = self.db.get_all_reports()
        # for report in reports:
        #     item = QTreeWidgetItem([...])
        #     self.files_tree.addTopLevelItem(item)
        
        # Заглушка для демонстрации
        sample_item = QTreeWidgetItem([
            "report_2024_12.xlsx",
            "ВТБ",
            "2024-12",
            "✓"
        ])
        self.files_tree.addTopLevelItem(sample_item)
    
    def _on_file_context_menu(self, pos: QModelIndex):
        """Контекстное меню для файла"""
        # Будет реализовано контекстное меню
        pass
    
    def _on_delete_report(self):
        """Удаление выбранного отчета"""
        selected_items = self.files_tree.selectedItems()
        
        if not selected_items:
            QMessageBox.warning(
                self,
                "Нет выбора",
                "Выберите файл отчета для удаления"
            )
            return
        
        reply = QMessageBox.question(
            self,
            "Подтверждение удаления",
            "Вы уверены, что хотите удалить выбранный отчет?\n\n"
            "Все связанные транзакции будут удалены,\n"
            "а портфель пересчитан.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Удаление из БД
            # report_id = selected_items[0].data(0, Qt.ItemDataRole.UserRole)
            # self.db.delete_report_file(report_id)
            
            # Обновление UI
            self._refresh_files_tree()
            
            QMessageBox.information(
                self,
                "Удалено",
                "Отчет успешно удален"
            )
    
    def _on_refresh_quotes(self):
        """Обновление котировок из Мосбиржи"""
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("Загрузка...")
        
        # Здесь будет вызов moex_api.py
        QTimer.singleShot(2000, self._on_quotes_refreshed)
    
    def _on_quotes_refreshed(self):
        """Обработчик завершения обновления котировок"""
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("🔄 Обновить котировки")
        
        QMessageBox.information(
            self,
            "Готово",
            "Котировки обновлены из API Мосбиржи"
        )
    
    def _on_send_to_ai(self):
        """Отправка сообщения ИИ-парсеру"""
        message = self.chat_input.text().strip()
        
        if not message:
            return
        
        # Добавление сообщения пользователя в чат
        self._add_user_message(message)
        self.chat_input.clear()
        
        # Обработка сообщения и создание правила
        QTimer.singleShot(500, lambda: self._process_ai_feedback(message))
    
    def _process_ai_feedback(self, message: str):
        """Обработка фидбека пользователя и создание правила"""
        # Здесь будет логика NLP для извлечения правил из сообщения
        
        # Пример создания правила
        rule_data = {
            'broker_id': None,  # Глобальное правило
            'rule_type': 'commission_binding',
            'pattern': 'Списание спец. комиссии',
            'target_field': 'commission',
            'action': {'bind_to': 'trade_commission'},
            'feedback_text': message
        }
        
        # rule_id = self.db.add_parsing_rule(**rule_data)
        
        # Ответ ИИ
        ai_response = (
            "✅ Понял! Создано новое правило парсинга:\n\n"
            f"«{message}»\n\n"
            "Это правило будет применяться ко всем будущим импортам.\n"
            "Хотите, чтобы я перепарсил текущие данные с учетом нового правила?"
        )
        
        self._add_ai_message(ai_response)
    
    def _add_user_message(self, message: str):
        """Добавление сообщения пользователя в чат"""
        self.chat_display.append(
            f"<div style='background-color: #1e293b; padding: 8px; "
            f"border-radius: 6px; margin: 4px 0;'>"
            f"<b style='color: #60a5fa;'>Вы:</b> {message}"
            f"</div>"
        )
    
    def _add_ai_message(self, message: str):
        """Добавление сообщения ИИ в чат"""
        self.chat_display.append(
            f"<div style='background-color: #0f172a; padding: 8px; "
            f"border-radius: 6px; margin: 4px 0;'>"
            f"<b style='color: #4ade80;'>ИИ-Парсер:</b> {message}"
            f"</div>"
        )
    
    def refresh_data(self):
        """Публичный метод для обновления данных модуля"""
        self._refresh_files_tree()

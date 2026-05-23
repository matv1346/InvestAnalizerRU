"""
ui/ai_advisor_module.py - ИИ-Советник и калькулятор ребалансировки
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSplitter, QTextEdit, QGroupBox, QComboBox, QDoubleSpinBox,
    QScrollArea, QFrame, QMessageBox, QProgressBar, QListWidget,
    QListWidgetItem, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal, pyqtSlot, Qt, QTimer
from PyQt6.QtGui import QFont

# Алиас для совместимости
Signal = pyqtSignal
Slot = pyqtSlot

from database import Database


class AIAdvisorModule(QWidget):
    """Модуль ИИ-советника с рекомендациями и калькулятором ребалансировки"""
    
    rebalance_calculated = Signal(dict)
    
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
        
        title_label = QLabel("🤖 ИИ-Советник")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Кнопка обновления рекомендаций
        refresh_btn = QPushButton("🔄 Обновить анализ")
        refresh_btn.clicked.connect(self._on_refresh_analysis)
        header_layout.addWidget(refresh_btn)
        
        main_layout.addLayout(header_layout)
        
        # Основной сплиттер
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Левая панель - Рекомендации ИИ
        left_panel = self._create_recommendations_panel()
        splitter.addWidget(left_panel)
        
        # Правая панель - Калькулятор ребалансировки
        right_panel = self._create_rebalance_calculator_panel()
        splitter.addWidget(right_panel)
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([500, 500])
        
        main_layout.addWidget(splitter)
    
    def _create_recommendations_panel(self) -> QWidget:
        """Создание панели рекомендаций ИИ"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Заголовок
        rec_label = QLabel("💡 Инвестиционные рекомендации")
        rec_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        layout.addWidget(rec_label)
        
        # Список рекомендаций
        self.recommendations_list = QListWidget()
        self.recommendations_list.setStyleSheet("""
            QListWidget {
                background-color: #0f172a;
                border: 1px solid #334155;
                border-radius: 8px;
            }
            QListWidget::item {
                padding: 12px;
                border-bottom: 1px solid #1e293b;
                border-radius: 4px;
                margin: 2px;
            }
            QListWidget::item:hover {
                background-color: #1e293b;
            }
            QListWidget::item:selected {
                background-color: #3b82f6;
            }
        """)
        layout.addWidget(self.recommendations_list)
        
        # Детали выбранной рекомендации
        details_group = QGroupBox("📋 Детали рекомендации")
        details_layout = QVBoxLayout(details_group)
        
        self.recommendation_details = QTextEdit()
        self.recommendation_details.setReadOnly(True)
        self.recommendation_details.setPlaceholderText(
            "Выберите рекомендацию из списка для просмотра деталей"
        )
        details_layout.addWidget(self.recommendation_details)
        
        layout.addWidget(details_group)
        
        # Кнопки действий
        buttons_layout = QHBoxLayout()
        
        dismiss_btn = QPushButton("❌ Отклонить")
        dismiss_btn.clicked.connect(self._on_dismiss_recommendation)
        buttons_layout.addWidget(dismiss_btn)
        
        implement_btn = QPushButton("✅ Принять к исполнению")
        implement_btn.clicked.connect(self._on_implement_recommendation)
        buttons_layout.addWidget(implement_btn)
        
        layout.addLayout(buttons_layout)
        
        return panel
    
    def _create_rebalance_calculator_panel(self) -> QWidget:
        """Создание панели калькулятора ребалансировки"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Заголовок
        calc_label = QLabel("🧮 Калькулятор ребалансировки")
        calc_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        layout.addWidget(calc_label)
        
        # Параметры ввода
        params_group = QGroupBox("⚙️ Параметры")
        params_layout = QVBoxLayout(params_group)
        
        # Сумма новых инвестиций
        input_layout_1 = QHBoxLayout()
        input_layout_1.addWidget(QLabel("💰 Сумма новых инвестиций (₽):"))
        self.investment_amount = QDoubleSpinBox()
        self.investment_amount.setMaximum(1000000000)
        self.investment_amount.setValue(50000)
        self.investment_amount.setStyleSheet("font-size: 14px; font-weight: bold;")
        input_layout_1.addWidget(self.investment_amount)
        params_layout.addLayout(input_layout_1)
        
        # Риск-профиль
        input_layout_2 = QHBoxLayout()
        input_layout_2.addWidget(QLabel("🎯 Риск-профиль:"))
        self.risk_profile = QComboBox()
        self.risk_profile.addItems([
            "Консервативный (облигации 70%, акции 30%)",
            "Умеренный (облигации 50%, акции 50%)",
            "Агрессивный (облигации 20%, акции 80%)"
        ])
        self.risk_profile.setStyleSheet("font-size: 13px;")
        input_layout_2.addWidget(self.risk_profile)
        params_layout.addLayout(input_layout_2)
        
        layout.addWidget(params_group)
        
        # Кнопка расчета
        calculate_btn = QPushButton("🔨 Рассчитать ребалансировку")
        calculate_btn.setMinimumHeight(50)
        calculate_btn.setStyleSheet("font-size: 14px; font-weight: bold;")
        calculate_btn.clicked.connect(self._on_calculate_rebalance)
        layout.addWidget(calculate_btn)
        
        # Прогресс бар расчета
        self.calc_progress = QProgressBar()
        self.calc_progress.setVisible(False)
        self.calc_progress.setTextVisible(False)
        self.calc_progress.setMaximumHeight(8)
        layout.addWidget(self.calc_progress)
        
        # Результаты расчета
        results_group = QGroupBox("📊 Рекомендуемые сделки")
        results_layout = QVBoxLayout(results_group)
        
        self.trades_list = QTextEdit()
        self.trades_list.setReadOnly(True)
        self.trades_list.setPlaceholderText(
            "Здесь появится пошаговый план закупки после расчета"
        )
        self.trades_list.setStyleSheet("""
            QTextEdit {
                background-color: #0f172a;
                border: 1px solid #334155;
                border-radius: 8px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                line-height: 1.6;
            }
        """)
        results_layout.addWidget(self.trades_list)
        
        # Сводка
        summary_layout = QHBoxLayout()
        
        self.total_invested_label = QLabel("Вложено: 0 ₽")
        summary_layout.addWidget(self.total_invested_label)
        
        summary_layout.addStretch()
        
        self.remaining_cash_label = label = QLabel("Остаток: 0 ₽")
        summary_layout.addWidget(self.remaining_cash_label)
        
        results_layout.addLayout(summary_layout)
        
        layout.addWidget(results_group)
        
        # Пояснение ИИ
        explanation_group = QGroupBox("🤖 Обоснование от ИИ")
        explanation_layout = QVBoxLayout(explanation_group)
        
        self.ai_explanation = QTextEdit()
        self.ai_explanation.setReadOnly(True)
        self.ai_explanation.setPlaceholderText(
            "ИИ объяснит логику рекомендуемой ребалансировки"
        )
        self.ai_explanation.setMaximumHeight(150)
        explanation_layout.addWidget(self.ai_explanation)
        
        layout.addWidget(explanation_group)
        
        return panel
    
    def get_widget(self) -> QWidget:
        """Возвращает основной виджет модуля"""
        return self
    
    def refresh_data(self):
        """Обновление данных модуля"""
        self._load_recommendations()
    
    def _load_recommendations(self):
        """Загрузка рекомендаций ИИ"""
        self.recommendations_list.clear()
        
        # Здесь будет загрузка из БД
        # recommendations = self.db.get_active_recommendations()
        
        # Заглушка для демонстрации
        sample_recommendations = [
            {
                'id': 1,
                'type': 'risk_alert',
                'priority': 'high',
                'title': '⚠️ Высокая концентрация в одном активе',
                'description': 'ЕвроТранс занимает 40.27% вашего портфеля'
            },
            {
                'id': 2,
                'type': 'diversification',
                'priority': 'medium',
                'title': '🎯 Рекомендуется диверсификация',
                'description': 'Добавьте экспозицию на технологический сектор'
            },
            {
                'id': 3,
                'type': 'tax_optimization',
                'priority': 'low',
                'title': '💰 Налоговая оптимизация',
                'description': 'Рассмотрите продажу убыточных позиций для налогового вычета'
            }
        ]
        
        for rec in sample_recommendations:
            item = QListWidgetItem(f"{rec['title']}\n{rec['description']}")
            item.setData(Qt.ItemDataRole.UserRole, rec)
            
            # Цветовая кодировка приоритета
            if rec['priority'] == 'high':
                item.setBackground(QColor("#8B0000"))
            elif rec['priority'] == 'medium':
                item.setBackground(QColor("#FFD700"))
            
            self.recommendations_list.addItem(item)
    
    def _on_refresh_analysis(self):
        """Обновление анализа портфеля"""
        QMessageBox.information(
            self,
            "Анализ",
            "ИИ-агент сканирует ваш портфель...\n"
            "Анализ рисков, диверсификации и рыночных трендов."
        )
        
        self._load_recommendations()
    
    def _on_dismiss_recommendation(self):
        """Отклонение рекомендации"""
        selected_items = self.recommendations_list.selectedItems()
        
        if not selected_items:
            QMessageBox.warning(
                self,
                "Нет выбора",
                "Выберите рекомендацию для отклонения"
            )
            return
        
        # Удаление из списка
        for item in selected_items:
            row = self.recommendations_list.row(item)
            self.recommendations_list.takeItem(row)
        
        QMessageBox.information(
            self,
            "Отклонено",
            "Рекомендация отклонена и не будет показываться снова"
        )
    
    def _on_implement_recommendation(self):
        """Принятие рекомендации к исполнению"""
        selected_items = self.recommendations_list.selectedItems()
        
        if not selected_items:
            QMessageBox.warning(
                self,
                "Нет выбора",
                "Выберите рекомендацию для исполнения"
            )
            return
        
        rec_data = selected_items[0].data(Qt.ItemDataRole.UserRole)
        
        QMessageBox.information(
            self,
            "Принято",
            f"Рекомендация '{rec_data['title']}' принята к исполнению\n\n"
            "Следуйте шагам в калькуляторе ребалансировки"
        )
    
    def _on_calculate_rebalance(self):
        """Расчет ребалансировки портфеля"""
        amount = self.investment_amount.value()
        risk_profile = self.risk_profile.currentText()
        
        # Показ прогресса
        self.calc_progress.setVisible(True)
        self.calc_progress.setValue(0)
        
        # Имитация расчета
        QTimer.singleShot(500, lambda: self.calc_progress.setValue(25))
        QTimer.singleShot(1000, lambda: self.calc_progress.setValue(50))
        QTimer.singleShot(1500, lambda: self.calc_progress.setValue(75))
        QTimer.singleShot(2000, self._show_rebalance_results)
    
    def _show_rebalance_results(self):
        """Показ результатов расчета ребалансировки"""
        self.calc_progress.setVisible(False)
        
        amount = self.investment_amount.value()
        
        # Пример результата расчета
        result_text = f"""
╔═══════════════════════════════════════════════════╗
║       ПЛАН РЕБАЛАНСИРОВКИ ПОРТФЕЛЯ               ║
╚═══════════════════════════════════════════════════╝

💰 Сумма инвестиций: {amount:,.0f} ₽
🎯 Профиль: {self.risk_profile.currentText().split(' ')[0]}

─────────────────────────────────────────────────────

📋 ПОШАГОВЫЙ ПЛАН ЗАКУПКИ:

1️⃣ Купить SBER — 2 лота (примерно 6 200 ₽)
   └─ Обоснование: доведение доли акций до целевых 15%

2️⃣ Купить ОФЗ 26243 — 40 шт. (примерно 38 000 ₽)
   └─ Обоснование: размытие концентрации транспортного сектора

3️⃣ Купить VTBX — 5 лотов (примерно 5 800 ₽)
   └─ Обоснование: экспозиция на технологический сектор

─────────────────────────────────────────────────────

💵 ИТОГО ВЛОЖЕНО: 50 000 ₽
💵 ОСТАТОК: 0 ₽

⚠️ Рекомендация: парковать свободные средства в фонд ликвидности LQDT
"""
        
        self.trades_list.setText(result_text)
        
        self.total_invested_label.setText(f"Вложено: {amount:,.0f} ₽")
        self.remaining_cash_label.setText("Остаток: 0 ₽")
        
        # Объяснение от ИИ
        ai_text = f"""
🤖 <b>Обоснование стратегии ребалансировки:</b>

Текущий анализ показывает высокую концентрацию в транспортном секторе 
(ЕвроТранс ~40%). Предложенная стратегия направлена на:

✓ <b>Снижение рисков:</b> Диверсификация по секторам экономики
✓ <b>Защита капитала:</b> Добавление ОФЗ с текущей доходностью к погашению ~14%
✓ <b>Рост потенциала:</b> Экспозиция на технологический сектор через VTBX

При выбранном риск-профиле "{self.risk_profile.currentText().split(' ')[0]}" 
рекомендуемая структура: 50% облигации / 50% акции.

Данная ребалансировка приблизит ваш портфель к целевой аллокации 
и снизит волатильность без существенного снижения ожидаемой доходности.
"""
        
        self.ai_explanation.setText(ai_text)
        
        # Отправка сигнала
        self.rebalance_calculated.emit({
            'amount': amount,
            'risk_profile': risk_profile,
            'trades': []
        })

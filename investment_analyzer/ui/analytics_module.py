"""
ui/analytics_module.py - Аналитика и конструктор отчетов
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QGroupBox, QComboBox, QCheckBox, QScrollArea,
    QFrame, QMessageBox, QFileDialog, QGridLayout, QSpacerItem,
    QSizePolicy
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont

from database import Database


class AnalyticsModule(QWidget):
    """Модуль аналитики с конструктором дашбордов и экспортом"""
    
    export_requested = Signal()
    
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
        
        title_label = QLabel("📈 Аналитика и отчеты")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Кнопка экспорта
        export_btn = QPushButton("📤 Экспорт отчета")
        export_btn.clicked.connect(self._on_export)
        header_layout.addWidget(export_btn)
        
        # Кнопка сохранения дашборда
        save_dashboard_btn = QPushButton("💾 Сохранить дашборд")
        save_dashboard_btn.clicked.connect(self._on_save_dashboard)
        header_layout.addWidget(save_dashboard_btn)
        
        main_layout.addLayout(header_layout)
        
        # Вкладки аналитики
        self.analytics_tabs = QTabWidget()
        
        # Вкладка 1: Сводная аналитика
        summary_tab = self._create_summary_tab()
        self.analytics_tabs.addTab(summary_tab, "📊 Сводная")
        
        # Вкладка 2: Конструктор графиков
        builder_tab = self._create_chart_builder_tab()
        self.analytics_tabs.addTab(builder_tab, "🛠️ Конструктор")
        
        # Вкладка 3: Структура портфеля
        structure_tab = self._create_structure_tab()
        self.analytics_tabs.addTab(structure_tab, "🎯 Структура")
        
        main_layout.addWidget(self.analytics_tabs)
    
    def _create_summary_tab(self) -> QWidget:
        """Создание вкладки сводной аналитики"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Карточки с ключевыми метриками
        metrics_layout = QGridLayout()
        
        # Общая стоимость портфеля
        total_value_card = self._create_metric_card(
            "💰 Общая стоимость",
            "0 ₽",
            "#3b82f6"
        )
        metrics_layout.addWidget(total_value_card, 0, 0)
        
        # P&L
        pnl_card = self._create_metric_card(
            "📊 P&L",
            "0 ₽ (0%)",
            "#4ade80"
        )
        metrics_layout.addWidget(pnl_card, 0, 1)
        
        # XIRR
        xirr_card = self._create_metric_card(
            "📈 XIRR",
            "0%",
            "#f59e0b"
        )
        metrics_layout.addWidget(xirr_card, 0, 2)
        
        # Количество активов
        assets_card = self._create_metric_card(
            "🎯 Активов",
            "0",
            "#8b5cf6"
        )
        metrics_layout.addWidget(assets_card, 0, 3)
        
        layout.addLayout(metrics_layout)
        
        # График доходности (заглушка)
        chart_group = QGroupBox("📈 График доходности портфеля")
        chart_layout = QVBoxLayout(chart_group)
        
        chart_placeholder = QLabel(
            "Здесь будет график доходности\n"
            "(используется pyqtgraph или QtWebEngine + ApexCharts)"
        )
        chart_placeholder.setAlignment(Qt.AlignCenter)
        chart_placeholder.setMinimumHeight(300)
        chart_placeholder.setStyleSheet(
            "background-color: #0f172a; border-radius: 8px; color: #94a3b8;"
        )
        chart_layout.addWidget(chart_placeholder)
        
        layout.addWidget(chart_group)
        
        # Таблица по секторам
        sectors_group = QGroupBox("🏭 Распределение по секторам")
        sectors_layout = QVBoxLayout(sectors_group)
        
        sectors_placeholder = QLabel("Данные о секторах будут загружены из API Мосбиржи")
        sectors_placeholder.setAlignment(Qt.AlignCenter)
        sectors_placeholder.setMinimumHeight(150)
        sectors_layout.addWidget(sectors_placeholder)
        
        layout.addWidget(sectors_group)
        
        return widget
    
    def _create_chart_builder_tab(self) -> QWidget:
        """Создание вкладки конструктора графиков"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Панель настроек графика
        settings_group = QGroupBox("⚙️ Параметры графика")
        settings_layout = QGridLayout(settings_group)
        
        # Тип графика
        settings_layout.addWidget(QLabel("Тип графика:"), 0, 0)
        self.chart_type_combo = QComboBox()
        self.chart_type_combo.addItems([
            "Линейный (Line)",
            "Столбчатый (Bar)",
            "Круговой (Donut)",
            "Свечной (Candlestick)",
            "Область (Area)",
            "Точечный (Scatter)"
        ])
        settings_layout.addWidget(self.chart_type_combo, 0, 1)
        
        # Ось X
        settings_layout.addWidget(QLabel("Ось X:"), 1, 0)
        self.x_axis_combo = QComboBox()
        self.x_axis_combo.addItems(["Дата", "Время", "Категория"])
        settings_layout.addWidget(self.x_axis_combo, 1, 1)
        
        # Ось Y
        settings_layout.addWidget(QLabel("Ось Y:"), 2, 0)
        self.y_axis_combo = QComboBox()
        self.y_axis_combo.addItems([
            "Стоимость", "Доходность", "Количество",
            "Дивиденды", "Купоны", "Комиссии"
        ])
        settings_layout.addWidget(self.y_axis_combo, 2, 1)
        
        # Фильтры по тикерам
        settings_layout.addWidget(QLabel("Тикеры:"), 3, 0)
        tickers_widget = QWidget()
        tickers_layout = QHBoxLayout(tickers_widget)
        tickers_layout.setContentsMargins(0, 0, 0, 0)
        
        self.ticker_sber = QCheckBox("SBER")
        self.ticker_gazp = QCheckBox("GAZP")
        self.ticker_lkoh = QCheckBox("LKOH")
        self.ticker_all = QCheckBox("Все")
        self.ticker_all.setChecked(True)
        
        tickers_layout.addWidget(self.ticker_sber)
        tickers_layout.addWidget(self.ticker_gazp)
        tickers_layout.addWidget(self.ticker_lkoh)
        tickers_layout.addWidget(self.ticker_all)
        tickers_layout.addStretch()
        
        settings_layout.addWidget(tickers_widget, 3, 1)
        
        # Период
        settings_layout.addWidget(QLabel("Период:"), 4, 0)
        period_combo = QComboBox()
        period_combo.addItems([
            "За всё время",
            "За месяц",
            "За квартал",
            "За год",
            "Пользовательский"
        ])
        settings_layout.addWidget(period_combo, 4, 1)
        
        layout.addWidget(settings_group)
        
        # Кнопки действий
        buttons_layout = QHBoxLayout()
        
        build_btn = QPushButton("🔨 Построить график")
        build_btn.clicked.connect(self._on_build_chart)
        buttons_layout.addWidget(build_btn)
        
        buttons_layout.addStretch()
        
        layout.addLayout(buttons_layout)
        
        # Область предпросмотра
        preview_group = QGroupBox("👁️ Предпросмотр")
        preview_layout = QVBoxLayout(preview_group)
        
        preview_placeholder = QLabel(
            "Здесь появится предпросмотр графика\n"
            "после нажатия кнопки 'Построить график'"
        )
        preview_placeholder.setAlignment(Qt.AlignCenter)
        preview_placeholder.setMinimumHeight(350)
        preview_placeholder.setStyleSheet(
            "background-color: #0f172a; border-radius: 8px; color: #94a3b8;"
        )
        preview_layout.addWidget(preview_placeholder)
        
        layout.addWidget(preview_group)
        
        return widget
    
    def _create_structure_tab(self) -> QWidget:
        """Создание вкладки структуры портфеля"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Круговая диаграмма распределения
        allocation_group = QGroupBox("🎯 Распределение активов")
        allocation_layout = QVBoxLayout(allocation_group)
        
        allocation_placeholder = QLabel(
            "Круговая диаграмма распределения\n"
            "по классам активов / секторам / брокерам"
        )
        allocation_placeholder.setAlignment(Qt.AlignCenter)
        allocation_placeholder.setMinimumHeight(300)
        allocation_placeholder.setStyleSheet(
            "background-color: #0f172a; border-radius: 8px; color: #94a3b8;"
        )
        allocation_layout.addWidget(allocation_placeholder)
        
        layout.addWidget(allocation_group)
        
        # Детализация по брокерам
        brokers_group = QGroupBox("🏦 Детализация по брокерам")
        brokers_layout = QVBoxLayout(brokers_group)
        
        brokers_placeholder = QLabel("Таблица с детализацией по каждому брокеру")
        brokers_placeholder.setAlignment(Qt.AlignCenter)
        brokers_placeholder.setMinimumHeight(200)
        brokers_layout.addWidget(brokers_placeholder)
        
        layout.addWidget(brokers_group)
        
        return widget
    
    def _create_metric_card(self, title: str, value: str, color: str) -> QFrame:
        """Создание карточки метрики"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #0f172a;
                border-radius: 12px;
                border-left: 4px solid {color};
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        layout.addWidget(title_label)
        
        value_label = QLabel(value)
        value_label.setStyleSheet(f"color: {color}; font-size: 24px; font-weight: bold;")
        layout.addWidget(value_label)
        
        return card
    
    def get_widget(self) -> QWidget:
        """Возвращает основной виджет модуля"""
        return self
    
    def refresh_data(self):
        """Обновление данных аналитики"""
        # Здесь будет загрузка актуальных данных
        pass
    
    def _on_build_chart(self):
        """Построение графика"""
        # Сбор параметров
        chart_type = self.chart_type_combo.currentText()
        x_axis = self.x_axis_combo.currentText()
        y_axis = self.y_axis_combo.currentText()
        
        # Логика построения графика
        QMessageBox.information(
            self,
            "График построен",
            f"Параметры:\nТип: {chart_type}\nX: {x_axis}\nY: {y_axis}"
        )
    
    def _on_save_dashboard(self):
        """Сохранение пользовательского дашборда"""
        dashboard_name, ok = QInputDialog.getText(
            self,
            "Сохранение дашборда",
            "Введите имя дашборда:"
        )
        
        if ok and dashboard_name:
            # Сохранение в БД
            config = {
                'name': dashboard_name,
                'charts': [],
                'filters': {}
            }
            
            # self.db.save_custom_dashboard(dashboard_name, config)
            
            QMessageBox.information(
                self,
                "Сохранено",
                f"Дашборд '{dashboard_name}' сохранен"
            )
    
    def _on_export(self):
        """Экспорт отчета"""
        file_types = "PDF (*.pdf);;Excel (*.xlsx);;CSV (*.csv)"
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Экспорт аналитического отчета",
            "",
            file_types
        )
        
        if file_path:
            self.export_requested.emit()
            QMessageBox.information(
                self,
                "Экспорт",
                f"Отчет экспортирован в:\n{file_path}"
            )


# Импорт для диалога ввода текста
from PySide6.QtWidgets import QInputDialog

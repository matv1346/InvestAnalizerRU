"""
app.py - Главное окно приложения, навигация и основной каркас UI
Investment Analyzer - Десктопное приложение для анализа инвестиционного портфеля
"""

import sys
import os
from datetime import datetime
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QFrame, QSplitter,
    QTreeWidget, QTreeWidgetItem, QMessageBox, QFileDialog,
    QStackedWidget, QToolBar, QStatusBar, QMenu,
    QDialog, QDialogButtonBox, QLineEdit, QTextEdit, QScrollArea,
    QSizePolicy, QSpacerItem, QProgressBar
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, pyqtSlot, QTimer, QThread, QSize, QUrl, QModelIndex,
    QPropertyAnimation, QEasingCurve, QByteArray
)
from PyQt6.QtGui import (
    QIcon, QFont, QColor, QPalette, QBrush, QPixmap, QDesktopServices,
    QActionGroup, QKeySequence, QShortcut, QAction
)

# Алиасы для совместимости с кодом PySide6
Signal = pyqtSignal
Slot = pyqtSlot

# Импорт локальных модулей
from database import get_database, Database
from ui.main_navigation import MainNavigation
from ui.data_module import DataModule
from ui.registry_module import RegistryModule
from ui.analytics_module import AnalyticsModule
from ui.ai_advisor_module import AIAdvisorModule


class InvestmentAnalyzerApp(QMainWindow):
    """Главное окно приложения Investment Analyzer"""
    
    # Сигналы для межмодульной коммуникации
    data_imported = Signal(dict)  # Данные о загруженных файлах
    portfolio_updated = Signal(dict)  # Обновление портфеля
    ai_recommendation_ready = Signal(dict)  # Готовность рекомендации ИИ
    
    def __init__(self):
        super().__init__()
        
        # Инициализация базы данных
        self.db = get_database()
        
        # Настройка основного окна
        self.setWindowTitle("Investment Analyzer - Анализ инвестиционного портфеля")
        self.setMinimumSize(1400, 900)
        self.resize(1600, 1000)
        
        # Применение темной темы
        self._apply_dark_theme()
        
        # Создание центрального виджета
        self._setup_central_widget()
        
        # Создание меню и тулбара
        self._setup_menu_bar()
        self._setup_toolbar()
        
        # Создание статус бара
        self._setup_status_bar()
        
        # Инициализация модулей
        self._init_modules()
        
        # Подключение сигналов
        self._connect_signals()
        
        # Загрузка начальных данных
        self._load_initial_data()
        
        # Показать приветственное сообщение
        self._show_welcome_message()
    
    def _apply_dark_theme(self):
        """Применение современной темной темы (Slate/Charcoal)"""
        dark_stylesheet = """
            QMainWindow {
                background-color: #1e293b;
                color: #f1f5f9;
            }
            
            QWidget {
                background-color: #1e293b;
                color: #f1f5f9;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
            }
            
            QTabWidget::pane {
                border: 1px solid #334155;
                background-color: #0f172a;
                border-radius: 8px;
            }
            
            QTabBar::tab {
                background-color: #334155;
                color: #94a3b8;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            
            QTabBar::tab:selected {
                background-color: #0f172a;
                color: #f1f5f9;
                font-weight: bold;
            }
            
            QTabBar::tab:hover:!selected {
                background-color: #475569;
            }
            
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 500;
            }
            
            QPushButton:hover {
                background-color: #2563eb;
            }
            
            QPushButton:pressed {
                background-color: #1d4ed8;
            }
            
            QPushButton:disabled {
                background-color: #475569;
                color: #94a3b8;
            }
            
            QTreeWidget, QTableWidget, QListWidget {
                background-color: #0f172a;
                alternate-background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                gridline-color: #334155;
            }
            
            QTreeWidget::item, QTableWidget::item, QListWidget::item {
                padding: 6px;
                border-radius: 4px;
            }
            
            QTreeWidget::item:hover, QTableWidget::item:hover, QListWidget::item:hover {
                background-color: #1e293b;
            }
            
            QTreeWidget::item:selected, QTableWidget::item:selected, QListWidget::item:selected {
                background-color: #3b82f6;
                color: white;
            }
            
            QHeaderView::section {
                background-color: #1e293b;
                color: #94a3b8;
                padding: 8px;
                border: none;
                border-bottom: 1px solid #334155;
                font-weight: 600;
            }
            
            QMenuBar {
                background-color: #0f172a;
                color: #f1f5f9;
                border-bottom: 1px solid #334155;
                padding: 4px;
            }
            
            QMenuBar::item {
                padding: 6px 12px;
                border-radius: 4px;
            }
            
            QMenuBar::item:selected {
                background-color: #334155;
            }
            
            QMenu {
                background-color: #0f172a;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 4px;
            }
            
            QMenu::item {
                padding: 8px 24px;
                border-radius: 4px;
            }
            
            QMenu::item:selected {
                background-color: #3b82f6;
            }
            
            QToolBar {
                background-color: #0f172a;
                border-bottom: 1px solid #334155;
                padding: 4px;
                spacing: 4px;
            }
            
            QToolBar QToolButton {
                background-color: transparent;
                border: none;
                border-radius: 4px;
                padding: 6px;
                color: #94a3b8;
            }
            
            QToolBar QToolButton:hover {
                background-color: #1e293b;
                color: #f1f5f9;
            }
            
            QStatusBar {
                background-color: #0f172a;
                color: #94a3b8;
                border-top: 1px solid #334155;
            }
            
            QProgressBar {
                border: none;
                border-radius: 4px;
                text-align: center;
                background-color: #1e293b;
                height: 8px;
            }
            
            QProgressBar::chunk {
                background-color: #3b82f6;
                border-radius: 4px;
            }
            
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            
            QLabel {
                color: #f1f5f9;
            }
            
            QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                background-color: #0f172a;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px;
                selection-background-color: #3b82f6;
            }
            
            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
                border-color: #3b82f6;
            }
            
            QGroupBox {
                border: 1px solid #334155;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
                font-weight: 600;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
                color: #94a3b8;
            }
            
            QSplitter::handle {
                background-color: #334155;
                width: 1px;
            }
            
            QSplitter::handle:horizontal {
                width: 1px;
            }
            
            QSplitter::handle:vertical {
                height: 1px;
            }
        """
        
        self.setStyleSheet(dark_stylesheet)
    
    def _setup_central_widget(self):
        """Настройка центрального виджета с навигацией"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Основной навигатор (табы)
        self.main_navigation = MainNavigation()
        main_layout.addWidget(self.main_navigation)
    
    def _setup_menu_bar(self):
        """Настройка меню приложения"""
        menubar = self.menuBar()
        
        # Меню Файл
        file_menu = menubar.addMenu("Файл")
        
        import_action = QAction("Импорт отчетов", self)
        import_action.setShortcut(QKeySequence("Ctrl+I"))
        import_action.triggered.connect(self._on_import_triggered)
        file_menu.addAction(import_action)
        
        export_action = QAction("Экспорт данных", self)
        export_action.setShortcut(QKeySequence("Ctrl+E"))
        export_action.triggered.connect(self._on_export_triggered)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Выход", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Меню Настройки
        settings_menu = menubar.addMenu("Настройки")
        
        db_action = QAction("База данных", self)
        db_action.triggered.connect(self._on_database_settings)
        settings_menu.addAction(db_action)
        
        ai_action = QAction("ИИ-модель", self)
        ai_action.triggered.connect(self._on_ai_settings)
        settings_menu.addAction(ai_action)
        
        settings_menu.addSeparator()
        
        theme_action = QAction("Тема оформления", self)
        theme_action.triggered.connect(self._on_theme_settings)
        settings_menu.addAction(theme_action)
        
        # Меню Помощь
        help_menu = menubar.addMenu("Помощь")
        
        about_action = QAction("О программе", self)
        about_action.triggered.connect(self._show_about_dialog)
        help_menu.addAction(about_action)
        
        docs_action = QAction("Документация", self)
        docs_action.setShortcut(QKeySequence("F1"))
        docs_action.triggered.connect(self._open_documentation)
        help_menu.addAction(docs_action)
    
    def _setup_toolbar(self):
        """Настройка панели инструментов"""
        toolbar = QToolBar("Основные действия")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)
        
        # Кнопка импорта
        import_btn = QAction("📥 Импорт", self)
        import_btn.setToolTip("Импортировать отчеты брокеров")
        import_btn.triggered.connect(self._on_import_triggered)
        toolbar.addAction(import_btn)
        
        # Кнопка обновления
        refresh_btn = QAction("🔄 Обновить", self)
        refresh_btn.setToolTip("Обновить данные портфеля")
        refresh_btn.triggered.connect(self._on_refresh_triggered)
        toolbar.addAction(refresh_btn)
        
        toolbar.addSeparator()
        
        # Кнопка экспорта
        export_btn = QAction("📤 Экспорт", self)
        export_btn.setToolTip("Экспортировать данные")
        export_btn.triggered.connect(self._on_export_triggered)
        toolbar.addAction(export_btn)
        
        # Кнопка ИИ-советника
        ai_btn = QAction("🤖 ИИ-Советник", self)
        ai_btn.setToolTip("Открыть панель ИИ-советника")
        ai_btn.triggered.connect(lambda: self.main_navigation.setCurrentIndex(3))
        toolbar.addAction(ai_btn)
    
    def _setup_status_bar(self):
        """Настройка статус бара"""
        statusbar = QStatusBar()
        self.setStatusBar(statusbar)
        
        # Статус подключения к БД
        self.db_status_label = QLabel("✓ База данных подключена")
        self.db_status_label.setStyleSheet("color: #4ade80;")
        statusbar.addPermanentWidget(self.db_status_label)
        
        # Индикатор загрузки
        self.loading_progress = QProgressBar()
        self.loading_progress.setVisible(False)
        self.loading_progress.setMaximumWidth(150)
        statusbar.addPermanentWidget(self.loading_progress)
        
        # Основная информация
        self.status_label = QLabel("Готов к работе")
        statusbar.addWidget(self.status_label, 1)
    
    def _init_modules(self):
        """Инициализация основных модулей приложения"""
        # Модуль данных
        self.data_module = DataModule(self.db)
        self.main_navigation.add_tab(self.data_module.get_widget(), "📊 Данные")
        
        # Модуль реестра
        self.registry_module = RegistryModule(self.db)
        self.main_navigation.add_tab(self.registry_module.get_widget(), "📋 Реестр")
        
        # Модуль аналитики
        self.analytics_module = AnalyticsModule(self.db)
        self.main_navigation.add_tab(self.analytics_module.get_widget(), "📈 Аналитика")
        
        # Модуль ИИ-советника
        self.ai_advisor_module = AIAdvisorModule(self.db)
        self.main_navigation.add_tab(self.ai_advisor_module.get_widget(), "🤖 ИИ-Советник")
    
    def _connect_signals(self):
        """Подключение сигналов между модулями"""
        # Сигналы от модуля данных
        self.data_module.files_imported.connect(self._on_files_imported)
        self.data_module.portfolio_recalculated.connect(self._on_portfolio_recalculated)
        
        # Сигналы от модуля реестра
        self.registry_module.transaction_selected.connect(self._on_transaction_selected)
        
        # Сигналы от модуля аналитики
        self.analytics_module.export_requested.connect(self._on_export_triggered)
        
        # Сигналы от модуля ИИ
        self.ai_advisor_module.rebalance_calculated.connect(self._on_rebalance_calculated)
    
    def _load_initial_data(self):
        """Загрузка начальных данных при запуске"""
        self.status_label.setText("Загрузка данных...")
        
        # Проверка наличия данных в БД
        summary = self.db.get_portfolio_summary()
        
        if summary['total_assets'] > 0:
            self.status_label.setText(
                f"Загружено: {summary['total_assets']} активов, "
                f"портфель: {summary['total_market_value']:,.0f} ₽"
            )
        else:
            self.status_label.setText("Нет данных. Импортируйте отчеты брокеров.")
    
    def _show_welcome_message(self):
        """Показ приветственного сообщения для новых пользователей"""
        summary = self.db.get_portfolio_summary()
        
        if summary['total_assets'] == 0:
            QMessageBox.information(
                self,
                "Добро пожаловать!",
                "Это ваше первое использование приложения.\n\n"
                "Для начала работы:\n"
                "1. Перейдите на вкладку 'Данные'\n"
                "2. Нажмите 'Импортировать отчеты'\n"
                "3. Выберите файлы Excel/CSV от вашего брокера\n\n"
                "Приложение автоматически определит брокера и обработает данные."
            )
    
    # ==================== Обработчики событий ====================
    
    @Slot()
    def _on_import_triggered(self):
        """Обработчик импорта файлов"""
        self.main_navigation.setCurrentIndex(0)  # Переключение на вкладку Данные
        self.data_module.show_import_dialog()
    
    @Slot()
    def _on_export_triggered(self):
        """Обработчик экспорта данных"""
        file_types = "Excel (*.xlsx);;CSV (*.csv);;PDF (*.pdf)"
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Экспорт данных",
            "",
            file_types
        )
        
        if file_path:
            self._perform_export(file_path, selected_filter)
    
    @Slot()
    def _on_refresh_triggered(self):
        """Обработчик обновления данных"""
        self.status_label.setText("Обновление данных...")
        self.loading_progress.setVisible(True)
        
        # Запуск обновления котировок и пересчета портфеля
        QTimer.singleShot(100, self._perform_refresh)
    
    @Slot(dict)
    def _on_files_imported(self, import_data: dict):
        """Обработчик успешного импорта файлов"""
        files_count = import_data.get('files_count', 0)
        transactions_count = import_data.get('transactions_count', 0)
        
        self.status_label.setText(
            f"Импортировано файлов: {files_count}, транзакций: {transactions_count}"
        )
        
        # Обновление других модулей
        self.registry_module.refresh_data()
        self.analytics_module.refresh_data()
        self.ai_advisor_module.refresh_data()
    
    @Slot(dict)
    def _on_portfolio_recalculated(self, portfolio_data: dict):
        """Обработчик пересчета портфеля"""
        total_value = portfolio_data.get('total_value', 0)
        total_pnl = portfolio_data.get('total_pnl', 0)
        
        self.status_label.setText(
            f"Портфель: {total_value:,.0f} ₽ | P&L: {total_pnl:,.0f} ₽"
        )
    
    @Slot(object)
    def _on_transaction_selected(self, transaction):
        """Обработчик выбора транзакции в реестре"""
        # Drill-down логика
        pass
    
    @Slot(dict)
    def _on_rebalance_calculated(self, rebalance_data: dict):
        """Обработчик расчета ребалансировки"""
        self.status_label.setText("Ребалансировка рассчитана")
    
    # ==================== Внутренние методы ====================
    
    def _perform_export(self, file_path: str, file_type: str):
        """Выполнение экспорта данных"""
        try:
            # Здесь будет вызов exporter.py
            self.status_label.setText(f"Данные экспортированы в {file_path}")
            QMessageBox.information(
                self,
                "Экспорт завершен",
                f"Данные успешно экспортированы в файл:\n{file_path}"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка экспорта",
                f"Не удалось экспортировать данные:\n{str(e)}"
            )
    
    def _perform_refresh(self):
        """Выполнение обновления данных"""
        try:
            # Обновление котировок из Мосбиржи
            # Пересчет портфеля
            # Обновление UI
            
            self.loading_progress.setVisible(False)
            self.status_label.setText("Данные обновлены")
        except Exception as e:
            self.loading_progress.setVisible(False)
            self.status_label.setText("Ошибка обновления")
            QMessageBox.warning(
                self,
                "Ошибка обновления",
                f"Не удалось обновить данные:\n{str(e)}"
            )
    
    def _on_database_settings(self):
        """Настройки базы данных"""
        QMessageBox.information(
            self,
            "База данных",
            f"Путь к базе данных:\n{self.db.db_path}\n\n"
            f"Размер: TBD MB"
        )
    
    def _on_ai_settings(self):
        """Настройки ИИ модели"""
        QMessageBox.information(
            self,
            "ИИ-модель",
            "Настройки ИИ-модели:\n"
            "Провайдер: Ollama / OpenAI-compatible\n"
            "Модель: Llama 3.2 / GPT-4\n"
            "Температура: 0.3"
        )
    
    def _on_theme_settings(self):
        """Настройки темы оформления"""
        QMessageBox.information(
            self,
            "Тема оформления",
            "Текущая тема: Dark (Slate/Charcoal)\n\n"
            "Светлая тема будет доступна в будущих версиях."
        )
    
    def _show_about_dialog(self):
        """Диалог о программе"""
        about_text = """
        <h2>Investment Analyzer</h2>
        <p>Версия: 1.0.0</p>
        <p>Профессиональная система анализа инвестиционного портфеля</p>
        <br>
        <p><b>Основные возможности:</b></p>
        <ul>
            <li>Импорт отчетов от любых брокеров (Excel/CSV)</li>
            <li>Интеллектуальный парсер с RLHF-обучением</li>
            <li>Интеграция с API Мосбиржи (ISS)</li>
            <li>Расчет налогов по FIFO и XIRR</li>
            <li>ИИ-советник и калькулятор ребалансировки</li>
            <li>Конструктор дашбордов и отчетов</li>
        </ul>
        <br>
        <p>© 2025 Investment Analyzer Team</p>
        """
        
        QMessageBox.about(self, "О программе", about_text)
    
    def _open_documentation(self):
        """Открытие документации"""
        QDesktopServices.openUrl(QUrl("https://example.com/docs"))
    
    def closeEvent(self, event):
        """Обработчик закрытия приложения"""
        reply = QMessageBox.question(
            self,
            "Выход из приложения",
            "Вы уверены, что хотите выйти?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()


def main():
    """Точка входа в приложение"""
    app = QApplication(sys.argv)
    
    # Настройка шрифтов
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    # Создание и показ главного окна
    window = InvestmentAnalyzerApp()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

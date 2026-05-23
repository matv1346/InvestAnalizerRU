"""
ui/registry_module.py - Интерактивный реестр сделок (Drill-Down)
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QFrame, QGroupBox, QTreeWidget, QTreeWidgetItem, QMessageBox,
    QFileDialog, QLineEdit, QDateEdit, QCheckBox
)
from PyQt6.QtCore import pyqtSignal, pyqtSlot, Qt, QTimer
from PyQt6.QtGui import QFont, QColor, QBrush

# Алиас для совместимости
Signal = pyqtSignal
Slot = pyqtSlot

from database import Database


class RegistryModule(QWidget):
    """Модуль интерактивного реестра сделок с Drill-Down навигацией"""
    
    transaction_selected = Signal(object)  # Сигнал при выборе транзакции
    
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
        
        title_label = QLabel("📋 Реестр сделок")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Кнопка добавления отчета
        add_report_btn = QPushButton("➕ Добавить отчет")
        add_report_btn.clicked.connect(self._on_add_report)
        header_layout.addWidget(add_report_btn)
        
        # Кнопка экспорта
        export_btn = QPushButton("📤 Экспорт")
        export_btn.clicked.connect(self._on_export)
        header_layout.addWidget(export_btn)
        
        main_layout.addLayout(header_layout)
        
        # Панель фильтров
        filters_group = self._create_filters_panel()
        main_layout.addWidget(filters_group)
        
        # Дерево навигации (Уровень 1 и 2)
        nav_group = self._create_navigation_tree()
        main_layout.addWidget(nav_group)
        
        # Таблица транзакций (Уровень 3)
        transactions_group = self._create_transactions_table()
        main_layout.addWidget(transactions_group)
        
        # Статус бар
        status_layout = QHBoxLayout()
        
        self.total_count_label = QLabel("Всего транзакций: 0")
        status_layout.addWidget(self.total_count_label)
        
        status_layout.addStretch()
        
        self.filtered_count_label = QLabel("Показано: 0")
        self.filtered_count_label.setStyleSheet("color: #94a3b8;")
        status_layout.addWidget(self.filtered_count_label)
        
        main_layout.addLayout(status_layout)
    
    def _create_filters_panel(self) -> QGroupBox:
        """Создание панели фильтров"""
        group = QGroupBox("🔍 Фильтры")
        layout = QHBoxLayout(group)
        
        # Фильтр по типу транзакции
        layout.addWidget(QLabel("Тип:"))
        self.type_filter = QComboBox()
        self.type_filter.addItem("Все типы", "all")
        self.type_filter.addItem("Покупка", "buy")
        self.type_filter.addItem("Продажа", "sell")
        self.type_filter.addItem("Дивиденды", "dividend")
        self.type_filter.addItem("Купоны", "coupon")
        self.type_filter.addItem("Комиссии", "fee")
        self.type_filter.currentTextChanged.connect(self._apply_filters)
        layout.addWidget(self.type_filter)
        
        # Фильтр по дате
        layout.addWidget(QLabel("Дата с:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        layout.addWidget(self.date_from)
        
        layout.addWidget(QLabel("по:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        layout.addWidget(self.date_to)
        
        # Текстовый поиск
        layout.addWidget(QLabel("Поиск:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Тикер, ISIN, брокер...")
        self.search_input.textChanged.connect(self._apply_filters)
        layout.addWidget(self.search_input)
        
        # Кнопка сброса
        reset_btn = QPushButton("Сбросить")
        reset_btn.clicked.connect(self._reset_filters)
        layout.addWidget(reset_btn)
        
        return group
    
    def _create_navigation_tree(self) -> QGroupBox:
        """Создание дерева навигации"""
        group = QGroupBox("📁 Навигация (кликните для детализации)")
        layout = QVBoxLayout(group)
        
        self.nav_tree = QTreeWidget()
        self.nav_tree.setHeaderLabels(["Уровень", "Название", "Сумма", "Транзакций"])
        self.nav_tree.setColumnWidth(0, 100)
        self.nav_tree.setColumnWidth(1, 300)
        self.nav_tree.setColumnWidth(2, 120)
        self.nav_tree.setColumnWidth(3, 80)
        self.nav_tree.itemClicked.connect(self._on_nav_item_clicked)
        layout.addWidget(self.nav_tree)
        
        return group
    
    def _create_transactions_table(self) -> QGroupBox:
        """Создание таблицы транзакций"""
        group = QGroupBox("💹 Детали транзакций")
        layout = QVBoxLayout(group)
        
        self.transactions_table = QTableWidget()
        self.transactions_table.setColumnCount(10)
        self.transactions_table.setHorizontalHeaderLabels([
            "Дата", "Время", "Брокер", "Тикер", "Тип",
            "Кол-во", "Цена", "Сумма", "Комиссия", "Налог"
        ])
        
        header = self.transactions_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSortIndicatorShown(True)
        header.setSortIndicator(0, Qt.SortOrder.DescendingOrder)
        
        self.transactions_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.transactions_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.transactions_table.setAlternatingRowColors(True)
        self.transactions_table.itemSelectionChanged.connect(self._on_transaction_selected)
        
        layout.addWidget(self.transactions_table)
        
        return group
    
    def get_widget(self) -> QWidget:
        """Возвращает основной виджет модуля"""
        return self
    
    def refresh_data(self):
        """Обновление данных реестра"""
        self._load_navigation_tree()
        self._load_transactions()
    
    def _load_navigation_tree(self):
        """Загрузка дерева навигации"""
        self.nav_tree.clear()
        
        # Уровень 1: Глобальный портфель
        portfolio_item = QTreeWidgetItem([
            "Портфель", "Все брокеры", "0 ₽", "0"
        ])
        portfolio_item.setData(0, Qt.ItemDataRole.UserRole, 'portfolio')
        self.nav_tree.addTopLevelItem(portfolio_item)
        
        # Уровень 2: Брокеры
        brokers = self.db.get_portfolio_positions()
        broker_totals = {}
        
        for pos in brokers:
            broker_name = pos['broker_name']
            if broker_name not in broker_totals:
                broker_totals[broker_name] = {'value': 0, 'count': 0}
            
            broker_totals[broker_name]['value'] += pos['market_value'] or 0
            broker_totals[broker_name]['count'] += 1
        
        for broker_name, data in broker_totals.items():
            broker_item = QTreeWidgetItem([
                "Брокер", broker_name, f"{data['value']:,.0f} ₽", str(data['count'])
            ])
            broker_item.setData(0, Qt.ItemDataRole.UserRole, 'broker')
            broker_item.setData(1, Qt.ItemDataRole.UserRole, broker_name)
            portfolio_item.addChild(broker_item)
        
        # Развернуть первый уровень
        self.nav_tree.expandItem(portfolio_item)
    
    def _load_transactions(self, filters: dict = None):
        """Загрузка транзакций в таблицу"""
        self.transactions_table.setRowCount(0)
        
        # Здесь будет запрос к БД с фильтрами
        # transactions = self.db.get_transactions(filters)
        
        # Заглушка для демонстрации
        sample_data = [
            ("2024-12-15", "14:30", "ВТБ", "SBER", "buy", "100", "250.50", "25,050", "50", "0"),
            ("2024-12-14", "11:15", "ВТБ", "GAZP", "sell", "50", "180.00", "9,000", "18", "0"),
            ("2024-12-13", "10:00", "Тинькофф", "LKOH", "buy", "20", "2800.00", "56,000", "112", "0"),
        ]
        
        for row_data in sample_data:
            row_position = self.transactions_table.rowCount()
            self.transactions_table.insertRow(row_position)
            
            for col, value in enumerate(row_data):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.transactions_table.setItem(row_position, col, item)
        
        self._update_counts(len(sample_data))
    
    def _apply_filters(self):
        """Применение фильтров"""
        filters = {
            'type': self.type_filter.currentData(),
            'date_from': self.date_from.date().toString("yyyy-MM-dd"),
            'date_to': self.date_to.date().toString("yyyy-MM-dd"),
            'search': self.search_input.text()
        }
        
        self._load_transactions(filters)
    
    def _reset_filters(self):
        """Сброс фильтров"""
        self.type_filter.setCurrentIndex(0)
        self.search_input.clear()
        self._load_transactions()
    
    def _on_nav_item_clicked(self, item: QTreeWidgetItem, column: int):
        """Обработчик клика по элементу навигации"""
        level = item.data(0, Qt.ItemDataRole.UserRole)
        
        if level == 'broker':
            broker_name = item.data(1, Qt.ItemDataRole.UserRole)
            # Drill-down до уровня брокера
            self._load_transactions({'broker': broker_name})
        elif level == 'portfolio':
            # Глобальный уровень
            self._load_transactions()
        
        self.transaction_selected.emit({
            'level': level,
            'data': item.data(1, Qt.ItemDataRole.UserRole) if level == 'broker' else None
        })
    
    def _on_transaction_selected(self):
        """Обработчик выбора транзакции"""
        selected_rows = self.transactions_table.selectedItems()
        
        if selected_rows:
            row = selected_rows[0].row()
            transaction_data = {
                'date': self.transactions_table.item(row, 0).text(),
                'ticker': self.transactions_table.item(row, 3).text(),
                'type': self.transactions_table.item(row, 4).text(),
            }
            
            self.transaction_selected.emit(transaction_data)
    
    def _on_add_report(self):
        """Добавление отчета"""
        QMessageBox.information(
            self,
            "Добавление отчета",
            "Перейдите на вкладку 'Данные' для импорта нового отчета"
        )
    
    def _on_export(self):
        """Экспорт данных"""
        file_types = "Excel (*.xlsx);;CSV (*.csv)"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Экспорт реестра сделок",
            "",
            file_types
        )
        
        if file_path:
            # Здесь будет вызов exporter.py
            QMessageBox.information(
                self,
                "Экспорт",
                f"Данные экспортированы в:\n{file_path}"
            )
    
    def _update_counts(self, count: int):
        """Обновление счетчиков"""
        self.filtered_count_label.setText(f"Показано: {count}")

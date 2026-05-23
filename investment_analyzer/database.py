"""
database.py - Схемы SQLite, FIFO, XIRR, кэш котировок, правила RLHF-парсинга
"""

import sqlite3
from datetime import datetime, date
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager
import json
import os


class Database:
    """Основной класс работы с базой данных SQLite"""
    
    def __init__(self, db_path: str = "investment_data.db"):
        self.db_path = db_path
        self.init_database()
    
    @contextmanager
    def get_connection(self):
        """Контекстный менеджер для подключения к БД"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def init_database(self):
        """Инициализация всех таблиц базы данных"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Таблица брокеров
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS brokers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    display_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1
                )
            """)
            
            # Таблица загруженных файлов отчетов
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS report_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    broker_id INTEGER NOT NULL,
                    filename TEXT NOT NULL,
                    file_path TEXT,
                    file_hash TEXT UNIQUE,
                    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    report_period_start DATE,
                    report_period_end DATE,
                    file_size INTEGER,
                    parse_status TEXT DEFAULT 'pending',
                    parse_error TEXT,
                    FOREIGN KEY (broker_id) REFERENCES brokers(id) ON DELETE CASCADE
                )
            """)
            
            # Таблица активов (ценные бумаги)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS assets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    isin TEXT,
                    name TEXT,
                    asset_type TEXT CHECK(asset_type IN ('stock', 'bond', 'etf', 'bpirf', 'currency', 'other')),
                    sector TEXT,
                    currency TEXT DEFAULT 'RUB',
                    nominal_value REAL,
                    moex_code TEXT,
                    metadata JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(ticker, currency)
                )
            """)
            
            # Таблица транзакций (основная)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_file_id INTEGER NOT NULL,
                    broker_id INTEGER NOT NULL,
                    asset_id INTEGER NOT NULL,
                    transaction_date DATE NOT NULL,
                    transaction_time TIME,
                    transaction_type TEXT CHECK(transaction_type IN ('buy', 'sell', 'dividend', 'coupon', 'fee', 'tax', 'deposit', 'withdrawal', 'conversion', 'other')),
                    quantity REAL NOT NULL,
                    price REAL NOT NULL,
                    amount REAL NOT NULL,
                    currency TEXT DEFAULT 'RUB',
                    commission REAL DEFAULT 0,
                    tax REAL DEFAULT 0,
                    accrued_interest REAL DEFAULT 0,
                    settlement_date DATE,
                    trade_id TEXT,
                    original_row_data JSON,
                    is_duplicate BOOLEAN DEFAULT 0,
                    duplicate_of INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (report_file_id) REFERENCES report_files(id) ON DELETE CASCADE,
                    FOREIGN KEY (broker_id) REFERENCES brokers(id) ON DELETE CASCADE,
                    FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE,
                    FOREIGN KEY (duplicate_of) REFERENCES transactions(id)
                )
            """)
            
            # Индексы для ускорения поиска дубликатов и фильтрации
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_transactions_date 
                ON transactions(transaction_date)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_transactions_asset 
                ON transactions(asset_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_transactions_broker 
                ON transactions(broker_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_transactions_type 
                ON transactions(transaction_type)
            """)
            
            # Таблица позиций портфеля (текущие остатки)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS portfolio_positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    broker_id INTEGER NOT NULL,
                    asset_id INTEGER NOT NULL,
                    quantity REAL NOT NULL DEFAULT 0,
                    average_buy_price REAL DEFAULT 0,
                    current_price REAL,
                    market_value REAL,
                    unrealized_pnl REAL,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (broker_id) REFERENCES brokers(id) ON DELETE CASCADE,
                    FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE,
                    UNIQUE(broker_id, asset_id)
                )
            """)
            
            # Таблица денежных потоков (вводы/выводы) для XIRR
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cash_flows (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    broker_id INTEGER NOT NULL,
                    flow_date DATE NOT NULL,
                    flow_type TEXT CHECK(flow_type IN ('inflow', 'outflow')),
                    amount REAL NOT NULL,
                    currency TEXT DEFAULT 'RUB',
                    description TEXT,
                    transaction_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (broker_id) REFERENCES brokers(id) ON DELETE CASCADE,
                    FOREIGN KEY (transaction_id) REFERENCES transactions(id)
                )
            """)
            
            # Таблица правил RLHF-парсинга (обучение на фидбеке пользователя)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS parsing_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    broker_id INTEGER,
                    rule_type TEXT CHECK(rule_type IN ('field_mapping', 'pattern_matching', 'commission_binding', 'tax_binding', 'asset_classification', 'custom')),
                    pattern TEXT,
                    pattern_type TEXT DEFAULT 'regex',
                    target_field TEXT,
                    action JSON,
                    priority INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1,
                    created_from_feedback BOOLEAN DEFAULT 0,
                    feedback_text TEXT,
                    confidence_score REAL DEFAULT 1.0,
                    usage_count INTEGER DEFAULT 0,
                    last_used TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (broker_id) REFERENCES brokers(id) ON DELETE SET NULL
                )
            """)
            
            # Таблица истории чата с ИИ-парсером (контекст обучения)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    user_message TEXT NOT NULL,
                    ai_response TEXT,
                    related_report_file_id INTEGER,
                    rule_created_id INTEGER,
                    sentiment_score REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (related_report_file_id) REFERENCES report_files(id) ON DELETE SET NULL,
                    FOREIGN KEY (rule_created_id) REFERENCES parsing_rules(id) ON DELETE SET NULL
                )
            """)
            
            # Таблица кэша котировок Мосбиржи
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS moex_quotes_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_id INTEGER NOT NULL,
                    quote_date DATE NOT NULL,
                    open_price REAL,
                    high_price REAL,
                    low_price REAL,
                    close_price REAL,
                    last_price REAL,
                    volume INTEGER,
                    value REAL,
                    currency TEXT DEFAULT 'RUB',
                    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE,
                    UNIQUE(asset_id, quote_date)
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_moex_quotes_asset_date 
                ON moex_quotes_cache(asset_id, quote_date)
            """)
            
            # Таблица метаданных активов от Мосбиржи
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS moex_asset_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_id INTEGER NOT NULL,
                    secid TEXT,
                    boardid TEXT,
                    short_name TEXT,
                    reg_number TEXT,
                    issuer_name TEXT,
                    sector_economy TEXT,
                    type_instrument TEXT,
                    currency_nominal TEXT,
                    face_value REAL,
                    maturity_date DATE,
                    coupon_rate REAL,
                    listing_level INTEGER,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    raw_data JSON,
                    FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE,
                    UNIQUE(asset_id)
                )
            """)
            
            # Таблица курсов валют (для кросс-курсового движка)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS currency_rates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rate_date DATE NOT NULL,
                    currency_from TEXT NOT NULL,
                    currency_to TEXT NOT NULL DEFAULT 'RUB',
                    rate REAL NOT NULL,
                    source TEXT DEFAULT 'moex',
                    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(rate_date, currency_from, currency_to)
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_currency_rates_date 
                ON currency_rates(rate_date)
            """)
            
            # Таблица пользовательских дашбордов (конструктор отчетов)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS custom_dashboards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT DEFAULT 'default',
                    dashboard_name TEXT NOT NULL,
                    description TEXT,
                    configuration JSON NOT NULL,
                    widgets JSON,
                    filters JSON,
                    is_default BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_accessed TIMESTAMP
                )
            """)
            
            # Таблица пресетов графиков
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chart_presets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    preset_name TEXT NOT NULL,
                    chart_type TEXT CHECK(chart_type IN ('line', 'bar', 'donut', 'candlestick', 'area', 'scatter')),
                    x_axis_field TEXT,
                    y_axis_fields JSON,
                    color_scheme TEXT,
                    filters JSON,
                    group_by TEXT,
                    is_system BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица настроек ИИ-советника
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_advisor_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    setting_key TEXT UNIQUE NOT NULL,
                    setting_value JSON,
                    description TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица рекомендаций ИИ
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    recommendation_type TEXT CHECK(recommendation_type IN ('rebalance', 'risk_alert', 'opportunity', 'diversification', 'tax_optimization')),
                    priority TEXT CHECK(priority IN ('high', 'medium', 'low')),
                    title TEXT NOT NULL,
                    description TEXT,
                    action_suggested JSON,
                    reasoning TEXT,
                    expected_impact JSON,
                    is_dismissed BOOLEAN DEFAULT 0,
                    is_implemented BOOLEAN DEFAULT 0,
                    related_assets JSON,
                    confidence_score REAL
                )
            """)
            
            # Таблица расчетов ребалансировки
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rebalance_calculations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    calculation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    risk_profile TEXT CHECK(risk_profile IN ('conservative', 'moderate', 'aggressive')),
                    new_investment_amount REAL DEFAULT 0,
                    current_portfolio_json JSON,
                    target_allocation_json JSON,
                    recommended_trades JSON,
                    total_invested REAL,
                    remaining_cash REAL,
                    expected_return REAL,
                    expected_risk REAL,
                    calculation_params JSON
                )
            """)
            
            # Таблица налоговых расчетов (FIFO)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tax_calculations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tax_year INTEGER NOT NULL,
                    broker_id INTEGER,
                    asset_id INTEGER,
                    calculation_method TEXT DEFAULT 'fifo',
                    buy_transaction_id INTEGER,
                    sell_transaction_id INTEGER,
                    quantity_sold REAL,
                    purchase_price REAL,
                    sale_price REAL,
                    taxable_gain REAL,
                    tax_rate REAL,
                    tax_amount REAL,
                    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (broker_id) REFERENCES brokers(id),
                    FOREIGN KEY (asset_id) REFERENCES assets(id),
                    FOREIGN KEY (buy_transaction_id) REFERENCES transactions(id),
                    FOREIGN KEY (sell_transaction_id) REFERENCES transactions(id)
                )
            """)
            
            # Вставка начальных данных для системных пресетов
            self._insert_default_chart_presets(cursor)
            self._insert_default_ai_settings(cursor)
    
    def _insert_default_chart_presets(self, cursor):
        """Вставка системных пресетов графиков"""
        default_presets = [
            ('Портфель по времени', 'line', 'date', 
             json.dumps(['market_value', 'unrealized_pnl']), 'blue_gradient', 
             json.dumps({'asset_type': 'all'}), None, True),
            ('Структура активов', 'donut', 'asset_type', 
             json.dumps(['quantity']), 'category_colors', 
             json.dumps({}), 'asset_type', True),
            ('Доходность по секторам', 'bar', 'sector', 
             json.dumps(['unrealized_pnl_percent']), 'sector_colors', 
             json.dumps({}), 'sector', True),
        ]
        
        for preset in default_presets:
            cursor.execute("""
                INSERT OR IGNORE INTO chart_presets 
                (preset_name, chart_type, x_axis_field, y_axis_fields, color_scheme, filters, group_by, is_system)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, preset)
    
    def _insert_default_ai_settings(self, cursor):
        """Вставка настроек ИИ по умолчанию"""
        default_settings = [
            ('risk_concentration_threshold', json.dumps({'single_asset': 0.25, 'sector': 0.40}), 
             'Порог концентрации риска (доля)'),
            ('rebalance_frequency', json.dumps({'type': 'threshold', 'value': 0.05}), 
             'Частота ребалансировки'),
            ('ai_model_config', json.dumps({'provider': 'ollama', 'model': 'llama3.2', 'temperature': 0.3}), 
             'Конфигурация ИИ модели'),
        ]
        
        for setting in default_settings:
            cursor.execute("""
                INSERT OR IGNORE INTO ai_advisor_settings 
                (setting_key, setting_value, description)
                VALUES (?, ?, ?)
            """, setting)
    
    # ==================== CRUD операции ====================
    
    def add_broker(self, name: str, display_name: Optional[str] = None) -> int:
        """Добавление брокера"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO brokers (name, display_name) VALUES (?, ?)",
                (name, display_name or name)
            )
            return cursor.lastrowid
    
    def get_broker_by_name(self, name: str) -> Optional[sqlite3.Row]:
        """Получение брокера по имени"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM brokers WHERE name = ?", (name,))
            return cursor.fetchone()
    
    def add_report_file(self, broker_id: int, filename: str, file_hash: str, 
                       file_path: Optional[str] = None) -> int:
        """Добавление отчета о файле"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO report_files 
                (broker_id, filename, file_path, file_hash)
                VALUES (?, ?, ?, ?)
            """, (broker_id, filename, file_path, file_hash))
            return cursor.lastrowid
    
    def delete_report_file(self, report_id: int) -> bool:
        """Удаление файла отчета (каскадно удаляет транзакции)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM report_files WHERE id = ?", (report_id,))
            return cursor.rowcount > 0
    
    def add_asset(self, ticker: str, asset_type: str, **kwargs) -> int:
        """Добавление актива"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO assets 
                (ticker, isin, name, asset_type, sector, currency, nominal_value, moex_code, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticker,
                kwargs.get('isin'),
                kwargs.get('name'),
                asset_type,
                kwargs.get('sector'),
                kwargs.get('currency', 'RUB'),
                kwargs.get('nominal_value'),
                kwargs.get('moex_code'),
                json.dumps(kwargs.get('metadata', {}))
            ))
            return cursor.lastrowid
    
    def get_or_create_asset(self, ticker: str, currency: str = 'RUB', **kwargs) -> int:
        """Получить или создать актив"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM assets WHERE ticker = ? AND currency = ?",
                (ticker, currency)
            )
            row = cursor.fetchone()
            
            if row:
                return row['id']
            else:
                return self.add_asset(ticker, kwargs.get('asset_type', 'other'), 
                                    currency=currency, **kwargs)
    
    def add_transaction(self, report_file_id: int, broker_id: int, asset_id: int,
                       transaction_date: date, transaction_type: str,
                       quantity: float, price: float, amount: float,
                       **kwargs) -> int:
        """Добавление транзакции"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO transactions 
                (report_file_id, broker_id, asset_id, transaction_date, transaction_time,
                 transaction_type, quantity, price, amount, currency, commission, tax,
                 accrued_interest, settlement_date, trade_id, original_row_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                report_file_id, broker_id, asset_id, transaction_date,
                kwargs.get('transaction_time'), transaction_type, quantity, price, amount,
                kwargs.get('currency', 'RUB'), kwargs.get('commission', 0),
                kwargs.get('tax', 0), kwargs.get('accrued_interest', 0),
                kwargs.get('settlement_date'), kwargs.get('trade_id'),
                json.dumps(kwargs.get('original_row_data', {}))
            ))
            return cursor.lastrowid
    
    def find_duplicates(self, broker_id: int, transaction_date: date, 
                       asset_id: int, quantity: float, amount: float) -> List[sqlite3.Row]:
        """Поиск потенциальных дубликатов транзакций"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.*, rf.filename as report_filename
                FROM transactions t
                JOIN report_files rf ON t.report_file_id = rf.id
                WHERE t.broker_id = ?
                  AND t.transaction_date = ?
                  AND t.asset_id = ?
                  AND ABS(t.quantity - ?) < 0.0001
                  AND ABS(t.amount - ?) < 0.01
                  AND t.is_duplicate = 0
            """, (broker_id, transaction_date, asset_id, quantity, amount))
            return cursor.fetchall()
    
    def mark_as_duplicate(self, transaction_id: int, duplicate_of: int):
        """Отметить транзакцию как дубликат"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE transactions 
                SET is_duplicate = 1, duplicate_of = ?
                WHERE id = ?
            """, (duplicate_of, transaction_id))
    
    # ==================== Правила парсинга (RLHF) ====================
    
    def add_parsing_rule(self, broker_id: Optional[int], rule_type: str,
                        pattern: str, target_field: str, action: Dict,
                        feedback_text: Optional[str] = None,
                        priority: int = 0) -> int:
        """Добавление правила парсинга из фидбека пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO parsing_rules 
                (broker_id, rule_type, pattern, pattern_type, target_field, action,
                 priority, is_active, created_from_feedback, feedback_text)
                VALUES (?, ?, ?, 'regex', ?, ?, ?, 1, 1, ?)
            """, (broker_id, rule_type, pattern, target_field, json.dumps(action), 
                  priority, feedback_text))
            return cursor.lastrowid
    
    def get_parsing_rules(self, broker_id: Optional[int] = None, 
                         rule_type: Optional[str] = None) -> List[sqlite3.Row]:
        """Получение активных правил парсинга"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM parsing_rules WHERE is_active = 1"
            params = []
            
            if broker_id is not None:
                query += " AND (broker_id = ? OR broker_id IS NULL)"
                params.append(broker_id)
            
            if rule_type is not None:
                query += " AND rule_type = ?"
                params.append(rule_type)
            
            query += " ORDER BY priority DESC, created_at DESC"
            
            cursor.execute(query, params)
            return cursor.fetchall()
    
    def update_rule_confidence(self, rule_id: int, confidence_delta: float):
        """Обновление уверенности в правиле на основе использования"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE parsing_rules 
                SET confidence_score = MIN(1.0, confidence_score + ?),
                    usage_count = usage_count + 1,
                    last_used = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (confidence_delta, rule_id))
    
    # ==================== Портфель и позиции ====================
    
    def get_portfolio_positions(self, broker_id: Optional[int] = None) -> List[sqlite3.Row]:
        """Получение текущих позиций портфеля"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT pp.*, a.ticker, a.name, a.asset_type, a.sector, a.currency,
                       b.name as broker_name
                FROM portfolio_positions pp
                JOIN assets a ON pp.asset_id = a.id
                JOIN brokers b ON pp.broker_id = b.id
                WHERE pp.quantity != 0
            """
            params = []
            
            if broker_id is not None:
                query += " AND pp.broker_id = ?"
                params.append(broker_id)
            
            cursor.execute(query, params)
            return cursor.fetchall()
    
    def update_portfolio_position(self, broker_id: int, asset_id: int,
                                 quantity: float, average_price: float,
                                 current_price: Optional[float] = None):
        """Обновление позиции портфеля"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            market_value = quantity * current_price if current_price else None
            unrealized_pnl = None
            if current_price and average_price > 0:
                unrealized_pnl = (current_price - average_price) * quantity
            
            cursor.execute("""
                INSERT INTO portfolio_positions 
                (broker_id, asset_id, quantity, average_buy_price, current_price, 
                 market_value, unrealized_pnl, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(broker_id, asset_id) DO UPDATE SET
                    quantity = excluded.quantity,
                    average_buy_price = excluded.average_buy_price,
                    current_price = COALESCE(excluded.current_price, current_price),
                    market_value = COALESCE(excluded.market_value, market_value),
                    unrealized_pnl = COALESCE(excluded.unrealized_pnl, unrealized_pnl),
                    last_updated = CURRENT_TIMESTAMP
            """, (broker_id, asset_id, quantity, average_price, current_price, 
                  market_value, unrealized_pnl))
    
    # ==================== Котировки и кэш ====================
    
    def cache_moex_quote(self, asset_id: int, quote_date: date, 
                        quote_data: Dict) -> int:
        """Кэширование котировки Мосбиржи"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO moex_quotes_cache 
                (asset_id, quote_date, open_price, high_price, low_price, close_price,
                 last_price, volume, value, currency, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', '+1 day'))
                ON CONFLICT(asset_id, quote_date) DO UPDATE SET
                    open_price = excluded.open_price,
                    high_price = excluded.high_price,
                    low_price = excluded.low_price,
                    close_price = excluded.close_price,
                    last_price = excluded.last_price,
                    volume = excluded.volume,
                    value = excluded.value,
                    fetched_at = CURRENT_TIMESTAMP,
                    expires_at = datetime('now', '+1 day')
            """, (
                asset_id, quote_date,
                quote_data.get('open'), quote_data.get('high'),
                quote_data.get('low'), quote_data.get('close'),
                quote_data.get('last'), quote_data.get('volume'),
                quote_data.get('value'), quote_data.get('currency', 'RUB')
            ))
            return cursor.lastrowid
    
    def get_latest_quote(self, asset_id: int) -> Optional[sqlite3.Row]:
        """Получение последней котировки для актива"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM moex_quotes_cache 
                WHERE asset_id = ? 
                ORDER BY quote_date DESC 
                LIMIT 1
            """, (asset_id,))
            return cursor.fetchone()
    
    def get_historical_quotes(self, asset_id: int, start_date: date, 
                             end_date: date) -> List[sqlite3.Row]:
        """Получение исторических котировок"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM moex_quotes_cache 
                WHERE asset_id = ? 
                  AND quote_date BETWEEN ? AND ?
                ORDER BY quote_date ASC
            """, (asset_id, start_date, end_date))
            return cursor.fetchall()
    
    # ==================== Курсы валют ====================
    
    def add_currency_rate(self, rate_date: date, currency_from: str, 
                         currency_to: str, rate: float):
        """Добавление курса валюты"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO currency_rates 
                (rate_date, currency_from, currency_to, rate)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(rate_date, currency_from, currency_to) DO UPDATE SET
                    rate = excluded.rate,
                    fetched_at = CURRENT_TIMESTAMP
            """, (rate_date, currency_from, currency_to, rate))
    
    def get_currency_rate(self, rate_date: date, currency_from: str, 
                         currency_to: str = 'RUB') -> Optional[float]:
        """Получение курса валюты на дату"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Прямой курс
            cursor.execute("""
                SELECT rate FROM currency_rates 
                WHERE rate_date = ? 
                  AND currency_from = ? 
                  AND currency_to = ?
            """, (rate_date, currency_from, currency_to))
            row = cursor.fetchone()
            
            if row:
                return row['rate']
            
            # Если прямой курс не найден, пробуем найти обратный
            if currency_to == 'RUB':
                cursor.execute("""
                    SELECT 1/rate as rate FROM currency_rates 
                    WHERE rate_date <= ? 
                      AND currency_from = ? 
                      AND currency_to = ?
                    ORDER BY rate_date DESC 
                    LIMIT 1
                """, (rate_date, currency_to, currency_from))
                row = cursor.fetchone()
                
                if row:
                    return row['rate']
            
            return None
    
    # ==================== Пользовательские дашборды ====================
    
    def save_custom_dashboard(self, dashboard_name: str, configuration: Dict,
                            widgets: Optional[List] = None,
                            filters: Optional[Dict] = None,
                            user_id: str = 'default') -> int:
        """Сохранение пользовательского дашборда"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO custom_dashboards 
                (user_id, dashboard_name, description, configuration, widgets, filters)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user_id, dashboard_name, configuration.get('description'),
                json.dumps(configuration),
                json.dumps(widgets or []),
                json.dumps(filters or {})
            ))
            return cursor.lastrowid
    
    def get_custom_dashboards(self, user_id: str = 'default') -> List[sqlite3.Row]:
        """Получение пользовательских дашбордов"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM custom_dashboards 
                WHERE user_id = ? 
                ORDER BY last_accessed DESC, created_at DESC
            """, (user_id,))
            return cursor.fetchall()
    
    def delete_custom_dashboard(self, dashboard_id: int) -> bool:
        """Удаление пользовательского дашборда"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM custom_dashboards WHERE id = ?",
                (dashboard_id,)
            )
            return cursor.rowcount > 0
    
    # ==================== Рекомендации ИИ ====================
    
    def add_ai_recommendation(self, recommendation_type: str, priority: str,
                             title: str, description: str,
                             action_suggested: Dict, reasoning: str,
                             related_assets: Optional[List[str]] = None,
                             confidence_score: float = 0.8) -> int:
        """Добавление рекомендации ИИ"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO ai_recommendations 
                (recommendation_type, priority, title, description, action_suggested,
                 reasoning, related_assets, confidence_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                recommendation_type, priority, title, description,
                json.dumps(action_suggested), reasoning,
                json.dumps(related_assets or []), confidence_score
            ))
            return cursor.lastrowid
    
    def get_active_recommendations(self, limit: int = 10) -> List[sqlite3.Row]:
        """Получение активных рекомендаций ИИ"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM ai_recommendations 
                WHERE is_dismissed = 0 
                ORDER BY 
                    CASE priority 
                        WHEN 'high' THEN 1 
                        WHEN 'medium' THEN 2 
                        ELSE 3 
                    END,
                    generated_at DESC
                LIMIT ?
            """, (limit,))
            return cursor.fetchall()
    
    def dismiss_recommendation(self, recommendation_id: int):
        """Отклонение рекомендации"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE ai_recommendations 
                SET is_dismissed = 1 
                WHERE id = ?
            """, (recommendation_id,))
    
    # ==================== Расчеты XIRR ====================
    
    def get_cash_flows_for_xirr(self, broker_id: Optional[int] = None,
                               start_date: Optional[date] = None,
                               end_date: Optional[date] = None) -> List[Tuple[date, float]]:
        """Получение денежных потоков для расчета XIRR"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT flow_date, 
                       CASE WHEN flow_type = 'inflow' THEN amount ELSE -amount END as signed_amount
                FROM cash_flows
                WHERE 1=1
            """
            params = []
            
            if broker_id is not None:
                query += " AND broker_id = ?"
                params.append(broker_id)
            
            if start_date is not None:
                query += " AND flow_date >= ?"
                params.append(start_date)
            
            if end_date is not None:
                query += " AND flow_date <= ?"
                params.append(end_date)
            
            query += " ORDER BY flow_date ASC"
            
            cursor.execute(query, params)
            return [(row['flow_date'], row['signed_amount']) for row in cursor.fetchall()]
    
    def calculate_xirr(self, cash_flows: List[Tuple[date, float]], 
                      guess: float = 0.1, max_iterations: int = 100,
                      tolerance: float = 1e-6) -> Optional[float]:
        """
        Расчет XIRR методом Ньютона-Рафсона
        
        Args:
            cash_flows: Список кортежей (дата, сумма)
            guess: Начальное приближение
            max_iterations: Максимальное количество итераций
            tolerance: Точность вычисления
            
        Returns:
            XIRR в виде годовой ставки или None если не сходится
        """
        if len(cash_flows) < 2:
            return None
        
        # Сортировка по датам
        cash_flows = sorted(cash_flows, key=lambda x: x[0])
        
        dates = [cf[0] for cf in cash_flows]
        amounts = [cf[1] for cf in cash_flows]
        
        # Первая дата как точка отсчета
        date_0 = dates[0]
        
        def npv(rate: float) -> float:
            """Расчет чистой приведенной стоимости"""
            total = 0.0
            for i, (d, amount) in enumerate(zip(dates, amounts)):
                days_diff = (d - date_0).days
                total += amount / ((1 + rate) ** (days_diff / 365.0))
            return total
        
        def npv_derivative(rate: float) -> float:
            """Производная NPV по ставке"""
            total = 0.0
            for i, (d, amount) in enumerate(zip(dates, amounts)):
                days_diff = (d - date_0).days
                exponent = days_diff / 365.0
                total -= days_diff * amount / (365.0 * ((1 + rate) ** (exponent + 1)))
            return total
        
        rate = guess
        for iteration in range(max_iterations):
            npv_val = npv(rate)
            if abs(npv_val) < tolerance:
                return rate
            
            derivative = npv_derivative(rate)
            if abs(derivative) < 1e-10:
                break
            
            new_rate = rate - npv_val / derivative
            
            # Ограничение диапазона ставки
            if new_rate < -0.9999:
                new_rate = -0.9999
            elif new_rate > 10:
                new_rate = 10
            
            if abs(new_rate - rate) < tolerance:
                return new_rate
            
            rate = new_rate
        
        return None  # Не сошлось
    
    # ==================== Налоговый расчет FIFO ====================
    
    def calculate_fifo_tax(self, broker_id: int, asset_id: int,
                          tax_year: int) -> List[Dict]:
        """
        Расчет налога по методу FIFO для конкретного актива
        
        Returns:
            Список словарей с информацией о сделках и налоге
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Получаем все покупки и продажи за год
            cursor.execute("""
                SELECT id, transaction_date, transaction_type, quantity, price, amount
                FROM transactions
                WHERE broker_id = ?
                  AND asset_id = ?
                  AND strftime('%Y', transaction_date) = ?
                  AND transaction_type IN ('buy', 'sell')
                ORDER BY transaction_date ASC, id ASC
            """, (broker_id, asset_id, str(tax_year)))
            
            transactions = cursor.fetchall()
            
            # Очередь покупок для FIFO
            buy_queue = []
            tax_lots = []
            
            for tx in transactions:
                if tx['transaction_type'] == 'buy':
                    # Добавляем в очередь покупок
                    buy_queue.append({
                        'transaction_id': tx['id'],
                        'date': tx['transaction_date'],
                        'quantity': tx['quantity'],
                        'price': tx['price'],
                        'remaining': tx['quantity']
                    })
                elif tx['transaction_type'] == 'sell':
                    sell_quantity = tx['quantity']
                    sell_price = tx['price']
                    
                    # Применяем FIFO
                    while sell_quantity > 0 and buy_queue:
                        buy_lot = buy_queue[0]
                        
                        if buy_lot['remaining'] <= sell_quantity:
                            # Используем всю партию
                            quantity_used = buy_lot['remaining']
                            buy_queue.pop(0)
                        else:
                            # Используем часть партии
                            quantity_used = sell_quantity
                            buy_lot['remaining'] -= sell_quantity
                        
                        # Расчет финансового результата
                        purchase_cost = quantity_used * buy_lot['price']
                        sale_proceeds = quantity_used * sell_price
                        gain = sale_proceeds - purchase_cost
                        
                        tax_lots.append({
                            'buy_transaction_id': buy_lot['transaction_id'],
                            'sell_transaction_id': tx['id'],
                            'buy_date': buy_lot['date'],
                            'sell_date': tx['transaction_date'],
                            'quantity': quantity_used,
                            'purchase_price': buy_lot['price'],
                            'sale_price': sell_price,
                            'gain': gain,
                            'taxable': gain > 0
                        })
                        
                        sell_quantity -= quantity_used
            
            return tax_lots
    
    # ==================== Статистика и аналитика ====================
    
    def get_portfolio_summary(self, broker_id: Optional[int] = None) -> Dict:
        """Получение сводной информации по портфелю"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT 
                    COUNT(DISTINCT pp.asset_id) as total_assets,
                    SUM(pp.market_value) as total_market_value,
                    SUM(pp.unrealized_pnl) as total_unrealized_pnl,
                    AVG(pp.unrealized_pnl / (pp.average_buy_price * pp.quantity)) * 100 as avg_return_percent
                FROM portfolio_positions pp
                WHERE pp.quantity != 0
            """
            params = []
            
            if broker_id is not None:
                query += " AND pp.broker_id = ?"
                params.append(broker_id)
            
            cursor.execute(query, params)
            row = cursor.fetchone()
            
            return {
                'total_assets': row['total_assets'] or 0,
                'total_market_value': row['total_market_value'] or 0,
                'total_unrealized_pnl': row['total_unrealized_pnl'] or 0,
                'avg_return_percent': row['avg_return_percent'] or 0
            }
    
    def get_transactions_count(self, report_file_id: Optional[int] = None) -> int:
        """Получение количества транзакций"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT COUNT(*) as cnt FROM transactions WHERE is_duplicate = 0"
            params = []
            
            if report_file_id is not None:
                query += " AND report_file_id = ?"
                params.append(report_file_id)
            
            cursor.execute(query, params)
            return cursor.fetchone()['cnt']


# Глобальный экземпляр базы данных
db_instance: Optional[Database] = None


def get_database(db_path: str = "investment_data.db") -> Database:
    """Получение глобального экземпляра базы данных"""
    global db_instance
    if db_instance is None:
        db_instance = Database(db_path)
    return db_instance

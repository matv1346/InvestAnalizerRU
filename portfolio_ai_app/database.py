"""
database.py - Схемы SQLite и расчетные функции (FIFO, XIRR)
Полная автономность: все данные хранятся локально в SQLite.
"""

import sqlite3
import json
import hashlib
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import numpy as np
from scipy.optimize import newton


DB_PATH = Path(__file__).parent / "portfolio_data.db"


def get_connection() -> sqlite3.Connection:
    """Получить соединение с БД."""
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Инициализация схемы базы данных."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Таблица брокеров
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS brokers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Таблица файлов отчетов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS report_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            broker_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            file_hash TEXT UNIQUE NOT NULL,
            file_path TEXT,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            row_count INTEGER DEFAULT 0,
            FOREIGN KEY (broker_id) REFERENCES brokers(id) ON DELETE CASCADE
        )
    """)
    
    # Таблица транзакций
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_file_id INTEGER NOT NULL,
            broker_id INTEGER NOT NULL,
            trade_date DATE NOT NULL,
            settlement_date DATE,
            ticker TEXT NOT NULL,
            isin TEXT,
            operation_type TEXT NOT NULL,
            -- Тип операции: BUY, SELL, DIVIDEND, COUPON, COMMISSION, TAX
            quantity REAL NOT NULL,
            price REAL NOT NULL,
            amount REAL NOT NULL,
            -- Сумма сделки (положительная для покупки, отрицательная для продажи)
            commission REAL DEFAULT 0.0,
            tax REAL DEFAULT 0.0,
            accrued_tax REAL DEFAULT 0.0,
            -- Удержанный налог (для дивидендов/купонов)
            currency TEXT DEFAULT 'RUB',
            counterparty TEXT,
            original_row_data TEXT,
            -- JSON с исходными данными строки
            ai_confidence REAL DEFAULT 0.0,
            -- Уверенность ИИ-классификатора
            is_manual_correction INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (report_file_id) REFERENCES report_files(id) ON DELETE CASCADE,
            FOREIGN KEY (broker_id) REFERENCES brokers(id) ON DELETE CASCADE
        )
    """)
    
    # Индексы для ускорения поиска
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_transactions_ticker 
        ON transactions(ticker)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_transactions_date 
        ON transactions(trade_date)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_transactions_broker 
        ON transactions(broker_id)
    """)
    
    # Таблица для хранения обучающих данных ИИ-парсера (RLHF лог)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_training_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_text TEXT NOT NULL,
            predicted_type TEXT NOT NULL,
            corrected_type TEXT NOT NULL,
            feature_vector TEXT,
            -- JSON вектор признаков
            broker_context TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            applied_to_model INTEGER DEFAULT 0
        )
    """)
    
    # Таблица весов локальной ИИ-модели парсера
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_parser_weights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_version TEXT NOT NULL,
            weights_data TEXT NOT NULL,
            -- JSON serialized weights
            vocabulary_data TEXT,
            -- JSON vocabulary for TF-IDF
            trained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            training_samples_count INTEGER DEFAULT 0
        )
    """)
    
    # Таблица кэша котировок Мосбиржи
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS moex_quotes_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            quote_date DATE NOT NULL,
            open_price REAL,
            close_price REAL,
            high_price REAL,
            low_price REAL,
            volume INTEGER,
            currency TEXT DEFAULT 'RUB',
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ticker, quote_date)
        )
    """)
    
    # Таблица метаданных бумаг (сектор, тип, валюта)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS securities_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT UNIQUE NOT NULL,
            isin TEXT,
            security_type TEXT,
            -- SHARE, BOND, ETF, CURRENCY
            sector TEXT,
            industry TEXT,
            currency_nominal TEXT,
            issuer_name TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Таблица сохраненных пользовательских графиков/дашбордов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS saved_dashboards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            config_json TEXT NOT NULL,
            -- Конфигурация осей, фильтров, типов графиков
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Таблица позиций портфеля (рассчитывается, но кэшируется)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            broker_id INTEGER,
            ticker TEXT NOT NULL,
            total_quantity REAL NOT NULL,
            average_buy_price REAL NOT NULL,
            current_price REAL,
            market_value REAL,
            unrealized_pnl REAL,
            realized_pnl REAL,
            weight_percent REAL,
            calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(broker_id, ticker)
        )
    """)
    
    conn.commit()
    conn.close()
    print(f"[DATABASE] Инициализирована база данных: {DB_PATH}")


# ============================================================================
# CRUD операции для брокеров
# ============================================================================

def add_broker(name: str) -> int:
    """Добавить брокера, вернуть ID."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO brokers (name) VALUES (?)", (name,))
        conn.commit()
        broker_id = cursor.lastrowid
        return broker_id
    except sqlite3.IntegrityError:
        cursor.execute("SELECT id FROM brokers WHERE name = ?", (name,))
        row = cursor.fetchone()
        return row['id'] if row else None
    finally:
        conn.close()


def get_all_brokers() -> List[Dict]:
    """Получить список всех брокеров."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM brokers ORDER BY name")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def delete_broker(broker_id: int):
    """Удалить брокера и все связанные данные (каскад)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.execute("DELETE FROM brokers WHERE id = ?", (broker_id,))
    conn.commit()
    conn.close()


# ============================================================================
# CRUD операции для файлов отчетов
# ============================================================================

def calculate_file_hash(filepath: str) -> str:
    """Вычислить SHA256 хэш файла для обнаружения дубликатов."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def add_report_file(broker_id: int, filename: str, filepath: str = None) -> Tuple[int, bool]:
    """
    Добавить файл отчета.
    Возвращает (file_id, is_duplicate).
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    file_hash = calculate_file_hash(filepath) if filepath else hashlib.sha256(filename.encode()).hexdigest()
    
    # Проверка на дубликат
    cursor.execute("SELECT id FROM report_files WHERE file_hash = ?", (file_hash,))
    existing = cursor.fetchone()
    
    if existing:
        conn.close()
        return existing['id'], True
    
    cursor.execute(
        "INSERT INTO report_files (broker_id, filename, file_hash, file_path) VALUES (?, ?, ?, ?)",
        (broker_id, filename, file_hash, filepath)
    )
    conn.commit()
    file_id = cursor.lastrowid
    conn.close()
    return file_id, False


def get_reports_for_broker(broker_id: int) -> List[Dict]:
    """Получить все отчеты для брокера."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM report_files WHERE broker_id = ? ORDER BY upload_date DESC",
        (broker_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def delete_report_file(file_id: int):
    """Удалить файл отчета и все связанные транзакции."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.execute("DELETE FROM report_files WHERE id = ?", (file_id,))
    conn.commit()
    conn.close()


# ============================================================================
# CRUD операции для транзакций
# ============================================================================

def add_transaction(data: Dict) -> int:
    """Добавить транзакцию."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO transactions (
            report_file_id, broker_id, trade_date, settlement_date, ticker, isin,
            operation_type, quantity, price, amount, commission, tax, accrued_tax,
            currency, counterparty, original_row_data, ai_confidence, is_manual_correction
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get('report_file_id'),
        data.get('broker_id'),
        data.get('trade_date'),
        data.get('settlement_date'),
        data.get('ticker'),
        data.get('isin'),
        data.get('operation_type'),
        data.get('quantity', 0),
        data.get('price', 0),
        data.get('amount', 0),
        data.get('commission', 0),
        data.get('tax', 0),
        data.get('accrued_tax', 0),
        data.get('currency', 'RUB'),
        data.get('counterparty'),
        json.dumps(data.get('original_row_data', {})),
        data.get('ai_confidence', 0.0),
        data.get('is_manual_correction', 0)
    ))
    
    conn.commit()
    tx_id = cursor.lastrowid
    conn.close()
    return tx_id


def add_transactions_batch(transactions: List[Dict]):
    """Добавить пакет транзакций (для производительности)."""
    conn = get_connection()
    cursor = conn.cursor()
    
    batch_data = []
    for tx in transactions:
        batch_data.append((
            tx.get('report_file_id'),
            tx.get('broker_id'),
            tx.get('trade_date'),
            tx.get('settlement_date'),
            tx.get('ticker'),
            tx.get('isin'),
            tx.get('operation_type'),
            tx.get('quantity', 0),
            tx.get('price', 0),
            tx.get('amount', 0),
            tx.get('commission', 0),
            tx.get('tax', 0),
            tx.get('accrued_tax', 0),
            tx.get('currency', 'RUB'),
            tx.get('counterparty'),
            json.dumps(tx.get('original_row_data', {})),
            tx.get('ai_confidence', 0.0),
            tx.get('is_manual_correction', 0)
        ))
    
    cursor.executemany("""
        INSERT INTO transactions (
            report_file_id, broker_id, trade_date, settlement_date, ticker, isin,
            operation_type, quantity, price, amount, commission, tax, accrued_tax,
            currency, counterparty, original_row_data, ai_confidence, is_manual_correction
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, batch_data)
    
    conn.commit()
    conn.close()


def get_transactions(filters: Dict = None) -> List[Dict]:
    """Получить транзакции с фильтрами."""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM transactions WHERE 1=1"
    params = []
    
    if filters:
        if filters.get('broker_id'):
            query += " AND broker_id = ?"
            params.append(filters['broker_id'])
        if filters.get('ticker'):
            query += " AND ticker = ?"
            params.append(filters['ticker'])
        if filters.get('operation_type'):
            query += " AND operation_type = ?"
            params.append(filters['operation_type'])
        if filters.get('date_from'):
            query += " AND trade_date >= ?"
            params.append(filters['date_from'])
        if filters.get('date_to'):
            query += " AND trade_date <= ?"
            params.append(filters['date_to'])
        if filters.get('report_file_id'):
            query += " AND report_file_id = ?"
            params.append(filters['report_file_id'])
    
    query += " ORDER BY trade_date DESC, id DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        row_dict = dict(row)
        if row_dict.get('original_row_data'):
            row_dict['original_row_data'] = json.loads(row_dict['original_row_data'])
        result.append(row_dict)
    
    return result


def delete_transactions_for_file(file_id: int):
    """Удалить все транзакции для файла отчета."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transactions WHERE report_file_id = ?", (file_id,))
    conn.commit()
    conn.close()


# ============================================================================
# ИИ-обучение: RLHF логирование и веса модели
# ============================================================================

def log_ai_training_example(original_text: str, predicted: str, corrected: str, 
                           features: Dict = None, broker_context: str = None):
    """Записать пример коррекции ИИ для дообучения."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO ai_training_log 
        (original_text, predicted_type, corrected_type, feature_vector, broker_context)
        VALUES (?, ?, ?, ?, ?)
    """, (
        original_text,
        predicted,
        corrected,
        json.dumps(features) if features else None,
        broker_context
    ))
    
    conn.commit()
    conn.close()


def get_training_dataset(limit: int = None) -> List[Dict]:
    """Получить датасет для обучения модели."""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM ai_training_log ORDER BY created_at ASC"
    if limit:
        query += f" LIMIT {limit}"
    
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        row_dict = dict(row)
        if row_dict.get('feature_vector'):
            row_dict['feature_vector'] = json.loads(row_dict['feature_vector'])
        result.append(row_dict)
    
    return result


def save_ai_model_weights(weights: np.ndarray, vocabulary: Dict, model_version: str = "v1.0"):
    """Сохранить веса обученной модели."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Очистить старые веса
    cursor.execute("DELETE FROM ai_parser_weights")
    
    cursor.execute("""
        INSERT INTO ai_parser_weights 
        (model_version, weights_data, vocabulary_data, training_samples_count)
        VALUES (?, ?, ?, ?)
    """, (
        model_version,
        json.dumps(weights.tolist()),
        json.dumps(vocabulary),
        len(vocabulary)
    ))
    
    conn.commit()
    conn.close()


def load_ai_model_weights() -> Tuple[Optional[np.ndarray], Optional[Dict]]:
    """Загрузить веса модели."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM ai_parser_weights ORDER BY trained_at DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    
    if row:
        weights = np.array(json.loads(row['weights_data']))
        vocabulary = json.loads(row['vocabulary_data'])
        return weights, vocabulary
    
    return None, None


# ============================================================================
# Кэш котировок Мосбиржи
# ============================================================================

def save_moex_quote(ticker: str, quote_date: str, open_price: float, 
                    close_price: float, high_price: float, low_price: float,
                    volume: int = 0, currency: str = 'RUB'):
    """Сохранить котировку в кэш."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR REPLACE INTO moex_quotes_cache 
        (ticker, quote_date, open_price, close_price, high_price, low_price, volume, currency)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        ticker, quote_date, open_price, close_price, high_price, low_price, volume, currency
    ))
    
    conn.commit()
    conn.close()


def save_moex_quotes_batch(quotes: List[Dict]):
    """Пакетное сохранение котировок."""
    conn = get_connection()
    cursor = conn.cursor()
    
    batch_data = []
    for q in quotes:
        batch_data.append((
            q['ticker'],
            q['quote_date'],
            q.get('open_price'),
            q.get('close_price'),
            q.get('high_price'),
            q.get('low_price'),
            q.get('volume', 0),
            q.get('currency', 'RUB')
        ))
    
    cursor.executemany("""
        INSERT OR REPLACE INTO moex_quotes_cache 
        (ticker, quote_date, open_price, close_price, high_price, low_price, volume, currency)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, batch_data)
    
    conn.commit()
    conn.close()


def get_quotes_for_ticker(ticker: str, date_from: str = None, date_to: str = None) -> List[Dict]:
    """Получить исторические котировки для тикера."""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM moex_quotes_cache WHERE ticker = ?"
    params = [ticker]
    
    if date_from:
        query += " AND quote_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND quote_date <= ?"
        params.append(date_to)
    
    query += " ORDER BY quote_date ASC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def get_latest_quote(ticker: str) -> Optional[Dict]:
    """Получить последнюю доступную котировку."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM moex_quotes_cache 
        WHERE ticker = ? 
        ORDER BY quote_date DESC LIMIT 1
    """, (ticker,))
    
    row = cursor.fetchone()
    conn.close()
    
    return dict(row) if row else None


# ============================================================================
# Метаданные бумаг
# ============================================================================

def save_security_metadata(ticker: str, isin: str = None, security_type: str = None,
                          sector: str = None, industry: str = None, 
                          currency_nominal: str = None, issuer_name: str = None):
    """Сохранить метаданные бумаги."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR REPLACE INTO securities_metadata 
        (ticker, isin, security_type, sector, industry, currency_nominal, issuer_name, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (
        ticker, isin, security_type, sector, industry, currency_nominal, issuer_name
    ))
    
    conn.commit()
    conn.close()


def get_security_metadata(ticker: str) -> Optional[Dict]:
    """Получить метаданные бумаги."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM securities_metadata WHERE ticker = ?", (ticker,))
    row = cursor.fetchone()
    conn.close()
    
    return dict(row) if row else None


# ============================================================================
# Расчеты: FIFO, Средняя цена, XIRR
# ============================================================================

def calculate_fifo_positions(ticker: str, broker_id: int = None) -> Dict:
    """
    Рассчитать позицию по методу FIFO.
    Возвращает: {quantity, average_price, realized_pnl, lots: [...]}
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Получить все транзакции по тику
    if broker_id:
        query = "SELECT * FROM transactions WHERE ticker = ? AND operation_type IN ('BUY', 'SELL') AND broker_id = ? ORDER BY trade_date ASC, id ASC"
        params = [ticker, broker_id]
    else:
        query = "SELECT * FROM transactions WHERE ticker = ? AND operation_type IN ('BUY', 'SELL') ORDER BY trade_date ASC, id ASC"
        params = [ticker]
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    lots = []  # Список лотов: [{quantity, price, remaining}]
    total_realized_pnl = 0.0
    current_quantity = 0.0
    
    for row in rows:
        tx = dict(row)
        qty = tx['quantity']
        price = tx['price']
        
        if tx['operation_type'] == 'BUY':
            # Добавить новый лот
            lots.append({
                'quantity': qty,
                'remaining': qty,
                'price': price,
                'date': tx['trade_date']
            })
            current_quantity += qty
            
        elif tx['operation_type'] == 'SELL':
            # Продать из старых лотов (FIFO)
            qty_to_sell = qty
            while qty_to_sell > 0 and lots:
                oldest_lot = lots[0]
                
                if oldest_lot['remaining'] <= qty_to_sell:
                    # Лот полностью продан
                    sell_qty = oldest_lot['remaining']
                    pnl = (price - oldest_lot['price']) * sell_qty
                    total_realized_pnl += pnl
                    qty_to_sell -= sell_qty
                    lots.pop(0)
                else:
                    # Лот частично продан
                    pnl = (price - oldest_lot['price']) * qty_to_sell
                    total_realized_pnl += pnl
                    oldest_lot['remaining'] -= qty_to_sell
                    qty_to_sell = 0
            
            current_quantity -= qty
    
    # Рассчитать среднюю цену покупки
    total_cost = sum(lot['price'] * lot['remaining'] for lot in lots)
    avg_price = total_cost / current_quantity if current_quantity > 0 else 0.0
    
    return {
        'ticker': ticker,
        'quantity': current_quantity,
        'average_price': avg_price,
        'realized_pnl': total_realized_pnl,
        'lots': lots
    }


def calculate_xirr(cash_flows: List[Tuple[str, float]], guess: float = 0.1) -> float:
    """
    Рассчитать XIRR (доходность с учетом времени) методом Ньютона-Рафсона.
    
    cash_flows: список кортежей (date_str, amount)
    amount: положительный для притока, отрицательный для оттока
    """
    if not cash_flows:
        return 0.0
    
    # Преобразовать даты в дни от первой даты
    base_date = min(cf[0] for cf in cash_flows)
    base = datetime.strptime(base_date, '%Y-%m-%d') if isinstance(base_date, str) else base_date
    
    def npv(rate):
        """NPV для данной ставки."""
        total = 0.0
        for date, amount in cash_flows:
            d = datetime.strptime(date, '%Y-%m-%d') if isinstance(date, str) else date
            days_diff = (d - base).days
            total += amount / ((1 + rate) ** (days_diff / 365.0))
        return total
    
    def npv_derivative(rate):
        """Производная NPV."""
        total = 0.0
        for date, amount in cash_flows:
            d = datetime.strptime(date, '%Y-%m-%d') if isinstance(date, str) else date
            days_diff = (d - base).days
            total -= (days_diff / 365.0) * amount / ((1 + rate) ** (days_diff / 365.0 + 1))
        return total
    
    try:
        xirr = newton(npv, guess, fprime=npv_derivative, tol=1e-7, maxiter=100)
        return xirr
    except (RuntimeError, ZeroDivisionError):
        return 0.0


def calculate_portfolio_summary(broker_id: int = None) -> Dict:
    """
    Рассчитать сводку портфеля.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Получить уникальные тикеры
    query = "SELECT DISTINCT ticker FROM transactions WHERE operation_type = 'BUY'"
    params = []
    
    if broker_id:
        query += " AND broker_id = ?"
        params.append(broker_id)
    
    cursor.execute(query, params)
    tickers = [row['ticker'] for row in cursor.fetchall()]
    conn.close()
    
    positions = []
    total_market_value = 0.0
    total_invested = 0.0
    total_realized_pnl = 0.0
    
    for ticker in tickers:
        pos = calculate_fifo_positions(ticker, broker_id)
        
        if pos['quantity'] > 0:
            # Получить текущую цену
            latest_quote = get_latest_quote(ticker)
            current_price = latest_quote['close_price'] if latest_quote else pos['average_price']
            
            market_value = pos['quantity'] * current_price
            invested = pos['quantity'] * pos['average_price']
            unrealized_pnl = market_value - invested
            
            positions.append({
                'ticker': ticker,
                'quantity': pos['quantity'],
                'average_price': pos['average_price'],
                'current_price': current_price,
                'market_value': market_value,
                'unrealized_pnl': unrealized_pnl,
                'realized_pnl': pos['realized_pnl']
            })
            
            total_market_value += market_value
            total_invested += invested
            total_realized_pnl += pos['realized_pnl']
    
    # Рассчитать доли
    for pos in positions:
        pos['weight_percent'] = (pos['market_value'] / total_market_value * 100) if total_market_value > 0 else 0
    
    return {
        'positions': positions,
        'total_market_value': total_market_value,
        'total_invested': total_invested,
        'total_unrealized_pnl': total_market_value - total_invested,
        'total_realized_pnl': total_realized_pnl,
        'total_pnl': (total_market_value - total_invested) + total_realized_pnl
    }


# Инициализация при импорте
init_database()

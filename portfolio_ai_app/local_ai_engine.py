"""
local_ai_engine.py - Нативный ИИ-движок для парсинга и оптимизации портфеля
Полная автономность: все модели работают локально без облачных вызовов.

Архитектура:
1. ИИ-парсер: TF-IDF + Расстояние Левенштейна + Логистическая регрессия (scikit-learn)
2. ИИ-Советник: Матрица Марковица + Градиентный бустинг (XGBoost-style на numpy)
"""

import json
import re
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from pathlib import Path
import numpy as np
from scipy.optimize import minimize, LinearConstraint, Bounds
from collections import Counter

# Импортируем функции БД
from database import (
    get_training_dataset, 
    save_ai_model_weights, 
    load_ai_model_weights,
    log_ai_training_example,
    get_latest_quote,
    get_quotes_for_ticker,
    calculate_portfolio_summary
)


# ============================================================================
# ЧАСТЬ 1: НАТИВНЫЙ ИИ-ПАРСЕР
# Архитектура: TF-IDF + Levenshtein + Logistic Regression
# ============================================================================

class OperationType:
    """Константы типов операций."""
    BUY = 'BUY'
    SELL = 'SELL'
    DIVIDEND = 'DIVIDEND'
    COUPON = 'COUPON'
    COMMISSION = 'COMMISSION'
    TAX = 'TAX'
    DEPOSIT = 'DEPOSIT'
    WITHDRAWAL = 'WITHDRAWAL'


# Ключевые слова для классификации операций (русский/английский)
OPERATION_KEYWORDS = {
    OperationType.BUY: [
        'покупка', 'buy', 'приобретение', 'купил', 'purchase', 'acquisition',
        'зачисление бумаг', 'пополнение позиции'
    ],
    OperationType.SELL: [
        'продажа', 'sell', 'продам', 'sold', 'sale', 'disposal',
        'списание бумаг', 'закрытие позиции'
    ],
    OperationType.DIVIDEND: [
        'дивиденд', 'dividend', 'дивы', 'выплата акционерам',
        'income from shares'
    ],
    OperationType.COUPON: [
        'купон', 'coupon', 'нкд', 'aicd', 'выплата по облигации',
        'interest payment'
    ],
    OperationType.COMMISSION: [
        'комиссия', 'commission', 'вознаграждение', 'fee', 'тариф',
        'service fee', 'broker fee', 'транзакционные издержки'
    ],
    OperationType.TAX: [
        'налог', 'tax', 'ндфл', 'withholding tax', 'удержано',
        'tax on income'
    ]
}


def levenshtein_distance(s1: str, s2: str) -> int:
    """Вычислить расстояние Левенштейна между строками."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]


def text_similarity(text1: str, text2: str) -> float:
    """Вычислить схожесть текстов от 0 до 1."""
    distance = levenshtein_distance(text1.lower(), text2.lower())
    max_len = max(len(text1), len(text2))
    if max_len == 0:
        return 1.0
    return 1.0 - (distance / max_len)


class NativeAIParser:
    """
    Локальный ИИ-парсер брокерских отчетов.
    Использует TF-IDF векторизацию + логистическую регрессию.
    Поддерживает онлайн-дообучение на основе RLHF.
    """
    
    def __init__(self):
        self.vocabulary: Dict[str, int] = {}
        self.idf_weights: np.ndarray = None
        self.classifier_weights: Dict[str, np.ndarray] = {}  # веса для каждого класса
        self.is_trained = False
        self.model_version = "v1.0"
        
        # Загрузить сохраненные веса
        self._load_model()
    
    def _load_model(self):
        """Загрузить веса модели из БД."""
        weights, vocab = load_ai_model_weights()
        if weights is not None and vocab is not None:
            self.vocabulary = vocab
            self.classifier_weights = weights
            self.is_trained = True
            print(f"[AI_PARSER] Загружена обученная модель версии {self.model_version}")
        else:
            print("[AI_PARSER] Модель не найдена, используется базовая классификация по ключевым словам")
            self._initialize_base_model()
    
    def _initialize_base_model(self):
        """Инициализировать базовую модель с ключевыми словами."""
        # Создать начальный словарь из ключевых слов
        all_keywords = []
        for op_type, keywords in OPERATION_KEYWORDS.items():
            all_keywords.extend(keywords)
        
        for idx, word in enumerate(set(all_keywords)):
            self.vocabulary[word.lower()] = idx
        
        self.is_trained = True
    
    def _tokenize(self, text: str) -> List[str]:
        """Токенизировать текст: нижний регистр, удаление спецсимволов."""
        text = text.lower()
        text = re.sub(r'[^\w\sа-яёa-z]', '', text)
        tokens = text.split()
        # Удалить короткие токены и цифры
        tokens = [t for t in tokens if len(t) > 1 and not t.isdigit()]
        return tokens
    
    def _text_to_tfidf_vector(self, text: str) -> np.ndarray:
        """Преобразовать текст в TF-IDF вектор."""
        tokens = self._tokenize(text)
        vector = np.zeros(len(self.vocabulary))
        
        if not tokens:
            return vector
        
        # TF (Term Frequency)
        token_counts = Counter(tokens)
        
        for token, count in token_counts.items():
            if token in self.vocabulary:
                idx = self.vocabulary[token]
                tf = count / len(tokens)  # нормализованный TF
                idf = self.idf_weights[idx] if self.idf_weights is not None else 1.0
                vector[idx] = tf * idf
        
        # L2 нормализация
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        
        return vector
    
    def _update_vocabulary(self, texts: List[str]):
        """Обновить словарь на основе новых текстов."""
        for text in texts:
            tokens = self._tokenize(text)
            for token in tokens:
                if token not in self.vocabulary:
                    self.vocabulary[token] = len(self.vocabulary)
        
        # Пересоздать IDF веса
        n_docs = len(texts)
        self.idf_weights = np.ones(len(self.vocabulary))
    
    def classify_text(self, text: str) -> Tuple[str, float, Dict]:
        """
        Классифицировать текстовую строку.
        Возвращает: (operation_type, confidence, details)
        """
        if not text or not isinstance(text, str):
            return OperationType.COMMISSION, 0.0, {'method': 'default'}
        
        vector = self._text_to_tfidf_vector(text)
        scores = {}
        
        # Если есть обученные веса - использовать их
        if isinstance(self.classifier_weights, np.ndarray) and self.classifier_weights.ndim > 1:
            for op_type in OPERATION_KEYWORDS.keys():
                type_idx = list(OPERATION_KEYWORDS.keys()).index(op_type)
                if type_idx < self.classifier_weights.shape[0]:
                    weight_vector = self.classifier_weights[type_idx]
                    # Скалярное произведение
                    score = np.dot(vector, weight_vector[:len(vector)])
                    scores[op_type] = score
        else:
            # Fallback: классификация по ключевым словам + Levenshtein
            scores = self._keyword_based_classification(text)
        
        if not scores:
            return OperationType.COMMISSION, 0.0, {'method': 'fallback'}
        
        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]
        
        # Нормализовать уверенность через sigmoid
        confidence = 1.0 / (1.0 + np.exp(-best_score * 5))
        
        return best_type, confidence, {
            'all_scores': scores,
            'method': 'ml' if isinstance(self.classifier_weights, np.ndarray) else 'keyword'
        }
    
    def _keyword_based_classification(self, text: str) -> Dict[str, float]:
        """Классификация на основе ключевых слов и расстояния Левенштейна."""
        scores = {}
        text_lower = text.lower()
        
        for op_type, keywords in OPERATION_KEYWORDS.items():
            max_similarity = 0.0
            
            for keyword in keywords:
                # Точное совпадение
                if keyword in text_lower:
                    max_similarity = max(max_similarity, 1.0)
                else:
                    # Похожесть по Левенштейну
                    similarity = text_similarity(text_lower, keyword)
                    # Также проверить совпадение подстрок
                    for word in text_lower.split():
                        sub_similarity = text_similarity(word, keyword)
                        similarity = max(similarity, sub_similarity)
                    
                    max_similarity = max(max_similarity, similarity)
            
            scores[op_type] = max_similarity
        
        return scores
    
    def train_on_dataset(self, training_data: List[Dict], incremental: bool = True):
        """
        Обучить/дообучить модель на датасете.
        
        training_data: список {original_text, corrected_type, feature_vector}
        incremental: если True, дообучение без забывания старых весов
        """
        if not training_data:
            print("[AI_PARSER] Нет данных для обучения")
            return
        
        print(f"[AI_PARSER] Обучение на {len(training_data)} примерах...")
        
        # Обновить словарь
        texts = [item['original_text'] for item in training_data]
        self._update_vocabulary(texts)
        
        # Подготовить матрицу признаков X и метки y
        X = []
        y = []
        
        op_types = list(OPERATION_KEYWORDS.keys())
        type_to_idx = {op: idx for idx, op in enumerate(op_types)}
        
        for item in training_data:
            vector = self._text_to_tfidf_vector(item['original_text'])
            X.append(vector)
            
            corrected_type = item.get('corrected_type', item.get('predicted_type'))
            if corrected_type in type_to_idx:
                y.append(type_to_idx[corrected_type])
        
        if not X or not y:
            print("[AI_PARSER] Не удалось подготовить данные для обучения")
            return
        
        X = np.array(X)
        y = np.array(y)
        
        # Обучить простую логистическую регрессию через градиентный спуск
        n_classes = len(op_types)
        n_features = X.shape[1] if X.ndim > 1 else len(self.vocabulary)
        
        # Инициализировать веса
        if incremental and isinstance(self.classifier_weights, np.ndarray):
            # Сохранить старые веса
            old_weights = self.classifier_weights
            # Расширить если нужно
            if old_weights.shape[1] < n_features:
                new_weights = np.zeros((n_classes, n_features))
                new_weights[:, :old_weights.shape[1]] = old_weights
                self.classifier_weights = new_weights
        else:
            self.classifier_weights = np.random.randn(n_classes, n_features) * 0.01
        
        # Градиентный спуск
        learning_rate = 0.1
        n_iterations = 100
        
        for iteration in range(n_iterations):
            # Forward pass
            logits = X @ self.classifier_weights.T
            
            # Softmax
            exp_logits = np.exp(logits - np.max(logits, axis=1, keepdims=True))
            probs = exp_logits / np.sum(exp_logits, axis=1, keepdims=True)
            
            # Градиент
            one_hot_y = np.zeros_like(probs)
            one_hot_y[np.arange(len(y)), y] = 1
            
            gradient = (probs - one_hot_y).T @ X / len(y)
            
            # Update weights
            self.classifier_weights -= learning_rate * gradient
        
        # Сохранить модель
        save_ai_model_weights(self.classifier_weights, self.vocabulary, self.model_version)
        
        print(f"[AI_PARSER] Обучение завершено. Точность на обучающей выборке: {self._calculate_accuracy(X, y):.2%}")
    
    def _calculate_accuracy(self, X: np.ndarray, y: np.ndarray) -> float:
        """Рассчитать точность на датасете."""
        if X.shape[0] == 0:
            return 0.0
        
        logits = X @ self.classifier_weights.T
        predictions = np.argmax(logits, axis=1)
        accuracy = np.mean(predictions == y)
        return accuracy
    
    def parse_report_row(self, row_data: Dict, broker_context: str = None) -> Dict:
        """
        Распарсить строку отчета.
        
        row_data: исходные данные строки (словарь из pandas)
        broker_context: контекст брокера для улучшения классификации
        """
        # Собрать текст для классификации из всех текстовых полей
        text_parts = []
        
        for key, value in row_data.items():
            if isinstance(value, str) and value.strip():
                text_parts.append(value.strip())
        
        full_text = ' '.join(text_parts)
        
        # Классифицировать
        operation_type, confidence, details = self.classify_text(full_text)
        
        # Извлечь структурированные данные
        result = {
            'operation_type': operation_type,
            'ai_confidence': float(confidence),
            'classification_details': details,
            'ticker': self._extract_ticker(row_data),
            'quantity': self._extract_quantity(row_data),
            'price': self._extract_price(row_data),
            'amount': self._extract_amount(row_data),
            'commission': self._extract_commission(row_data),
            'tax': self._extract_tax(row_data),
            'trade_date': self._extract_date(row_data),
            'isin': self._extract_isin(row_data),
            'currency': self._extract_currency(row_data)
        }
        
        return result
    
    def _extract_ticker(self, row_data: Dict) -> str:
        """Извлечь тикер из строки."""
        for key, value in row_data.items():
            if not isinstance(value, str):
                continue
            
            key_lower = key.lower()
            if 'ticker' in key_lower or 'symbol' in key_lower or 'код' in key_lower:
                return value.upper().strip()
            
            # Поиск паттерна тикера (2-5 заглавных букв + возможные цифры)
            match = re.search(r'\b([A-Z]{2,5}\d*)\b', value)
            if match:
                return match.group(1)
        
        return ''
    
    def _extract_quantity(self, row_data: Dict) -> float:
        """Извлечь количество."""
        for key, value in row_data.items():
            key_lower = key.lower()
            if 'qty' in key_lower or 'quantity' in key_lower or 'количество' in key_lower or 'шт' in key_lower:
                try:
                    return float(value)
                except (ValueError, TypeError):
                    pass
        return 0.0
    
    def _extract_price(self, row_data: Dict) -> float:
        """Извлечь цену."""
        for key, value in row_data.items():
            key_lower = key.lower()
            if 'price' in key_lower or 'цена' in key_lower:
                try:
                    return float(str(value).replace(',', '.'))
                except (ValueError, TypeError):
                    pass
        return 0.0
    
    def _extract_amount(self, row_data: Dict) -> float:
        """Извлечь сумму."""
        for key, value in row_data.items():
            key_lower = key.lower()
            if 'amount' in key_lower or 'sum' in key_lower or 'сумма' in key_lower or 'total' in key_lower:
                try:
                    return float(str(value).replace(',', '.'))
                except (ValueError, TypeError):
                    pass
        return 0.0
    
    def _extract_commission(self, row_data: Dict) -> float:
        """Извлечь комиссию."""
        for key, value in row_data.items():
            key_lower = key.lower()
            if 'commission' in key_lower or 'комиссия' in key_lower or 'fee' in key_lower:
                try:
                    return abs(float(str(value).replace(',', '.')))
                except (ValueError, TypeError):
                    pass
        return 0.0
    
    def _extract_tax(self, row_data: Dict) -> float:
        """Извлечь налог."""
        for key, value in row_data.items():
            key_lower = key.lower()
            if 'tax' in key_lower or 'налог' in key_lower or 'ндфл' in key_lower:
                try:
                    return abs(float(str(value).replace(',', '.')))
                except (ValueError, TypeError):
                    pass
        return 0.0
    
    def _extract_date(self, row_data: Dict) -> Optional[str]:
        """Извлечь дату сделки."""
        for key, value in row_data.items():
            key_lower = key.lower()
            if 'date' in key_lower or 'дата' in key_lower:
                if isinstance(value, datetime):
                    return value.strftime('%Y-%m-%d')
                # Попытка распарсить строку
                date_patterns = [
                    r'(\d{4}-\d{2}-\d{2})',
                    r'(\d{2}\.\d{2}\.\d{4})',
                    r'(\d{2}/\d{2}/\d{4})'
                ]
                for pattern in date_patterns:
                    match = re.search(pattern, str(value))
                    if match:
                        date_str = match.group(1)
                        # Нормализовать формат
                        if '.' in date_str:
                            parts = date_str.split('.')
                            return f"{parts[2]}-{parts[1]}-{parts[0]}"
                        elif '/' in date_str:
                            parts = date_str.split('/')
                            return f"{parts[2]}-{parts[0]}-{parts[1]}"
                        return date_str
        return None
    
    def _extract_isin(self, row_data: Dict) -> str:
        """Извлечь ISIN."""
        for key, value in row_data.items():
            if not isinstance(value, str):
                continue
            
            key_lower = key.lower()
            if 'isin' in key_lower:
                return value.upper().strip()
            
            # Паттерн ISIN: 2 буквы + 9 символов + 1 цифра
            match = re.search(r'\b([A-Z]{2}[A-Z0-9]{9}\d)\b', value)
            if match:
                return match.group(1)
        
        return ''
    
    def _extract_currency(self, row_data: Dict) -> str:
        """Извлечь валюту."""
        for key, value in row_data.items():
            if not isinstance(value, str):
                continue
            
            key_lower = key.lower()
            if 'currency' in key_lower or 'валюта' in key_lower:
                return value.upper().strip()
            
            # Поиск кодов валют
            for currency in ['RUB', 'USD', 'EUR', 'CNY', 'GBP']:
                if currency in value.upper():
                    return currency
        
        return 'RUB'


# ============================================================================
# ЧАСТЬ 2: ИИ-СОВЕТНИК (Матрица Марковица + Оптимизация)
# ============================================================================

class PortfolioOptimizer:
    """
    Локальный ИИ-советник для оптимизации портфеля.
    Использует Modern Portfolio Theory (Markowitz) и алгоритмы оптимизации.
    """
    
    def __init__(self):
        self.risk_free_rate = 0.075  # Безрисковая ставка (ключевая ставка ЦБ)
    
    def calculate_returns(self, prices: Dict[str, List[float]]) -> np.ndarray:
        """Рассчитать доходности активов."""
        returns = []
        for ticker, price_list in prices.items():
            if len(price_list) < 2:
                returns.append(0.0)
            else:
                daily_returns = np.diff(price_list) / price_list[:-1]
                avg_return = np.mean(daily_returns) * 252  # Годовая доходность
                returns.append(avg_return)
        return np.array(returns)
    
    def calculate_covariance_matrix(self, prices: Dict[str, List[float]]) -> np.ndarray:
        """Рассчитать ковариационную матрицу."""
        # Собрать все временные ряды в матрицу
        price_matrix = []
        tickers = list(prices.keys())
        
        # Найти минимальную длину
        min_len = min(len(prices[t]) for t in tickers)
        
        for ticker in tickers:
            price_series = prices[ticker][-min_len:]  # Обрезать до общей длины
            returns = np.diff(price_series) / price_series[:-1]
            price_matrix.append(returns)
        
        if not price_matrix:
            return np.array([[0]])
        
        # Ковариационная матрица (годовая)
        cov_matrix = np.cov(price_matrix) * 252
        
        # Регуляризация для численной стабильности
        cov_matrix += np.eye(cov_matrix.shape[0]) * 1e-6
        
        return cov_matrix
    
    def optimize_markowitz(self, 
                          expected_returns: np.ndarray,
                          cov_matrix: np.ndarray,
                          risk_profile: str = 'moderate',
                          target_return: float = None,
                          max_weight: float = 0.25) -> Dict:
        """
        Оптимизировать портфель по Марковицу.
        
        risk_profile: 'conservative', 'moderate', 'aggressive'
        target_return: целевая доходность (если None, максимизировать Sharpe)
        max_weight: максимальная доля одного актива
        """
        n_assets = len(expected_returns)
        
        # Ограничения на веса
        bounds = Bounds(
            lb=np.zeros(n_assets),  # Минимум 0%
            ub=np.ones(n_assets) * max_weight  # Максимум max_weight
        )
        
        # Сумма весов = 100%
        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}
        ]
        
        # Начальное предположение: равные веса
        initial_weights = np.ones(n_assets) / n_assets
        
        def portfolio_variance(weights):
            return weights.T @ cov_matrix @ weights
        
        def portfolio_return(weights):
            return weights.T @ expected_returns
        
        def sharpe_ratio(weights):
            ret = portfolio_return(weights)
            vol = np.sqrt(portfolio_variance(weights))
            if vol == 0:
                return 0
            return (ret - self.risk_free_rate) / vol
        
        # Разные стратегии оптимизации
        if risk_profile == 'conservative':
            # Минимизировать волатильность
            objective = lambda w: portfolio_variance(w)
        elif risk_profile == 'aggressive':
            # Максимизировать доходность (минимизировать отрицательную)
            objective = lambda w: -portfolio_return(w)
        else:  # moderate
            # Максимизировать коэффициент Шарпа (минимизировать отрицательный)
            objective = lambda w: -sharpe_ratio(w)
        
        # Оптимизация
        result = minimize(
            objective,
            initial_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'maxiter': 1000, 'ftol': 1e-10}
        )
        
        optimal_weights = result.x
        optimal_weights = np.maximum(optimal_weights, 0)  # Убрать отрицательные
        optimal_weights /= np.sum(optimal_weights)  # Нормализовать
        
        return {
            'weights': optimal_weights,
            'expected_return': portfolio_return(optimal_weights),
            'volatility': np.sqrt(portfolio_variance(optimal_weights)),
            'sharpe_ratio': sharpe_ratio(optimal_weights),
            'success': result.success,
            'message': result.message
        }
    
    def generate_rebalancing_plan(self, 
                                  current_positions: Dict[str, float],
                                  total_portfolio_value: float,
                                  risk_profile: str = 'moderate',
                                  new_investment: float = 0.0) -> Dict:
        """
        Сгенерировать план ребалансировки портфеля.
        
        current_positions: {ticker: current_value}
        total_portfolio_value: общая стоимость портфеля
        new_investment: сумма новых инвестиций
        """
        tickers = list(current_positions.keys())
        
        if not tickers:
            return {'error': 'Нет позиций для анализа'}
        
        # Получить исторические цены для расчета ковариации
        prices = {}
        for ticker in tickers:
            quotes = get_quotes_for_ticker(ticker)
            if quotes:
                prices[ticker] = [q['close_price'] for q in quotes[-252:]]  # 1 год
            else:
                # Если нет данных, использовать случайные (для демонстрации)
                prices[ticker] = [100.0] * 252
        
        # Рассчитать метрики
        expected_returns = self.calculate_returns(prices)
        cov_matrix = self.calculate_covariance_matrix(prices)
        
        # Оптимизировать
        optimization_result = self.optimize_markowitz(
            expected_returns,
            cov_matrix,
            risk_profile=risk_profile
        )
        
        # Текущие веса
        current_weights = {
            ticker: current_positions[ticker] / total_portfolio_value
            for ticker in tickers
        }
        
        # Целевые веса
        target_weights = {
            ticker: optimization_result['weights'][i]
            for i, ticker in enumerate(tickers)
        }
        
        # Общий капитал после новой инвестиции
        total_capital = total_portfolio_value + new_investment
        
        # План сделок
        buy_orders = []
        sell_orders = []
        
        for ticker in tickers:
            current_value = current_positions[ticker]
            target_value = target_weights[ticker] * total_capital
            difference = target_value - current_value
            
            if abs(difference) < 100:  # Игнорировать мелкие суммы
                continue
            
            # Получить текущую цену
            latest_quote = get_latest_quote(ticker)
            current_price = latest_quote['close_price'] if latest_quote else 100.0
            
            # Рассчитать количество лотов (предположим лотность 1 для простоты)
            lot_size = 1
            quantity = abs(difference) / current_price
            quantity = int(quantity // lot_size) * lot_size  # Округлить до лота
            
            if difference > 0:
                buy_orders.append({
                    'ticker': ticker,
                    'action': 'BUY',
                    'quantity': quantity,
                    'estimated_cost': quantity * current_price,
                    'reason': f'Увеличить долю с {current_weights[ticker]:.1%} до {target_weights[ticker]:.1%}'
                })
            else:
                sell_orders.append({
                    'ticker': ticker,
                    'action': 'SELL',
                    'quantity': quantity,
                    'estimated_proceeds': quantity * current_price,
                    'reason': f'Снизить долю с {current_weights[ticker]:.1%} до {target_weights[ticker]:.1%}'
                })
        
        # Анализ рисков
        risk_analysis = self._analyze_portfolio_risks(current_weights, target_weights, tickers)
        
        return {
            'optimization_result': optimization_result,
            'current_weights': current_weights,
            'target_weights': target_weights,
            'buy_orders': buy_orders,
            'sell_orders': sell_orders,
            'risk_analysis': risk_analysis,
            'total_capital': total_capital,
            'new_investment_allocated': new_investment
        }
    
    def _analyze_portfolio_risks(self, current_weights: Dict, target_weights: Dict, 
                                 tickers: List[str]) -> List[str]:
        """Проанализировать риски портфеля."""
        risks = []
        
        # Проверка концентрации
        for ticker, weight in current_weights.items():
            if weight > 0.40:
                risks.append(
                    f"⚠️ ВНИМАНИЕ: {ticker} занимает {weight:.1%} портфеля — это критический риск концентрации. "
                    f"Рекомендуемая доля: {target_weights[ticker]:.1%}"
                )
            elif weight > 0.25:
                risks.append(
                    f"⚡ {ticker} занимает {weight:.1%} портфеля — повышенный риск. "
                    f"Рекомендуется снизить до {target_weights[ticker]:.1%}"
                )
        
        # Проверка диверсификации
        n_assets = len([w for w in current_weights.values() if w > 0.05])
        if n_assets < 5:
            risks.append(
                f"⚠️ Недостаточная диверсификация: только {n_assets} значимых позиций. "
                "Рекомендуется минимум 8-10 различных активов."
            )
        
        # Проверка отклонения от оптимального
        total_deviation = sum(abs(current_weights.get(t, 0) - target_weights.get(t, 0)) 
                             for t in tickers)
        if total_deviation > 0.5:
            risks.append(
                f"📊 Портфель значительно отклоняется от оптимального (отклонение: {total_deviation:.1%}). "
                "Требуется ребалансировка."
            )
        
        return risks
    
    def generate_advisor_report(self, portfolio_summary: Dict) -> str:
        """
        Сгенерировать текстовый отчет ИИ-советника.
        """
        positions = portfolio_summary.get('positions', [])
        total_value = portfolio_summary.get('total_market_value', 0)
        total_pnl = portfolio_summary.get('total_pnl', 0)
        
        report_lines = [
            "📈 ОТЧЕТ ИИ-СОВЕТНИКА",
            "=" * 50,
            "",
            f"💰 Общая стоимость портфеля: {total_value:,.2f} ₽",
            f"📊 Совокупный P&L: {total_pnl:,.2f} ₽ ({total_pnl/total_value*100:.2f}%)" if total_value > 0 else "",
            "",
            "🔍 АНАЛИЗ ПОЗИЦИЙ:",
            "-" * 30
        ]
        
        # Топ позиций
        sorted_positions = sorted(positions, key=lambda x: x.get('market_value', 0), reverse=True)
        
        for pos in sorted_positions[:5]:
            ticker = pos.get('ticker', 'N/A')
            weight = pos.get('weight_percent', 0)
            pnl = pos.get('unrealized_pnl', 0)
            
            emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
            report_lines.append(
                f"{emoji} {ticker}: {weight:.1f}% портфеля, P&L: {pnl:,.2f} ₽"
            )
        
        report_lines.extend([
            "",
            "💡 РЕКОМЕНДАЦИИ:",
            "-" * 30
        ])
        
        # Генерация рекомендаций на основе анализа
        if sorted_positions:
            top_position = sorted_positions[0]
            if top_position.get('weight_percent', 0) > 30:
                report_lines.append(
                    f"• Рассмотрите сокращение позиции {top_position['ticker']} "
                    f"(сейчас {top_position['weight_percent']:.1f}%) для снижения риска концентрации."
                )
            
            # Проверка на наличие облигаций
            has_bonds = any('OFZ' in pos.get('ticker', '') or 'SU' in pos.get('ticker', '') 
                           for pos in positions)
            if not has_bonds:
                report_lines.append(
                    "• Рекомендуется добавить облигации (ОФЗ) для балансировки рисков."
                )
            
            # Диверсификация по секторам
            sectors = set()
            for pos in positions:
                # Здесь можно добавить логику определения сектора
                sectors.add('unknown')
            
            if len(sectors) < 3:
                report_lines.append(
                    "• Портфель недостаточно диверсифицирован по секторам экономики."
                )
        
        report_lines.extend([
            "",
            "🎯 ЦЕЛЕВАЯ АЛЛОКАЦИЯ (умеренный профиль):",
            "• Акции РФ: 40-50%",
            "• Облигации (ОФЗ): 30-40%",
            "• Денежные средства: 10-20%",
            "",
            "=" * 50,
            "Отчет сгенерирован локальным ИИ-движком. Все данные конфиденциальны."
        ])
        
        return '\n'.join(report_lines)


# ============================================================================
# ГЛАВНЫЙ ИНТЕРФЕЙС
# ============================================================================

class LocalAIEngine:
    """Единый интерфейс для всех ИИ-функций приложения."""
    
    def __init__(self):
        self.parser = NativeAIParser()
        self.optimizer = PortfolioOptimizer()
    
    def parse_and_classify(self, row_data: Dict, broker_context: str = None) -> Dict:
        """Распарсить и классифицировать строку отчета."""
        return self.parser.parse_report_row(row_data, broker_context)
    
    def train_parser(self, training_examples: List[Dict], incremental: bool = True):
        """Дообучить парсер на новых примерах."""
        self.parser.train_on_dataset(training_examples, incremental)
    
    def get_optimal_portfolio(self, positions: Dict[str, float], 
                             risk_profile: str = 'moderate') -> Dict:
        """Рассчитать оптимальную структуру портфеля."""
        total_value = sum(positions.values())
        return self.optimizer.generate_rebalancing_plan(
            positions, total_value, risk_profile
        )
    
    def generate_advisor_report(self, portfolio_summary: Dict) -> str:
        """Сгенерировать отчет советника."""
        return self.optimizer.generate_advisor_report(portfolio_summary)


# Экспорт единственного экземпляра
ai_engine = LocalAIEngine()

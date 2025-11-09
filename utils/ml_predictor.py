"""
BINAUTOGO - Machine Learning Predictor
Дополнительный сигнал к DeepSeek через ML
"""

import logging
import pickle
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import lightgbm as lgb

logger = logging.getLogger('BINAUTOGO.MLPredictor')


class MLPredictor:
    """
    Machine Learning предиктор
    Обучается на исторических данных и дополняет DeepSeek
    """
    
    def __init__(self):
        """Инициализация ML моделей"""
        # Ансамбль моделей
        self.models = {
            'random_forest': RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42
            ),
            'gradient_boost': GradientBoostingClassifier(
                n_estimators=100,
                max_depth=5,
                random_state=42
            ),
            'xgboost': xgb.XGBClassifier(
                n_estimators=100,
                max_depth=5,
                random_state=42
            ),
            'lightgbm': lgb.LGBMClassifier(
                n_estimators=100,
                max_depth=5,
                random_state=42
            )
        }
        
        self.scaler = StandardScaler()
        self.is_trained = False
        
        # Хранилище данных для обучения
        self.training_data = []
        
        # Путь для сохранения моделей
        self.models_dir = Path('data/ml_models')
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        # Загрузка сохранённых моделей
        self._load_models()
        
        logger.info("✅ MLPredictor инициализирован")
    
    def extract_features(self, signal, market_data=None) -> np.ndarray:
        """
        Извлечение признаков из сигнала
        
        Args:
            signal: Trading signal
            market_data: Рыночные данные (опционально)
            
        Returns:
            Массив признаков
        """
        features = []
        
        # Признаки из сигнала
        features.append(signal.confidence)
        features.append(1 if signal.direction == 'buy' else 0)
        features.append(signal.quantity)
        features.append((signal.take_profit - signal.price) / signal.price)  # Потенциальная прибыль
        features.append((signal.price - signal.stop_loss) / signal.price)  # Потенциальный убыток
        
        # Risk/Reward
        risk = abs(signal.price - signal.stop_loss)
        reward = abs(signal.take_profit - signal.price)
        features.append(reward / risk if risk > 0 else 0)
        
        # Признаки из анализа DeepSeek
        features.append(signal.analysis.confidence)
        features.append(signal.analysis.risk_score / 10)  # Нормализация
        
        # Признаки из market_data (если есть)
        if market_data:
            indicators = market_data.get('indicators', {})
            features.append(indicators.get('rsi_5m', 50) / 100)  # Нормализация
            features.append(indicators.get('rsi_1h', 50) / 100)
            features.append(indicators.get('volume_ratio', 1.0))
            features.append(indicators.get('bb_position', 0.5))
            
            # Изменение цены
            features.append(market_data.get('price_change_24h', 0) / 100)
        else:
            # Заглушки если нет market_data
            features.extend([0.5, 0.5, 1.0, 0.5, 0.0])
        
        # Временные признаки
        now = datetime.now()
        features.append(now.hour / 24)  # Час дня
        features.append(now.weekday() / 7)  # День недели
        
        return np.array(features).reshape(1, -1)
    
    def predict_trade_success(self, signal, market_data=None) -> float:
        """
        Предсказание успешности сделки
        
        Args:
            signal: Trading signal
            market_data: Рыночные данные
            
        Returns:
            Вероятность успеха (0-1)
        """
        if not self.is_trained:
            logger.debug("ML модель не обучена, возвращаем нейтральную оценку")
            return signal.confidence
        
        try:
            # Извлечение признаков
            features = self.extract_features(signal, market_data)
            
            # Нормализация
            features_scaled = self.scaler.transform(features)
            
            # Предсказания от всех моделей
            predictions = []
            for model_name, model in self.models.items():
                try:
                    pred = model.predict_proba(features_scaled)[0][1]  # Вероятность класса 1
                    predictions.append(pred)
                except Exception as e:
                    logger.debug(f"Ошибка предсказания {model_name}: {e}")
            
            # Усреднение предсказаний (ансамбль)
            if predictions:
                avg_prediction = np.mean(predictions)
                logger.debug(f"ML предсказание: {avg_prediction:.2%}")
                return avg_prediction
            else:
                return signal.confidence
                
        except Exception as e:
            logger.error(f"Ошибка ML предсказания: {e}")
            return signal.confidence
    
    def add_training_data(self, signal, order, outcome=None):
        """
        Добавление данных для обучения
        
        Args:
            signal: Trading signal
            order: Исполненный ордер
            outcome: Результат сделки (опционально)
        """
        features = self.extract_features(signal)
        
        # Если outcome не указан, ждём закрытия позиции
        self.training_data.append({
            'features': features,
            'signal': signal,
            'order': order,
            'outcome': outcome,
            'timestamp': datetime.now()
        })
        
        logger.debug(f"Добавлены данные для обучения. Всего: {len(self.training_data)}")
    
    def train_on_history(self, trades_history: list):
        """
        Обучение на истории сделок
        
        Args:
            trades_history: История сделок из PortfolioTracker
        """
        if len(trades_history) < 50:
            logger.info(f"Недостаточно данных для обучения: {len(trades_history)}/50")
            return
        
        logger.info(f"🤖 Начало обучения ML на {len(trades_history)} сделках...")
        
        try:
            # Подготовка данных
            X = []
            y = []
            
            for trade in trades_history:
                if trade['status'] != 'closed':
                    continue
                
                # Упрощённое извлечение признаков из истории
                features = [
                    trade.get('signal_confidence', 0.5),
                    1 if trade['side'] == 'buy' else 0,
                    trade['quantity'],
                    (trade['exit_price'] - trade['entry_price']) / trade['entry_price'],
                    0.03,  # Предполагаемый risk
                    2.0,   # Предполагаемый R/R
                    trade.get('signal_confidence', 0.5),
                    5 / 10,  # Средний риск
                    0.5, 0.5, 1.0, 0.5, 0.0,  # Технические индикаторы (средние)
                    12 / 24,  # Среднее время
                    2 / 7     # Средний день недели
                ]
                
                X.append(features)
                
                # Целевая переменная: 1 если прибыль, 0 если убыток
                y.append(1 if trade['pnl'] > 0 else 0)
            
            X = np.array(X)
            y = np.array(y)
            
            # Нормализация
            X_scaled = self.scaler.fit_transform(X)
            
            # Обучение каждой модели
            trained_count = 0
            for model_name, model in self.models.items():
                try:
                    model.fit(X_scaled, y)
                    
                    # Оценка точности
                    accuracy = model.score(X_scaled, y)
                    logger.info(f"  ✅ {model_name}: точность {accuracy:.2%}")
                    
                    trained_count += 1
                except Exception as e:
                    logger.error(f"  ❌ Ошибка обучения {model_name}: {e}")
            
            if trained_count > 0:
                self.is_trained = True
                logger.info(f"✅ ML модели обучены! ({trained_count}/4)")
                
                # Сохранение моделей
                self._save_models()
            else:
                logger.error("❌ Не удалось обучить ни одну модель")
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка обучения: {e}")
    
    def _save_models(self):
        """Сохранение обученных моделей"""
        try:
            # Сохранение каждой модели
            for model_name, model in self.models.items():
                model_path = self.models_dir / f"{model_name}.pkl"
                with open(model_path, 'wb') as f:
                    pickle.dump(model, f)
            
            # Сохранение scaler
            scaler_path = self.models_dir / "scaler.pkl"
            with open(scaler_path, 'wb') as f:
                pickle.dump(self.scaler, f)
            
            logger.info(f"💾 ML модели сохранены в {self.models_dir}")
            
        except Exception as e:
            logger.error(f"Ошибка сохранения моделей: {e}")
    
    def _load_models(self):
        """Загрузка сохранённых моделей"""
        try:
            # Проверка наличия файлов
            scaler_path = self.models_dir / "scaler.pkl"
            if not scaler_path.exists():
                logger.debug("Сохранённые модели не найдены")
                return
            
            # Загрузка scaler
            with open(scaler_path, 'rb') as f:
                self.scaler = pickle.load(f)
            
            # Загрузка моделей
            loaded_count = 0
            for model_name in self.models.keys():
                model_path = self.models_dir / f"{model_name}.pkl"
                if model_path.exists():
                    with open(model_path, 'rb') as f:
                        self.models[model_name] = pickle.load(f)
                    loaded_count += 1
            
            if loaded_count > 0:
                self.is_trained = True
                logger.info(f"✅ Загружено ML моделей: {loaded_count}/4")
            
        except Exception as e:
            logger.error(f"Ошибка загрузки моделей: {e}")
    
    def get_feature_importance(self) -> dict:
        """Важность признаков"""
        if not self.is_trained:
            return {}
        
        feature_names = [
            'confidence', 'direction', 'quantity', 'potential_profit',
            'potential_loss', 'risk_reward', 'deepseek_confidence',
            'risk_score', 'rsi_5m', 'rsi_1h', 'volume_ratio',
            'bb_position', 'price_change_24h', 'hour', 'weekday'
        ]
        
        importance = {}
        
        try:
            # Берём Random Forest для feature importance
            rf_model = self.models.get('random_forest')
            if rf_model and hasattr(rf_model, 'feature_importances_'):
                for name, imp in zip(feature_names, rf_model.feature_importances_):
                    importance[name] = float(imp)
        except Exception as e:
            logger.error(f"Ошибка получения важности: {e}")
        
        return importance


# Тестирование
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    from core.signal_generator import TradingSignal
    from core.deepseek_analyzer import MarketAnalysis
    
    print("🧪 Тестирование MLPredictor...\n")
    
    predictor = MLPredictor()
    
    # Создание тестового сигнала
    test_analysis = MarketAnalysis(
        symbol='BTC/USDT',
        direction='bullish',
        confidence=0.75,
        entry_price=43500.0,
        target_price=45000.0,
        stop_loss=42500.0,
        position_size=0.15,
        reasoning='Тест',
        risk_score=5,
        timeframe='1h',
        timestamp=datetime.now()
    )
    
    test_signal = TradingSignal(
        symbol='BTC/USDT',
        direction='buy',
        signal_type='long',
        strength=0.75,
        price=43500.0,
        quantity=0.1,
        stop_loss=42500.0,
        take_profit=45000.0,
        confidence=0.75,
        analysis=test_analysis,
        reasoning='Тест',
        timestamp=datetime.now()
    )
    
    # Предсказание
    prediction = predictor.predict_trade_success(test_signal)
    print(f"Предсказание: {prediction:.2%}")
    
    # Симуляция истории для обучения
    mock_history = []
    for i in range(100):
        mock_history.append({
            'timestamp': datetime.now(),
            'symbol': 'BTC/USDT',
            'side': 'buy',
            'quantity': 0.1,
            'entry_price': 43000 + i*10,
            'exit_price': 43500 + i*10,
            'pnl': 50 if i % 3 != 0 else -20,
            'signal_confidence': 0.7,
            'status': 'closed'
        })
    
    # Обучение
    predictor.train_on_history(mock_history)
    
    # Повторное предсказание
    prediction_after = predictor.predict_trade_success(test_signal)
    print(f"Предсказание после обучения: {prediction_after:.2%}")
    
    print("\n✅ Тест завершён!")

"""
BINAUTOGO - Pump Detector
Детектор пампов для быстрого реагирования на всплески
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass
import time

from config.settings import config

logger = logging.getLogger('BINAUTOGO.PumpDetector')


@dataclass
class PumpSignal:
    """Сигнал о пампе"""
    symbol: str
    trigger_price: float
    current_price: float
    price_change_percent: float
    volume_change: float
    order_book_imbalance: float
    confidence: float
    timestamp: datetime
    is_valid: bool = True


class PumpDetector:
    """
    Детектор пампов
    
    Анализирует:
    - Резкий рост цены
    - Всплеск объёма
    - Дисбаланс ордербука (доминация покупателей)
    - Скорость изменения цены
    """
    
    def __init__(self, market_data_manager, strategy):
        """
        Args:
            market_data_manager: Менеджер рыночных данных
            strategy: Текущая стратегия
        """
        self.market_data = market_data_manager
        self.strategy = strategy
        
        # История цен для отслеживания
        self.price_history: Dict[str, List[Dict]] = {}
        
        # История обнаруженных пампов
        self.pump_history: List[PumpSignal] = []
        
        # Параметры детектора
        self.price_threshold = 0.03  # 3% рост за минуту
        self.volume_multiplier = 3.0  # x3 от среднего объёма
        self.orderbook_threshold = 0.65  # 65% покупателей
        self.lookback_minutes = 5  # Анализ последних 5 минут
        
        # Счётчики
        self.pumps_detected = 0
        self.false_positives = 0
        
        logger.info("✅ PumpDetector инициализирован")
    
    def scan_markets(self, symbols: List[str]) -> List[PumpSignal]:
        """
        Сканирование рынков на пампы
        
        Args:
            symbols: Список символов для сканирования
            
        Returns:
            Список обнаруженных пампов
        """
        detected_pumps = []
        
        for symbol in symbols:
            try:
                pump = self.detect_pump(symbol)
                
                if pump and pump.is_valid:
                    detected_pumps.append(pump)
                    self.pumps_detected += 1
                    
                    logger.info(
                        f"🚀 ПАМП ОБНАРУЖЕН: {symbol} "
                        f"+{pump.price_change_percent:.2f}% "
                        f"Уверенность: {pump.confidence*100:.0f}%"
                    )
                    
            except Exception as e:
                logger.error(f"Ошибка сканирования {symbol}: {e}")
        
        return detected_pumps
    
    def detect_pump(self, symbol: str) -> Optional[PumpSignal]:
        """
        Обнаружение пампа для конкретного символа
        
        Args:
            symbol: Торговая пара
            
        Returns:
            PumpSignal или None
        """
        try:
            # Получение текущих данных
            current_data = self.market_data.get_market_summary(symbol)
            
            if not current_data:
                return None
            
            current_price = current_data['current_price']
            current_volume = current_data['volume_24h']
            
            # Обновление истории цен
            self._update_price_history(symbol, current_price, current_volume)
            
            # Проверка наличия достаточной истории
            if symbol not in self.price_history or len(self.price_history[symbol]) < 3:
                return None
            
            # Анализ изменения цены
            price_change = self._calculate_price_change(symbol)
            
            if price_change < self.price_threshold:
                return None  # Недостаточный рост
            
            # Анализ объёма
            volume_change = self._calculate_volume_change(symbol)
            
            if volume_change < self.volume_multiplier:
                return None  # Недостаточный объём
            
            # Анализ ордербука
            orderbook_imbalance = self._analyze_orderbook(symbol)
            
            if orderbook_imbalance < self.orderbook_threshold:
                return None  # Недостаточная доминация покупателей
            
            # Расчёт уверенности
            confidence = self._calculate_confidence(
                price_change, 
                volume_change, 
                orderbook_imbalance
            )
            
            # Создание сигнала
            pump_signal = PumpSignal(
                symbol=symbol,
                trigger_price=self.price_history[symbol][-2]['price'],
                current_price=current_price,
                price_change_percent=price_change * 100,
                volume_change=volume_change,
                order_book_imbalance=orderbook_imbalance,
                confidence=confidence,
                timestamp=datetime.now()
            )
            
            # Валидация сигнала
            pump_signal.is_valid = self._validate_pump_signal(pump_signal)
            
            if pump_signal.is_valid:
                self.pump_history.append(pump_signal)
            
            return pump_signal
            
        except Exception as e:
            logger.error(f"Ошибка детекции пампа {symbol}: {e}")
            return None
    
    def _update_price_history(self, symbol: str, price: float, volume: float):
        """Обновление истории цен"""
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        
        # Добавление новой точки
        self.price_history[symbol].append({
            'timestamp': datetime.now(),
            'price': price,
            'volume': volume
        })
        
        # Удаление старых данных (> lookback_minutes)
        cutoff_time = datetime.now() - timedelta(minutes=self.lookback_minutes)
        self.price_history[symbol] = [
            p for p in self.price_history[symbol]
            if p['timestamp'] > cutoff_time
        ]
    
    def _calculate_price_change(self, symbol: str) -> float:
        """
        Расчёт изменения цены
        
        Returns:
            Процент изменения (0.03 = 3%)
        """
        history = self.price_history[symbol]
        
        if len(history) < 2:
            return 0.0
        
        # Сравнение текущей цены с ценой минуту назад
        current_price = history[-1]['price']
        previous_price = history[-2]['price']
        
        change = (current_price - previous_price) / previous_price
        
        return change
    
    def _calculate_volume_change(self, symbol: str) -> float:
        """
        Расчёт изменения объёма
        
        Returns:
            Множитель от среднего (3.0 = x3)
        """
        history = self.price_history[symbol]
        
        if len(history) < 3:
            return 0.0
        
        # Средний объём за период
        avg_volume = sum(p['volume'] for p in history[:-1]) / (len(history) - 1)
        
        # Текущий объём
        current_volume = history[-1]['volume']
        
        if avg_volume == 0:
            return 0.0
        
        return current_volume / avg_volume
    
    def _analyze_orderbook(self, symbol: str) -> float:
        """
        Анализ дисбаланса ордербука
        
        Returns:
            Процент доминации покупателей (0.65 = 65%)
        """
        try:
            # Получение ордербука
            orderbook = self.market_data.exchange.fetch_order_book(symbol, limit=20)
            
            # Суммирование объёмов
            bid_volume = sum(bid[1] for bid in orderbook['bids'])
            ask_volume = sum(ask[1] for ask in orderbook['asks'])
            
            total_volume = bid_volume + ask_volume
            
            if total_volume == 0:
                return 0.5  # Нейтрально
            
            # Доля покупателей
            buy_dominance = bid_volume / total_volume
            
            return buy_dominance
            
        except Exception as e:
            logger.debug(f"Ошибка анализа ордербука {symbol}: {e}")
            return 0.5
    
    def _calculate_confidence(self, price_change: float, 
                             volume_change: float, 
                             orderbook_imbalance: float) -> float:
        """
        Расчёт уверенности в пампе
        
        Returns:
            Уверенность от 0.0 до 1.0
        """
        # Нормализация параметров
        price_score = min(price_change / 0.10, 1.0)  # Макс при 10%
        volume_score = min(volume_change / 5.0, 1.0)  # Макс при x5
        orderbook_score = orderbook_imbalance  # Уже 0-1
        
        # Взвешенная сумма
        confidence = (
            price_score * 0.4 +      # 40% вес
            volume_score * 0.35 +    # 35% вес
            orderbook_score * 0.25   # 25% вес
        )
        
        return confidence
    
    def _validate_pump_signal(self, signal: PumpSignal) -> bool:
        """
        Валидация сигнала пампа
        
        Args:
            signal: Сигнал пампа
            
        Returns:
            True если валиден
        """
        checks = []
        
        # 1. Минимальная уверенность
        checks.append(('Уверенность', signal.confidence >= 0.6))
        
        # 2. Недавние пампы по этому символу
        recent_pumps = [
            p for p in self.pump_history
            if p.symbol == signal.symbol 
            and p.timestamp > datetime.now() - timedelta(minutes=30)
        ]
        checks.append(('Частота', len(recent_pumps) < 3))
        
        # 3. Максимальное количество активных пампов
        active_pumps = self._get_active_pump_count()
        max_pumps = self.strategy.max_pump_pairs if hasattr(self.strategy, 'max_pump_pairs') else 5
        checks.append(('Лимит', active_pumps < max_pumps))
        
        # 4. Изменение цены не слишком экстремальное (> 50% = подозрительно)
        checks.append(('Реалистичность', signal.price_change_percent < 50))
        
        # Логирование
        failed = [name for name, passed in checks if not passed]
        if failed:
            logger.debug(f"Сигнал отклонён: {', '.join(failed)}")
        
        return all(passed for _, passed in checks)
    
    def _get_active_pump_count(self) -> int:
        """Количество активных пампов (последние 10 минут)"""
        cutoff = datetime.now() - timedelta(minutes=10)
        return len([p for p in self.pump_history if p.timestamp > cutoff])
    
    def create_pump_signal(self, pump: PumpSignal):
        """
        Создание торгового сигнала из пампа
        
        Args:
            pump: Обнаруженный памп
            
        Returns:
            TradingSignal для исполнения
        """
        from core.signal_generator import TradingSignal
        from core.deepseek_analyzer import MarketAnalysis
        
        # Создание быстрого анализа для пампа
        analysis = MarketAnalysis(
            symbol=pump.symbol,
            direction='bullish',
            confidence=pump.confidence,
            entry_price=pump.current_price,
            target_price=pump.current_price * (1 + self.strategy.pump_up_percent / 100),
            stop_loss=pump.current_price * 0.97,  # 3% стоп-лосс
            position_size=self.strategy.pump_order_multiplier * 0.1,
            reasoning=f"Памп обнаружен: +{pump.price_change_percent:.2f}%, объём x{pump.volume_change:.1f}",
            risk_score=7,  # Высокий риск для пампов
            timeframe='1m',
            timestamp=datetime.now()
        )
        
        signal = TradingSignal(
            symbol=pump.symbol,
            direction='buy',
            signal_type='long',
            strength=pump.confidence,
            price=pump.current_price,
            quantity=0.0,  # Будет рассчитано в risk manager
            stop_loss=analysis.stop_loss,
            take_profit=analysis.target_price,
            confidence=pump.confidence,
            analysis=analysis,
            reasoning=analysis.reasoning,
            timestamp=datetime.now()
        )
        
        return signal
    
    def get_statistics(self) -> Dict:
        """Статистика детектора пампов"""
        active_count = self._get_active_pump_count()
        
        return {
            'total_detected': self.pumps_detected,
            'active_now': active_count,
            'false_positives': self.false_positives,
            'success_rate': (
                (self.pumps_detected - self.false_positives) / self.pumps_detected
                if self.pumps_detected > 0 else 0
            ),
            'symbols_tracked': len(self.price_history)
        }
    
    def mark_false_positive(self, symbol: str):
        """Отметить памп как ложное срабатывание"""
        self.false_positives += 1
        logger.warning(f"⚠️ Ложный памп: {symbol}")


# Тестирование
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    from core.market_data import MarketDataManager
    from config.strategies import STRATEGY_100
    
    print("🧪 Тестирование PumpDetector...\n")
    
    # Инициализация
    market_data = MarketDataManager()
    detector = PumpDetector(market_data, STRATEGY_100)
    
    # Тест сканирования
    print("🔍 Сканирование рынков...")
    test_symbols = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT']
    
    pumps = detector.scan_markets(test_symbols)
    
    if pumps:
        print(f"\n🚀 Обнаружено пампов: {len(pumps)}")
        for pump in pumps:
            print(f"\n  {pump.symbol}:")
            print(f"    Изменение цены: +{pump.price_change_percent:.2f}%")
            print(f"    Объём: x{pump.volume_change:.1f}")
            print(f"    Ордербук: {pump.order_book_imbalance*100:.0f}% покупателей")
            print(f"    Уверенность: {pump.confidence*100:.0f}%")
    else:
        print("\n📭 Пампы не обнаружены")
    
    # Статистика
    print(f"\n📊 Статистика детектора:")
    stats = detector.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print("\n✅ Тест завершён!")

"""
BINAUTOGO - Signal Generator
Генерация торговых сигналов на основе анализа DeepSeek
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List
from dataclasses import dataclass

from config.settings import config
from core.deepseek_analyzer import DeepSeekAnalyzer, MarketAnalysis

logger = logging.getLogger('BINAUTOGO.SignalGenerator')


@dataclass
class TradingSignal:
    """Торговый сигнал"""
    symbol: str
    direction: str  # 'buy', 'sell', 'hold'
    signal_type: str  # 'long', 'short'
    strength: float  # 0.0 - 1.0
    price: float
    quantity: float
    stop_loss: float
    take_profit: float
    confidence: float
    analysis: MarketAnalysis
    reasoning: str
    timestamp: datetime
    is_valid: bool = True
    
    # Дополнительные параметры из вашей стратегии
    leverage: float = 1.0  # Кредитное плечо
    position_mode: str = 'one-way'  # 'one-way' или 'hedge'


class SignalGenerator:
    """
    Генератор торговых сигналов
    Преобразует анализ DeepSeek в торгуемые сигналы
    """
    
    def __init__(self, analyzer: DeepSeekAnalyzer):
        """
        Args:
            analyzer: Экземпляр DeepSeekAnalyzer
        """
        self.analyzer = analyzer
        self.signal_history: List[TradingSignal] = []
        logger.info("✅ SignalGenerator инициализирован")
    
    def generate_signal(self, market_data: dict) -> Optional[TradingSignal]:
        """
        Генерация торгового сигнала
        
        Args:
            market_data: Рыночные данные
            
        Returns:
            TradingSignal или None
        """
        try:
            symbol = market_data['symbol']
            current_price = market_data['current_price']
            
            logger.debug(f"🔍 Генерация сигнала для {symbol} @ ${current_price:,.2f}")
            
            # Получение анализа от DeepSeek
            analysis = self.analyzer.analyze_market(market_data)
            
            if not analysis or not analysis.is_valid:
                logger.debug(f"⚠️ Анализ недействителен для {symbol}")
                return None
            
            # Проверка минимальной уверенности
            if analysis.confidence < config.MIN_CONFIDENCE:
                logger.debug(
                    f"⚠️ Низкая уверенность {analysis.confidence*100:.0f}% "
                    f"< {config.MIN_CONFIDENCE*100:.0f}% для {symbol}"
                )
                return None
            
            # Определение направления сигнала
            if analysis.direction == 'neutral':
                logger.debug(f"📭 Нейтральный сигнал для {symbol}")
                return None
            
            signal_type = 'long' if analysis.direction == 'bullish' else 'short'
            direction = 'buy' if signal_type == 'long' else 'sell'
            
            # Расчёт параметров сделки
            stop_loss = self._calculate_stop_loss(
                current_price, 
                signal_type, 
                analysis.stop_loss
            )
            
            take_profit = self._calculate_take_profit(
                current_price, 
                signal_type, 
                analysis.target_price
            )
            
            # Проверка Risk/Reward соотношения
            risk_reward_ratio = self._calculate_risk_reward(
                current_price, 
                stop_loss, 
                take_profit, 
                signal_type
            )
            
            if risk_reward_ratio < config.MIN_RISK_REWARD_RATIO:
                logger.info(
                    f"⚠️ Низкое R/R соотношение {risk_reward_ratio:.2f} "
                    f"< {config.MIN_RISK_REWARD_RATIO:.2f} для {symbol}"
                )
                return None
            
            # Расчёт количества (временно, будет уточнено в RiskManager)
            quantity = analysis.position_size
            
            # Создание сигнала
            signal = TradingSignal(
                symbol=symbol,
                direction=direction,
                signal_type=signal_type,
                strength=analysis.confidence,
                price=current_price,
                quantity=quantity,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=analysis.confidence,
                analysis=analysis,
                reasoning=analysis.reasoning,
                timestamp=datetime.now(),
                leverage=1.0  # По умолчанию без плеча
            )
            
            # Валидация сигнала
            signal.is_valid = self._validate_signal(signal, market_data)
            
            if signal.is_valid:
                logger.info(
                    f"✅ Сигнал сгенерирован: {symbol} {direction.upper()} "
                    f"@ ${current_price:,.2f}, SL: ${stop_loss:,.2f}, "
                    f"TP: ${take_profit:,.2f}, R/R: {risk_reward_ratio:.2f}"
                )
                self.signal_history.append(signal)
            
            return signal
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации сигнала: {e}")
            return None
    
    def _calculate_stop_loss(self, entry_price: float, signal_type: str, 
                            suggested_sl: float) -> float:
        """Расчёт уровня стоп-лосс"""
        # Используем предложенный DeepSeek или дефолтный
        if suggested_sl and suggested_sl > 0:
            if signal_type == 'long':
                return min(suggested_sl, entry_price * (1 - config.DEFAULT_STOP_LOSS_PERCENT))
            else:
                return max(suggested_sl, entry_price * (1 + config.DEFAULT_STOP_LOSS_PERCENT))
        else:
            # Дефолтный стоп-лосс
            if signal_type == 'long':
                return entry_price * (1 - config.DEFAULT_STOP_LOSS_PERCENT)
            else:
                return entry_price * (1 + config.DEFAULT_STOP_LOSS_PERCENT)
    
    def _calculate_take_profit(self, entry_price: float, signal_type: str,
                              suggested_tp: float) -> float:
        """Расчёт уровня тейк-профит"""
        # Используем предложенный DeepSeek или дефолтный
        if suggested_tp and suggested_tp > 0:
            if signal_type == 'long':
                return max(suggested_tp, entry_price * (1 + config.DEFAULT_TAKE_PROFIT_PERCENT))
            else:
                return min(suggested_tp, entry_price * (1 - config.DEFAULT_TAKE_PROFIT_PERCENT))
        else:
            # Дефолтный тейк-профит
            if signal_type == 'long':
                return entry_price * (1 + config.DEFAULT_TAKE_PROFIT_PERCENT)
            else:
                return entry_price * (1 - config.DEFAULT_TAKE_PROFIT_PERCENT)
    
    def _calculate_risk_reward(self, entry: float, stop_loss: float, 
                              take_profit: float, signal_type: str) -> float:
        """Расчёт соотношения риск/прибыль"""
        if signal_type == 'long':
            risk = entry - stop_loss
            reward = take_profit - entry
        else:  # short
            risk = stop_loss - entry
            reward = entry - take_profit
        
        if risk <= 0:
            return 0.0
        
        return reward / risk
    
    def _validate_signal(self, signal: TradingSignal, market_data: dict) -> bool:
        """
        Валидация торгового сигнала
        
        Args:
            signal: Торговый сигнал
            market_data: Рыночные данные
            
        Returns:
            True если сигнал валиден
        """
        checks = []
        
        # 1. Проверка близости цены входа к текущей цене
        price_diff = abs(signal.price - market_data['current_price']) / market_data['current_price']
        checks.append(('Цена входа', price_diff < 0.02))  # В пределах 2%
        
        # 2. Проверка уровней стоп-лосс и тейк-профит
        if signal.signal_type == 'long':
            checks.append(('Стоп-лосс', signal.stop_loss < signal.price))
            checks.append(('Тейк-профит', signal.take_profit > signal.price))
        else:
            checks.append(('Стоп-лосс', signal.stop_loss > signal.price))
            checks.append(('Тейк-профит', signal.take_profit < signal.price))
        
        # 3. Проверка индикаторов
        indicators = market_data.get('indicators', {})
        rsi = indicators.get('rsi_5m', 50)
        
        if signal.signal_type == 'long':
            # Для лонга: RSI не должен быть перекуплен
            checks.append(('RSI перекупленность', rsi < config.RSI_OVERBOUGHT))
        else:
            # Для шорта: RSI не должен быть перепродан
            checks.append(('RSI перепроданность', rsi > config.RSI_OVERSOLD))
        
        # 4. Проверка объёма
        volume_ratio = indicators.get('volume_ratio', 1.0)
        checks.append(('Объём', volume_ratio > 0.8))  # Хотя бы 80% среднего
        
        # 5. Проверка частоты сигналов (избегаем овертрейдинга)
        recent_signals = self._get_recent_signals(signal.symbol, minutes=60)
        checks.append(('Частота сигналов', len(recent_signals) < config.MAX_TRADES_PER_HOUR))
        
        # Логирование проверок
        failed_checks = [name for name, passed in checks if not passed]
        if failed_checks:
            logger.debug(f"⚠️ Провалены проверки: {', '.join(failed_checks)}")
        
        # Сигнал валиден если все проверки пройдены
        return all(passed for _, passed in checks)
    
    def _get_recent_signals(self, symbol: str, minutes: int = 60) -> List[TradingSignal]:
        """Получение недавних сигналов для символа"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [
            s for s in self.signal_history
            if s.symbol == symbol and s.timestamp > cutoff_time
        ]
    
    def get_signal_statistics(self) -> dict:
        """Статистика по сгенерированным сигналам"""
        if not self.signal_history:
            return {}
        
        valid_signals = [s for s in self.signal_history if s.is_valid]
        
        return {
            'total_signals': len(self.signal_history),
            'valid_signals': len(valid_signals),
            'invalid_signals': len(self.signal_history) - len(valid_signals),
            'avg_confidence': sum(s.confidence for s in valid_signals) / len(valid_signals) if valid_signals else 0,
            'long_signals': len([s for s in valid_signals if s.signal_type == 'long']),
            'short_signals': len([s for s in valid_signals if s.signal_type == 'short']),
        }
    
    def clear_old_signals(self, days: int = 7):
        """Очистка старых сигналов"""
        cutoff = datetime.now() - timedelta(days=days)
        initial_count = len(self.signal_history)
        self.signal_history = [s for s in self.signal_history if s.timestamp > cutoff]
        removed = initial_count - len(self.signal_history)
        if removed > 0:
            logger.info(f"🗑️ Удалено {removed} старых сигналов")


# Тестирование
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    from core.deepseek_analyzer import DeepSeekAnalyzer
    
    print("🧪 Тестирование SignalGenerator...\n")
    
    # Инициализация
    analyzer = DeepSeekAnalyzer()
    generator = SignalGenerator(analyzer)
    
    # Тестовые данные
    test_market_data = {
        'symbol': 'BTC/USDT',
        'current_price': 43500.0,
        'price_change_24h': 3.5,
        'volume_24h': 28500000000,
        'high_24h': 44200,
        'low_24h': 42100,
        'indicators': {
            'rsi_5m': 62.0,
            'rsi_1h': 58.0,
            'macd': 125.5,
            'macd_signal': 115.0,
            'macd_histogram': 10.5,
            'bb_position': 0.65,
            'volume_ratio': 1.25
        }
    }
    
    # Генерация сигнала
    signal = generator.generate_signal(test_market_data)
    
    if signal:
        print(f"✅ Сигнал сгенерирован:")
        print(f"   Символ: {signal.symbol}")
        print(f"   Направление: {signal.direction.upper()} ({signal.signal_type})")
        print(f"   Уверенность: {signal.confidence*100:.1f}%")
        print(f"   Цена входа: ${signal.price:,.2f}")
        print(f"   Стоп-лосс: ${signal.stop_loss:,.2f}")
        print(f"   Тейк-профит: ${signal.take_profit:,.2f}")
        print(f"   Валидность: {'✅' if signal.is_valid else '❌'}")
        print(f"\n   💭 Обоснование:\n   {signal.reasoning}")
    else:
        print("❌ Сигнал не сгенерирован")
    
    # Статистика
    print(f"\n📊 Статистика:")
    stats = generator.get_signal_statistics()
    for key, value in stats.items():
        print(f"   {key}: {value}")

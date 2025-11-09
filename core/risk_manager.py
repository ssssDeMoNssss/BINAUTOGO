"""
BINAUTOGO - Risk Manager
Управление рисками на основе вашей стратегии
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import pandas as pd

from config.settings import config
from core.signal_generator import TradingSignal

logger = logging.getLogger('BINAUTOGO.RiskManager')


class RiskManager:
    """
    Менеджер рисков
    Реализует вашу торговую стратегию с параметрами безопасности
    """
    
    def __init__(self):
        self.daily_pnl: List[float] = []
        self.trade_history: List[dict] = []
        
        logger.info("✅ RiskManager инициализирован")
        logger.info(f"⚙️ Макс. риск на сделку: {config.MAX_PORTFOLIO_RISK*100:.1f}%")
        logger.info(f"⚙️ Макс. просадка: {config.MAX_DRAWDOWN*100:.1f}%")
    
    def validate_signal(self, signal: TradingSignal, market_data: dict) -> TradingSignal:
        """
        Валидация и корректировка сигнала согласно риск-менеджменту
        
        Args:
            signal: Торговый сигнал
            market_data: Рыночные данные
            
        Returns:
            Скорректированный сигнал
        """
        if not signal or not signal.is_valid:
            return signal
        
        logger.debug(f"🔍 Проверка риска для {signal.symbol}")
        
        # 1. Проверка общей экспозиции портфеля
        signal = self._check_portfolio_exposure(signal)
        if not signal.is_valid:
            return signal
        
        # 2. Расчёт размера позиции
        signal = self._calculate_position_size(signal, market_data)
        
        # 3. Проверка лимита просадки
        signal = self._check_drawdown_limit(signal)
        if not signal.is_valid:
            return signal
        
        # 4. Проверка корреляции активов
        signal = self._check_correlation_limits(signal)
        
        # 5. Корректировка на волатильность
        signal = self._adjust_for_volatility(signal, market_data)
        
        # 6. Проверка баланса
        signal = self._check_sufficient_balance(signal)
        
        # 7. Проверка лимита сделок
        signal = self._check_trade_frequency(signal)
        
        if signal.is_valid:
            logger.info(f"✅ Риск-проверка пройдена для {signal.symbol}")
        else:
            logger.warning(f"⛔ Сигнал отклонён риск-менеджментом: {signal.symbol}")
        
        return signal
    
    def _check_portfolio_exposure(self, signal: TradingSignal) -> TradingSignal:
        """
        Проверка общей экспозиции портфеля
        Из вашей стратегии: position_size - Максимальная допустимая позиция 8-18%
        """
        try:
            current_exposure = self._get_current_exposure()
            portfolio_value = self._get_portfolio_value()
            
            # Значение новой позиции
            signal_value = signal.quantity * signal.price
            new_exposure = current_exposure + signal_value
            exposure_ratio = new_exposure / portfolio_value if portfolio_value > 0 else 0
            
            # Максимум 80% портфеля в позициях
            if exposure_ratio > 0.80:
                logger.warning(f"⚠️ Превышена максимальная экспозиция: {exposure_ratio*100:.1f}%")
                
                # Корректируем размер позиции
                max_signal_value = (0.80 * portfolio_value) - current_exposure
                if max_signal_value > 0:
                    signal.quantity = max_signal_value / signal.price
                    logger.info(f"📉 Размер позиции уменьшен до {signal.quantity:.6f}")
                else:
                    signal.is_valid = False
                    logger.warning("❌ Нет места для новой позиции")
            
            return signal
            
        except Exception as e:
            logger.error(f"Ошибка проверки экспозиции: {e}")
            signal.is_valid = False
            return signal
    
    def _calculate_position_size(self, signal: TradingSignal, market_data: dict) -> TradingSignal:
        """
        Расчёт размера позиции на основе вашей стратегии
        
        Параметры из вашего конфига:
        - position_size: 8-18% (базовый размер)
        - min_balance: 30% свободного баланса
        - leverage: x1 (без плеча по умолчанию)
        """
        try:
            portfolio_value = self._get_portfolio_value()
            free_balance = self._get_free_balance()
            
            # Базовый размер позиции (из DeepSeek анализа или конфига)
            base_position_size = signal.analysis.position_size
            
            # Корректировка на уверенность
            # Чем выше уверенность, тем больше размер (но в пределах лимитов)
            confidence_multiplier = (signal.confidence ** 2)  # Квадрат для более консервативного подхода
            
            # Корректировка на волатильность (чем выше волатильность, тем меньше позиция)
            volatility = self._calculate_volatility(market_data)
            volatility_adjustment = min(1.0, 0.02 / volatility) if volatility > 0 else 1.0
            
            # Корректировка на недавнюю производительность
            performance_multiplier = self._get_performance_multiplier()
            
            # Финальный размер позиции
            adjusted_size = (
                base_position_size * 
                confidence_multiplier * 
                volatility_adjustment * 
                performance_multiplier
            )
            
            # Применение лимитов из вашей стратегии
            adjusted_size = max(0.08, min(adjusted_size, config.MAX_POSITION_SIZE_PERCENT))  # 8-20%
            
            # Проверка минимального свободного баланса (30% по вашей стратегии)
            min_free_balance = portfolio_value * 0.30
            if free_balance < min_free_balance:
                logger.warning(f"⚠️ Низкий свободный баланс: {free_balance:.2f} < {min_free_balance:.2f}")
                # Уменьшаем размер позиции пропорционально
                adjusted_size *= (free_balance / min_free_balance)
            
            # Расчёт количества
            position_value = portfolio_value * adjusted_size
            signal.quantity = position_value / signal.price
            
            logger.debug(
                f"📊 Размер позиции: {adjusted_size*100:.1f}% "
                f"({signal.quantity:.6f} @ ${signal.price:.2f})"
            )
            
            return signal
            
        except Exception as e:
            logger.error(f"Ошибка расчёта размера позиции: {e}")
            signal.is_valid = False
            return signal
    
    def _check_drawdown_limit(self, signal: TradingSignal) -> TradingSignal:
        """
        Проверка лимита просадки
        Из вашей стратегии: max_drawdown 10%, emergency stop 15%
        """
        try:
            current_drawdown = self._calculate_current_drawdown()
            
            # Аварийная остановка при 15%
            if current_drawdown >= config.EMERGENCY_STOP_DRAWDOWN:
                logger.error(
                    f"🚨 АВАРИЙНАЯ ОСТАНОВКА! Просадка {current_drawdown*100:.1f}% "
                    f">= {config.EMERGENCY_STOP_DRAWDOWN*100:.1f}%"
                )
                signal.is_valid = False
                return signal
            
            # Уменьшение позиций при приближении к максимальной просадке
            if current_drawdown >= config.MAX_DRAWDOWN * 0.80:  # 80% от макс просадки
                reduction_factor = 0.5  # Уменьшаем позицию вдвое
                signal.quantity *= reduction_factor
                logger.warning(
                    f"⚠️ Просадка {current_drawdown*100:.1f}%, "
                    f"размер позиции уменьшен на {(1-reduction_factor)*100:.0f}%"
                )
            
            # Полная остановка при максимальной просадке
            if current_drawdown >= config.MAX_DRAWDOWN:
                logger.error(
                    f"🛑 Достигнут лимит просадки: {current_drawdown*100:.1f}%"
                )
                signal.is_valid = False
            
            return signal
            
        except Exception as e:
            logger.error(f"Ошибка проверки просадки: {e}")
            return signal
    
    def _check_correlation_limits(self, signal: TradingSignal) -> TradingSignal:
        """
        Проверка корреляции между активами
        Избегаем перегруза по коррелированным позициям
        """
        try:
            # Получаем текущие позиции
            current_positions = self._get_current_positions()
            
            if not current_positions:
                return signal
            
            # Упрощённая проверка корреляции по базовому активу
            # BTC коррелирует с большинством альткоинов
            btc_exposure = sum(
                pos['value'] for pos in current_positions
                if 'BTC' in pos['symbol']
            )
            
            portfolio_value = self._get_portfolio_value()
            btc_ratio = btc_exposure / portfolio_value if portfolio_value > 0 else 0
            
            # Если уже большая экспозиция на BTC, уменьшаем новые BTC позиции
            if 'BTC' in signal.symbol and btc_ratio > 0.40:
                reduction = 0.40 / btc_ratio
                signal.quantity *= reduction
                logger.info(f"📉 BTC экспозиция {btc_ratio*100:.1f}%, позиция уменьшена")
            
            return signal
            
        except Exception as e:
            logger.error(f"Ошибка проверки корреляции: {e}")
            return signal
    
    def _adjust_for_volatility(self, signal: TradingSignal, market_data: dict) -> TradingSignal:
        """
        Корректировка на волатильность
        Из вашей стратегии: учёт daily_percent (-7% до 5%)
        """
        try:
            # Дневное изменение цены
            daily_change = abs(market_data.get('price_change_24h', 0)) / 100
            
            # Если высокая волатильность (>5%), уменьшаем позицию
            if daily_change > 0.05:
                volatility_factor = 0.05 / daily_change
                signal.quantity *= volatility_factor
                logger.info(
                    f"⚡ Высокая волатильность {daily_change*100:.1f}%, "
                    f"позиция скорректирована"
                )
            
            return signal
            
        except Exception as e:
            logger.error(f"Ошибка корректировки на волатильность: {e}")
            return signal
    
    def _check_sufficient_balance(self, signal: TradingSignal) -> TradingSignal:
        """
        Проверка достаточности баланса
        Из вашей стратегии: min_balance 100 USD, min_bnb 0.04 BNB
        """
        try:
            free_balance = self._get_free_balance()
            position_value = signal.quantity * signal.price
            
            # Проверка минимального баланса
            if free_balance < config.MIN_BALANCE:
                logger.error(
                    f"❌ Недостаточный баланс: {free_balance:.2f} "
                    f"< {config.MIN_BALANCE:.2f} USD"
                )
                signal.is_valid = False
                return signal
            
            # Проверка что хватает на позицию
            if position_value > free_balance:
                # Корректируем количество под доступный баланс
                signal.quantity = free_balance / signal.price
                logger.warning(f"⚠️ Размер позиции скорректирован под баланс")
            
            return signal
            
        except Exception as e:
            logger.error(f"Ошибка проверки баланса: {e}")
            signal.is_valid = False
            return signal
    
    def _check_trade_frequency(self, signal: TradingSignal) -> TradingSignal:
        """
        Проверка частоты торговли
        Из вашей стратегии: max_trade_pairs 4, защита от паники
        """
        try:
            # Проверка количества позиций
            current_positions = self._get_current_positions()
            if len(current_positions) >= config.MAX_POSITIONS:
                logger.warning(
                    f"⚠️ Достигнут лимит позиций: "
                    f"{len(current_positions)}/{config.MAX_POSITIONS}"
                )
                signal.is_valid = False
                return signal
            
            # Проверка частоты сделок (защита от овертрейдинга)
            recent_trades = self._get_recent_trades(hours=1)
            if len(recent_trades) >= config.MAX_TRADES_PER_HOUR:
                logger.warning(
                    f"⚠️ Превышен лимит сделок в час: "
                    f"{len(recent_trades)}/{config.MAX_TRADES_PER_HOUR}"
                )
                signal.is_valid = False
                return signal
            
            return signal
            
        except Exception as e:
            logger.error(f"Ошибка проверки частоты: {e}")
            return signal
    
    def _calculate_volatility(self, market_data: dict) -> float:
        """Расчёт волатильности"""
        try:
            # Используем дневное изменение как прокси волатильности
            daily_change = abs(market_data.get('price_change_24h', 2.0))
            return daily_change / 100
        except:
            return 0.02  # 2% по умолчанию
    
    def _get_performance_multiplier(self) -> float:
        """
        Корректировка на основе недавней производительности
        Из вашей стратегии: учёт win rate и streak
        """
        if len(self.daily_pnl) < 10:
            return 1.0
        
        # Последние 10 сделок
        recent_pnl = self.daily_pnl[-10:]
        wins = sum(1 for pnl in recent_pnl if pnl > 0)
        win_rate = wins / len(recent_pnl)
        
        # Увеличиваем размер при хорошей производительности
        if win_rate > 0.70:
            return 1.2  # +20%
        elif win_rate < 0.30:
            return 0.6  # -40%
        else:
            return 1.0
    
    def _calculate_current_drawdown(self) -> float:
        """Расчёт текущей просадки"""
        if not self.daily_pnl:
            return 0.0
        
        cumulative_pnl = pd.Series(self.daily_pnl).cumsum()
        running_max = cumulative_pnl.expanding().max()
        drawdown = (cumulative_pnl - running_max) / running_max.abs()
        
        return abs(float(drawdown.iloc[-1])) if not drawdown.empty else 0.0
    
    def _get_current_exposure(self) -> float:
        """Получение текущей экспозиции"""
        positions = self._get_current_positions()
        return sum(pos['value'] for pos in positions)
    
    def _get_portfolio_value(self) -> float:
        """Получение стоимости портфеля"""
        # Это заглушка, реальное значение будет из OrderExecutor
        return 10000.0  # $10,000 по умолчанию
    
    def _get_free_balance(self) -> float:
        """Получение свободного баланса"""
        # Заглушка
        return 5000.0
    
    def _get_current_positions(self) -> List[dict]:
        """Получение текущих позиций"""
        # Заглушка
        return []
    
    def _get_recent_trades(self, hours: int = 1) -> List[dict]:
        """Получение недавних сделок"""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [
            t for t in self.trade_history
            if t.get('timestamp', datetime.min) > cutoff
        ]
    
    def log_trade(self, trade: dict):
        """Логирование сделки для статистики"""
        self.trade_history.append(trade)
        if 'pnl' in trade:
            self.daily_pnl.append(trade['pnl'])
    
    def get_risk_metrics(self) -> dict:
        """Получение метрик риска"""
        return {
            'current_drawdown': self._calculate_current_drawdown(),
            'total_trades': len(self.trade_history),
            'current_exposure': self._get_current_exposure(),
            'free_balance': self._get_free_balance(),
            'portfolio_value': self._get_portfolio_value(),
        }


# Тестирование
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    from core.deepseek_analyzer import DeepSeekAnalyzer, MarketAnalysis
    from core.signal_generator import SignalGenerator, TradingSignal
    
    print("🧪 Тестирование RiskManager...\n")
    
    # Создание тестового сигнала
    test_analysis = MarketAnalysis(
        symbol='BTC/USDT',
        direction='bullish',
        confidence=0.75,
        entry_price=43500.0,
        target_price=45000.0,
        stop_loss=42500.0,
        position_size=0.15,
        reasoning='Тестовый анализ',
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
    
    test_market_data = {
        'symbol': 'BTC/USDT',
        'current_price': 43500.0,
        'price_change_24h': 2.5,
    }
    
    # Инициализация и тест
    risk_manager = RiskManager()
    validated_signal = risk_manager.validate_signal(test_signal, test_market_data)
    
    print(f"Результат валидации: {'✅ ПРИНЯТ' if validated_signal.is_valid else '❌ ОТКЛОНЁН'}")
    print(f"Скорректированное количество: {validated_signal.quantity:.6f}")
    
    print(f"\n📊 Метрики риска:")
    for key, value in risk_manager.get_risk_metrics().items():
        print(f"   {key}: {value}")

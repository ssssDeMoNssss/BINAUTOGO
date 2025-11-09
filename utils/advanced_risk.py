"""
BINAUTOGO - Advanced Risk Manager
Kelly Criterion и продвинутое управление рисками
"""

import logging
import numpy as np
from typing import Dict, Optional

logger = logging.getLogger('BINAUTOGO.AdvancedRisk')


class AdvancedRiskManager:
    """
    Продвинутое управление рисками
    
    Функции:
    - Kelly Criterion для размера позиций
    - Динамическое управление рисками
    - Адаптация к производительности
    """
    
    def __init__(self, portfolio_tracker):
        """
        Args:
            portfolio_tracker: Трекер портфеля для статистики
        """
        self.portfolio_tracker = portfolio_tracker
        
        # Параметры Kelly
        self.kelly_fraction = 0.25  # Используем 25% от полного Kelly (консервативно)
        self.min_position_size = 0.05  # Минимум 5% от портфеля
        self.max_position_size = 0.25  # Максимум 25% от портфеля
        
        logger.info("✅ AdvancedRiskManager инициализирован")
    
    def calculate_kelly_position_size(self, signal, performance_metrics: Dict) -> float:
        """
        Расчёт размера позиции по Kelly Criterion
        
        Kelly Formula: f* = (bp - q) / b
        где:
        - f* = оптимальная доля капитала
        - b = отношение выигрыша к ставке (odds)
        - p = вероятность выигрыша
        - q = вероятность проигрыша (1-p)
        
        Args:
            signal: Торговый сигнал
            performance_metrics: Метрики производительности
            
        Returns:
            Размер позиции (количество)
        """
        try:
            # Получение win rate и средних значений
            if not performance_metrics or performance_metrics.get('total_trades', 0) < 10:
                # Недостаточно данных - используем базовый размер
                logger.debug("Недостаточно данных для Kelly, используем базовый размер")
                return signal.quantity
            
            win_rate = performance_metrics.get('win_rate', 0.5)
            avg_win = performance_metrics.get('avg_win', 0)
            avg_loss = abs(performance_metrics.get('avg_loss', 0))
            
            # Расчёт odds (b)
            if avg_loss > 0:
                odds = avg_win / avg_loss
            else:
                odds = 2.0  # Дефолтное значение
            
            # Kelly Criterion
            p = win_rate
            q = 1 - p
            
            kelly_percentage = (odds * p - q) / odds
            
            # Применение фракционного Kelly (консервативно)
            fractional_kelly = kelly_percentage * self.kelly_fraction
            
            # Ограничение диапазона
            fractional_kelly = max(self.min_position_size, 
                                  min(fractional_kelly, self.max_position_size))
            
            # Корректировка на уверенность сигнала
            confidence_adjusted = fractional_kelly * signal.confidence
            
            # Расчёт количества
            from config.settings import config
            portfolio_value = 10000.0  # Заглушка, должно браться из OrderExecutor
            
            try:
                # Попытка получить реальное значение
                from core.order_executor import OrderExecutor
                executor = OrderExecutor()
                balance = executor.get_balance()
                if balance:
                    portfolio_value = balance
            except:
                pass
            
            position_value = portfolio_value * confidence_adjusted
            quantity = position_value / signal.price
            
            logger.debug(
                f"Kelly расчёт: win_rate={win_rate:.2%}, odds={odds:.2f}, "
                f"kelly%={kelly_percentage:.2%}, fractional={fractional_kelly:.2%}, "
                f"final={confidence_adjusted:.2%}"
            )
            
            logger.info(f"📊 Kelly размер: {quantity:.6f} (${position_value:.2f})")
            
            return quantity
            
        except Exception as e:
            logger.error(f"Ошибка расчёта Kelly: {e}")
            return signal.quantity
    
    def calculate_optimal_stop_loss(self, signal, volatility: float = None) -> float:
        """
        Расчёт оптимального стоп-лосса на основе волатильности
        
        Args:
            signal: Торговый сигнал
            volatility: Волатильность актива (опционально)
            
        Returns:
            Оптимальный уровень стоп-лосса
        """
        try:
            # Базовый стоп-лосс из сигнала
            base_stop = signal.stop_loss
            
            # Если нет волатильности, возвращаем базовый
            if volatility is None:
                return base_stop
            
            # ATR-based stop loss
            # Стоп = цена - (ATR * множитель)
            atr_multiplier = 2.0  # Стандартный множитель
            
            if signal.signal_type == 'long':
                optimal_stop = signal.price - (signal.price * volatility * atr_multiplier)
            else:  # short
                optimal_stop = signal.price + (signal.price * volatility * atr_multiplier)
            
            # Используем более консервативный вариант
            if signal.signal_type == 'long':
                final_stop = min(base_stop, optimal_stop)
            else:
                final_stop = max(base_stop, optimal_stop)
            
            logger.debug(
                f"Stop-loss: базовый=${base_stop:.2f}, "
                f"ATR-based=${optimal_stop:.2f}, "
                f"финальный=${final_stop:.2f}"
            )
            
            return final_stop
            
        except Exception as e:
            logger.error(f"Ошибка расчёта стоп-лосса: {e}")
            return signal.stop_loss
    
    def calculate_position_heat(self) -> float:
        """
        Расчёт "температуры" портфеля
        
        Returns:
            Heat от 0.0 (холодный) до 1.0 (перегрет)
        """
        try:
            metrics = self.portfolio_tracker.calculate_performance()
            
            if not metrics:
                return 0.0
            
            # Факторы нагрева
            factors = []
            
            # 1. Просадка
            drawdown = abs(metrics.get('max_drawdown', 0))
            drawdown_heat = min(drawdown / 0.15, 1.0)  # 15% = максимум
            factors.append(drawdown_heat * 0.4)  # Вес 40%
            
            # 2. Win rate (обратная связь)
            win_rate = metrics.get('win_rate', 0.5)
            win_rate_heat = 1.0 - min(win_rate / 0.7, 1.0)  # 70% = холодно
            factors.append(win_rate_heat * 0.3)  # Вес 30%
            
            # 3. Количество открытых позиций
            try:
                from core.order_executor import OrderExecutor
                executor = OrderExecutor()
                positions = len(executor.positions)
                max_positions = 10  # Максимальное комфортное количество
                positions_heat = min(positions / max_positions, 1.0)
                factors.append(positions_heat * 0.3)  # Вес 30%
            except:
                factors.append(0.5 * 0.3)
            
            # Общая температура
            total_heat = sum(factors)
            
            logger.debug(f"Portfolio heat: {total_heat:.2%}")
            
            return total_heat
            
        except Exception as e:
            logger.error(f"Ошибка расчёта heat: {e}")
            return 0.5
    
    def should_reduce_risk(self) -> bool:
        """
        Нужно ли снизить риск?
        
        Returns:
            True если портфель перегрет
        """
        heat = self.calculate_position_heat()
        
        # Порог для снижения риска
        if heat > 0.7:
            logger.warning(f"🔥 Портфель перегрет: {heat:.2%} > 70%")
            return True
        
        return False
    
    def get_risk_adjustment_factor(self) -> float:
        """
        Получение коэффициента корректировки риска
        
        Returns:
            Множитель от 0.5 до 1.5
        """
        heat = self.calculate_position_heat()
        
        # Обратная зависимость от heat
        if heat > 0.7:
            # Снижаем риск при перегреве
            factor = 0.5 + (1.0 - heat) * 0.5
        elif heat < 0.3:
            # Увеличиваем риск при холодном портфеле
            factor = 1.0 + (0.3 - heat) * 1.5
        else:
            # Нормальный риск
            factor = 1.0
        
        # Ограничение диапазона
        factor = max(0.5, min(factor, 1.5))
        
        logger.debug(f"Risk adjustment factor: {factor:.2f}")
        
        return factor
    
    def calculate_sharpe_ratio(self, returns: list, risk_free_rate: float = 0.02) -> float:
        """
        Расчёт коэффициента Шарпа
        
        Args:
            returns: Список доходностей
            risk_free_rate: Безрисковая ставка (годовая)
            
        Returns:
            Sharpe Ratio
        """
        try:
            if len(returns) < 2:
                return 0.0
            
            returns_array = np.array(returns)
            
            # Средняя доходность
            mean_return = np.mean(returns_array)
            
            # Стандартное отклонение
            std_return = np.std(returns_array)
            
            if std_return == 0:
                return 0.0
            
            # Sharpe Ratio
            sharpe = (mean_return - risk_free_rate / 252) / std_return
            
            # Аннуализация
            sharpe_annualized = sharpe * np.sqrt(252)
            
            return sharpe_annualized
            
        except Exception as e:
            logger.error(f"Ошибка расчёта Sharpe: {e}")
            return 0.0
    
    def calculate_sortino_ratio(self, returns: list, risk_free_rate: float = 0.02) -> float:
        """
        Расчёт коэффициента Сортино (учитывает только downside risk)
        
        Args:
            returns: Список доходностей
            risk_free_rate: Безрисковая ставка
            
        Returns:
            Sortino Ratio
        """
        try:
            if len(returns) < 2:
                return 0.0
            
            returns_array = np.array(returns)
            
            # Средняя доходность
            mean_return = np.mean(returns_array)
            
            # Downside deviation (только отрицательные доходности)
            negative_returns = returns_array[returns_array < 0]
            
            if len(negative_returns) == 0:
                return float('inf')
            
            downside_std = np.std(negative_returns)
            
            if downside_std == 0:
                return 0.0
            
            # Sortino Ratio
            sortino = (mean_return - risk_free_rate / 252) / downside_std
            
            # Аннуализация
            sortino_annualized = sortino * np.sqrt(252)
            
            return sortino_annualized
            
        except Exception as e:
            logger.error(f"Ошибка расчёта Sortino: {e}")
            return 0.0


# Тестирование
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    from core.signal_generator import TradingSignal
    from core.deepseek_analyzer import MarketAnalysis
    from core.portfolio_tracker import PortfolioTracker
    from datetime import datetime
    
    print("🧪 Тестирование AdvancedRiskManager...\n")
    
    # Создание трекера и risk manager
    tracker = PortfolioTracker()
    risk_manager = AdvancedRiskManager(tracker)
    
    # Тестовые данные
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
    
    # Тест Kelly Criterion
    print("1️⃣ Тест Kelly Criterion:")
    
    mock_metrics = {
        'total_trades': 50,
        'win_rate': 0.68,
        'avg_win': 125.0,
        'avg_loss': -50.0
    }
    
    kelly_size = risk_manager.calculate_kelly_position_size(test_signal, mock_metrics)
    print(f"   Kelly размер: {kelly_size:.6f}")
    
    # Тест Portfolio Heat
    print("\n2️⃣ Тест Portfolio Heat:")
    heat = risk_manager.calculate_position_heat()
    print(f"   Heat: {heat:.2%}")
    
    should_reduce = risk_manager.should_reduce_risk()
    print(f"   Снижать риск: {'Да' if should_reduce else 'Нет'}")
    
    # Тест корректировки
    print("\n3️⃣ Тест Risk Adjustment:")
    factor = risk_manager.get_risk_adjustment_factor()
    print(f"   Коэффициент: {factor:.2f}")
    
    # Тест Sharpe/Sortino
    print("\n4️⃣ Тест Sharpe/Sortino:")
    test_returns = [0.02, -0.01, 0.03, 0.01, -0.02, 0.04, 0.02, -0.01]
    
    sharpe = risk_manager.calculate_sharpe_ratio(test_returns)
    print(f"   Sharpe Ratio: {sharpe:.2f}")
    
    sortino = risk_manager.calculate_sortino_ratio(test_returns)
    print(f"   Sortino Ratio: {sortino:.2f}")
    
    print("\n✅ Все тесты завершены!")

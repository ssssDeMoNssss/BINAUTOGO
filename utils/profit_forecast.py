"""
BINAUTOGO - Profit Forecast
Прогноз прибыли на основе стратегии и исторических данных
"""

import logging
from typing import Dict
from config.strategies import STRATEGIES

logger = logging.getLogger('BINAUTOGO.ProfitForecast')


class ProfitForecaster:
    """
    Прогнозирование прибыли для разных стратегий
    
    Основано на:
    - Исторических данных рынка
    - Параметрах стратегии
    - Статистике win rate
    - Volatility рынка
    """
    
    def __init__(self):
        self.market_conditions = {
            'bull': 1.5,      # Бычий рынок: +50% к прибыли
            'neutral': 1.0,   # Нейтральный: базовая прибыль
            'bear': 0.6       # Медвежий: -40% к прибыли
        }
    
    def forecast_monthly_profit(self, deposit: int, 
                                market_condition: str = 'neutral',
                                conservative: bool = True) -> Dict:
        """
        Прогноз месячной прибыли
        
        Args:
            deposit: Размер депозита ($100, $1000, $3000, $6000)
            market_condition: Состояние рынка ('bull', 'neutral', 'bear')
            conservative: Консервативный прогноз или оптимистичный
            
        Returns:
            Детальный прогноз
        """
        if deposit not in STRATEGIES:
            raise ValueError(f"Депозит ${deposit} не поддерживается")
        
        strategy = STRATEGIES[deposit]
        
        # Базовые параметры расчёта
        avg_trades_per_day = self._calculate_trades_per_day(strategy)
        expected_win_rate = self._estimate_win_rate(strategy, conservative)
        avg_profit_per_trade = self._calculate_avg_profit(deposit, strategy)
        
        # Месячные показатели
        trading_days = 30
        total_trades = avg_trades_per_day * trading_days
        winning_trades = total_trades * expected_win_rate
        losing_trades = total_trades * (1 - expected_win_rate)
        
        # Расчёт прибыли/убытка
        avg_win = avg_profit_per_trade
        avg_loss = avg_profit_per_trade * 0.4  # Средний убыток 40% от прибыли
        
        gross_profit = winning_trades * avg_win
        gross_loss = losing_trades * avg_loss
        net_profit = gross_profit - gross_loss
        
        # Корректировка на рыночные условия
        market_multiplier = self.market_conditions.get(market_condition, 1.0)
        net_profit *= market_multiplier
        
        # Расчёт процента доходности
        roi_percent = (net_profit / deposit) * 100
        
        # Консервативная корректировка
        if conservative:
            net_profit *= 0.75  # Минус 25% для консервативности
            roi_percent *= 0.75
        
        return {
            'deposit': deposit,
            'strategy_name': strategy.name,
            'market_condition': market_condition,
            'conservative': conservative,
            
            # Торговая активность
            'avg_trades_per_day': round(avg_trades_per_day, 1),
            'total_trades_month': int(total_trades),
            'winning_trades': int(winning_trades),
            'losing_trades': int(losing_trades),
            'win_rate': expected_win_rate,
            
            # Финансовые показатели
            'avg_profit_per_trade': round(avg_profit_per_trade, 2),
            'avg_loss_per_trade': round(avg_loss, 2),
            'gross_profit': round(gross_profit, 2),
            'gross_loss': round(gross_loss, 2),
            'net_profit': round(net_profit, 2),
            'roi_percent': round(roi_percent, 2),
            
            # Прогнозы
            'min_profit': round(net_profit * 0.5, 2),  # Пессимистичный
            'max_profit': round(net_profit * 1.5, 2),  # Оптимистичный
            'expected_profit': round(net_profit, 2),    # Ожидаемый
        }
    
    def _calculate_trades_per_day(self, strategy) -> float:
        """Расчёт среднего количества сделок в день"""
        # Базовое количество зависит от количества пар
        base_trades = strategy.max_trade_pairs * 0.8  # 80% загрузка
        
        # Корректировка на агрессивность стратегии
        if strategy.use_pump_detector:
            base_trades += strategy.max_pump_pairs * 0.3  # 30% активация пампов
        
        return base_trades
    
    def _estimate_win_rate(self, strategy, conservative: bool) -> float:
        """Оценка win rate на основе стратегии"""
        # Базовый win rate
        base_win_rate = 0.65  # 65%
        
        # Бонусы от параметров
        if strategy.use_trailing_stop:
            base_win_rate += 0.05  # +5%
        
        if strategy.delta_deep:
            base_win_rate += 0.03  # +3%
        
        if strategy.progressive_max_pairs:
            base_win_rate += 0.02  # +2%
        
        # Штраф за агрессивность
        if strategy.quantity_aver_multiplier > 1.3:
            base_win_rate -= 0.02  # -2%
        
        # Консервативная корректировка
        if conservative:
            base_win_rate -= 0.05  # -5%
        
        return min(base_win_rate, 0.75)  # Макс 75%
    
    def _calculate_avg_profit(self, deposit: int, strategy) -> float:
        """Расчёт средней прибыли на сделку"""
        # Базовый размер позиции
        position_size = deposit * (strategy.position_size_percent / 100)
        
        # Целевая прибыль
        target_profit_percent = strategy.sell_up_percent / 100
        
        # Средняя прибыль
        avg_profit = position_size * target_profit_percent
        
        return avg_profit
    
    def generate_forecast_report(self, deposit: int) -> str:
        """Генерация текстового отчёта с прогнозом"""
        # Прогнозы для разных условий
        bull_forecast = self.forecast_monthly_profit(deposit, 'bull', False)
        neutral_forecast = self.forecast_monthly_profit(deposit, 'neutral', True)
        bear_forecast = self.forecast_monthly_profit(deposit, 'bear', True)
        
        report = f"""
╔══════════════════════════════════════════════════════════════╗
║     💰 ПРОГНОЗ ПРИБЫЛИ НА 30 ДНЕЙ - ${deposit}                  
╚══════════════════════════════════════════════════════════════╝

📊 Стратегия: {neutral_forecast['strategy_name']}
💵 Начальный депозит: ${deposit:,}

┌──────────────────────────────────────────────────────────────┐
│ 📈 ТОРГОВАЯ АКТИВНОСТЬ                                       │
└──────────────────────────────────────────────────────────────┘

  Сделок в день: {neutral_forecast['avg_trades_per_day']:.1f}
  Сделок в месяц: {neutral_forecast['total_trades_month']}
  Win Rate: {neutral_forecast['win_rate']*100:.0f}%

┌──────────────────────────────────────────────────────────────┐
│ 💰 ПРОГНОЗ ПРИБЫЛИ                                          │
└──────────────────────────────────────────────────────────────┘

🟢 БЫЧИЙ РЫНОК (оптимистичный):
   Прибыль: ${bull_forecast['expected_profit']:,.2f}
   ROI: {bull_forecast['roi_percent']:+.1f}%
   Итого: ${deposit + bull_forecast['expected_profit']:,.2f}

⚪ НЕЙТРАЛЬНЫЙ РЫНОК (ожидаемый):
   Прибыль: ${neutral_forecast['expected_profit']:,.2f}
   ROI: {neutral_forecast['roi_percent']:+.1f}%
   Итого: ${deposit + neutral_forecast['expected_profit']:,.2f}

🔴 МЕДВЕЖИЙ РЫНОК (пессимистичный):
   Прибыль: ${bear_forecast['expected_profit']:,.2f}
   ROI: {bear_forecast['roi_percent']:+.1f}%
   Итого: ${deposit + bear_forecast['expected_profit']:,.2f}

┌──────────────────────────────────────────────────────────────┐
│ 📊 ДИАПАЗОН ПРОГНОЗА (нейтральный рынок)                    │
└──────────────────────────────────────────────────────────────┘

  Минимум: ${neutral_forecast['min_profit']:,.2f}
  Ожидаемо: ${neutral_forecast['expected_profit']:,.2f}
  Максимум: ${neutral_forecast['max_profit']:,.2f}

┌──────────────────────────────────────────────────────────────┐
│ ⚠️ ВАЖНЫЕ ЗАМЕЧАНИЯ                                          │
└──────────────────────────────────────────────────────────────┘

• Прогноз основан на статистике и не гарантирует результат
• Реальная прибыль зависит от волатильности рынка
• Консервативный подход снижает риски но и прибыль
• Рекомендуется начинать с малых сумм на testnet
• Всегда используйте стоп-лоссы и риск-менеджмент

═══════════════════════════════════════════════════════════════
"""
        return report


def generate_all_forecasts():
    """Генерация прогнозов для всех депозитов"""
    forecaster = ProfitForecaster()
    
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║    💰 BINAUTOGO - ПРОГНОЗ ПРИБЫЛИ НА 30 ДНЕЙ               ║")
    print("╚══════════════════════════════════════════════════════════════╝\n")
    
    for deposit in [100, 1000, 3000, 6000]:
        print(forecaster.generate_forecast_report(deposit))
        print("\n" + "="*64 + "\n")


# Тестирование
if __name__ == "__main__":
    generate_all_forecasts()

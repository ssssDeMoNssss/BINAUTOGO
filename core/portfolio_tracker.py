"""
BINAUTOGO - Portfolio Tracker
Отслеживание портфеля и генерация отчётов
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict
import pandas as pd
import numpy as np
from pathlib import Path

from config.settings import config
from core.order_executor import Order
from core.signal_generator import TradingSignal

logger = logging.getLogger('BINAUTOGO.PortfolioTracker')


class PortfolioTracker:
    """
    Трекер портфеля
    Отслеживание сделок, производительности и генерация отчётов
    """
    
    def __init__(self):
        self.trades_history: List[dict] = []
        self.daily_snapshots: List[dict] = []
        self.performance_metrics: dict = {}
        
        # Создание директории для экспортов
        Path(config.EXPORT_DIR).mkdir(parents=True, exist_ok=True)
        
        logger.info("✅ PortfolioTracker инициализирован")
    
    def log_trade(self, order: Order, signal: TradingSignal):
        """
        Логирование сделки
        
        Args:
            order: Исполненный ордер
            signal: Торговый сигнал
        """
        trade_record = {
            'trade_id': order.id,
            'timestamp': order.timestamp,
            'symbol': order.symbol,
            'side': order.side,
            'signal_type': signal.signal_type,
            'quantity': order.filled_amount,
            'entry_price': order.average_price,
            'stop_loss': signal.stop_loss,
            'take_profit': signal.take_profit,
            'signal_confidence': signal.confidence,
            'reasoning': signal.reasoning[:200],  # Первые 200 символов
            'exit_price': None,
            'exit_timestamp': None,
            'pnl': 0.0,
            'pnl_percent': 0.0,
            'status': 'open',
            'exit_reason': None
        }
        
        self.trades_history.append(trade_record)
        logger.debug(f"📝 Сделка залогирована: {order.id}")
    
    def update_trade_exit(self, trade_id: str, exit_price: float, 
                         pnl: float, exit_reason: str = 'manual'):
        """
        Обновление сделки при закрытии
        
        Args:
            trade_id: ID сделки
            exit_price: Цена выхода
            pnl: Прибыль/убыток
            exit_reason: Причина закрытия
        """
        for trade in self.trades_history:
            if trade['trade_id'] == trade_id:
                trade['exit_price'] = exit_price
                trade['exit_timestamp'] = datetime.now()
                trade['pnl'] = pnl
                trade['pnl_percent'] = (pnl / (trade['entry_price'] * trade['quantity'])) * 100
                trade['status'] = 'closed'
                trade['exit_reason'] = exit_reason
                
                logger.info(
                    f"📊 Сделка закрыта: {trade_id}, "
                    f"P&L: ${pnl:+.2f} ({trade['pnl_percent']:+.2f}%)"
                )
                break
    
    def take_snapshot(self, portfolio_value: float, positions: List[dict]):
        """
        Сохранение снимка портфеля
        
        Args:
            portfolio_value: Общая стоимость портфеля
            positions: Текущие позиции
        """
        snapshot = {
            'timestamp': datetime.now(),
            'portfolio_value': portfolio_value,
            'num_positions': len(positions),
            'total_pnl': sum(trade.get('pnl', 0) for trade in self.trades_history),
            'positions': [
                {
                    'symbol': pos['symbol'],
                    'side': pos['side'],
                    'value': pos['value'],
                    'pnl': pos['unrealized_pnl']
                }
                for pos in positions
            ]
        }
        
        self.daily_snapshots.append(snapshot)
        logger.debug(f"📸 Снимок портфеля: ${portfolio_value:,.2f}")
    
    def calculate_performance(self) -> dict:
        """
        Расчёт метрик производительности
        
        Returns:
            Словарь с метриками
        """
        closed_trades = [t for t in self.trades_history if t['status'] == 'closed']
        
        if not closed_trades:
            logger.debug("Нет закрытых сделок для анализа")
            return {}
        
        # Базовые метрики
        total_trades = len(closed_trades)
        winning_trades = [t for t in closed_trades if t['pnl'] > 0]
        losing_trades = [t for t in closed_trades if t['pnl'] < 0]
        
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        
        # P&L метрики
        total_pnl = sum(t['pnl'] for t in closed_trades)
        avg_win = np.mean([t['pnl'] for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t['pnl'] for t in losing_trades]) if losing_trades else 0
        
        # Profit Factor
        gross_profit = sum(t['pnl'] for t in winning_trades)
        gross_loss = abs(sum(t['pnl'] for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Серии выигрышей/проигрышей
        max_win_streak = self._calculate_max_streak(closed_trades, winning=True)
        max_loss_streak = self._calculate_max_streak(closed_trades, winning=False)
        
        # Временные метрики
        if len(closed_trades) > 1:
            durations = [
                (t['exit_timestamp'] - t['timestamp']).total_seconds() / 3600
                for t in closed_trades
                if t['exit_timestamp']
            ]
            avg_duration = np.mean(durations) if durations else 0
        else:
            avg_duration = 0
        
        # Риск метрики
        if len(self.daily_snapshots) > 1:
            values = [s['portfolio_value'] for s in self.daily_snapshots]
            returns = pd.Series(values).pct_change().dropna()
            
            volatility = returns.std() * np.sqrt(252) if len(returns) > 0 else 0
            sharpe_ratio = (returns.mean() * 252) / volatility if volatility > 0 else 0
            
            # Просадка
            cumulative = (1 + returns).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max
            max_drawdown = drawdown.min()
        else:
            volatility = 0
            sharpe_ratio = 0
            max_drawdown = 0
        
        # Сохранение метрик
        self.performance_metrics = {
            'total_trades': total_trades,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_pnl': total_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'largest_win': max([t['pnl'] for t in winning_trades]) if winning_trades else 0,
            'largest_loss': min([t['pnl'] for t in losing_trades]) if losing_trades else 0,
            'max_win_streak': max_win_streak,
            'max_loss_streak': max_loss_streak,
            'avg_trade_duration_hours': avg_duration,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'updated_at': datetime.now()
        }
        
        return self.performance_metrics
    
    def _calculate_max_streak(self, trades: List[dict], winning: bool = True) -> int:
        """Расчёт максимальной серии выигрышей/проигрышей"""
        if not trades:
            return 0
        
        max_streak = 0
        current_streak = 0
        
        for trade in trades:
            if (winning and trade['pnl'] > 0) or (not winning and trade['pnl'] < 0):
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0
        
        return max_streak
    
    def generate_report(self) -> str:
        """
        Генерация текстового отчёта
        
        Returns:
            Форматированный текстовый отчёт
        """
        metrics = self.calculate_performance()
        
        if not metrics:
            return "📊 **Отчёт о производительности**\n\nНет данных для анализа"
        
        report = f"""
╔══════════════════════════════════════════════════════════════╗
║           📊 ОТЧЁТ О ПРОИЗВОДИТЕЛЬНОСТИ BINAUTOGO            ║
╚══════════════════════════════════════════════════════════════╝

🕒 Сгенерирован: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

┌─────────────────────────────────────────────────────────────┐
│ 📈 ТОРГОВАЯ СТАТИСТИКА                                      │
└─────────────────────────────────────────────────────────────┘

  Всего сделок:          {metrics['total_trades']}
  ✅ Выигрышных:         {metrics['winning_trades']} ({metrics['win_rate']*100:.1f}%)
  ❌ Проигрышных:        {metrics['losing_trades']} ({(1-metrics['win_rate'])*100:.1f}%)
  
  📊 Profit Factor:      {metrics['profit_factor']:.2f}
  💰 Общая прибыль:      ${metrics['total_pnl']:+,.2f}

┌─────────────────────────────────────────────────────────────┐
│ 💹 ПОКАЗАТЕЛИ СДЕЛОК                                        │
└─────────────────────────────────────────────────────────────┘

  Средняя прибыль:       ${metrics['avg_win']:+,.2f}
  Средний убыток:        ${metrics['avg_loss']:+,.2f}
  
  Крупнейший выигрыш:    ${metrics['largest_win']:+,.2f}
  Крупнейший проигрыш:   ${metrics['largest_loss']:+,.2f}

┌─────────────────────────────────────────────────────────────┐
│ ⏱ ВРЕМЕННЫЕ ПОКАЗАТЕЛИ                                      │
└─────────────────────────────────────────────────────────────┘

  Средняя длительность:  {metrics['avg_trade_duration_hours']:.1f} часов
  Макс. серия побед:     {metrics['max_win_streak']}
  Макс. серия неудач:    {metrics['max_loss_streak']}

┌─────────────────────────────────────────────────────────────┐
│ 📉 РИСК-МЕТРИКИ                                             │
└─────────────────────────────────────────────────────────────┘

  Волатильность:         {metrics['volatility']*100:.2f}%
  Sharpe Ratio:          {metrics['sharpe_ratio']:.2f}
  Макс. просадка:        {metrics['max_drawdown']*100:.2f}%

┌─────────────────────────────────────────────────────────────┐
│ 🎯 ТЕКУЩИЕ ПОЗИЦИИ                                          │
└─────────────────────────────────────────────────────────────┘
"""
        
        # Добавление открытых позиций
        open_trades = [t for t in self.trades_history if t['status'] == 'open']
        if open_trades:
            for trade in open_trades:
                report += f"""
  {trade['symbol']} - {trade['side'].upper()}
    Вход: ${trade['entry_price']:,.2f}
    Размер: {trade['quantity']:.6f}
    SL: ${trade['stop_loss']:,.2f} | TP: ${trade['take_profit']:,.2f}
"""
        else:
            report += "\n  Нет открытых позиций\n"
        
        report += "\n" + "═" * 63 + "\n"
        
        return report
    
    def export_data(self, filename: str = None):
        """
        Экспорт данных в JSON
        
        Args:
            filename: Имя файла (опционально)
        """
        if filename is None:
            filename = f"trading_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        filepath = Path(config.EXPORT_DIR) / filename
        
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'config': {
                'trading_pairs': config.TRADING_PAIRS,
                'max_risk': config.MAX_PORTFOLIO_RISK,
                'max_positions': config.MAX_POSITIONS,
            },
            'trades_history': self._serialize_trades(),
            'daily_snapshots': self._serialize_snapshots(),
            'performance_metrics': self._serialize_metrics(),
        }
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"📁 Данные экспортированы: {filepath}")
            
        except Exception as e:
            logger.error(f"Ошибка экспорта данных: {e}")
    
    def _serialize_trades(self) -> List[dict]:
        """Сериализация сделок для JSON"""
        return [
            {
                **trade,
                'timestamp': trade['timestamp'].isoformat() if trade['timestamp'] else None,
                'exit_timestamp': trade['exit_timestamp'].isoformat() if trade.get('exit_timestamp') else None
            }
            for trade in self.trades_history
        ]
    
    def _serialize_snapshots(self) -> List[dict]:
        """Сериализация снимков для JSON"""
        return [
            {
                **snapshot,
                'timestamp': snapshot['timestamp'].isoformat()
            }
            for snapshot in self.daily_snapshots
        ]
    
    def _serialize_metrics(self) -> dict:
        """Сериализация метрик для JSON"""
        if not self.performance_metrics:
            return {}
        
        return {
            **self.performance_metrics,
            'updated_at': self.performance_metrics['updated_at'].isoformat()
        }
    
    def get_trade_history(self, symbol: str = None, limit: int = None) -> List[dict]:
        """
        Получение истории сделок
        
        Args:
            symbol: Фильтр по символу (опционально)
            limit: Лимит количества записей
            
        Returns:
            Список сделок
        """
        trades = self.trades_history
        
        if symbol:
            trades = [t for t in trades if t['symbol'] == symbol]
        
        if limit:
            trades = trades[-limit:]
        
        return trades
    
    def get_daily_pnl(self) -> pd.DataFrame:
        """Получение дневного P&L"""
        if not self.daily_snapshots:
            return pd.DataFrame()
        
        df = pd.DataFrame(self.daily_snapshots)
        df['date'] = pd.to_datetime(df['timestamp']).dt.date
        
        daily_pnl = df.groupby('date').agg({
            'total_pnl': 'last',
            'portfolio_value': 'last',
            'num_positions': 'mean'
        })
        
        return daily_pnl


# Тестирование
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    print("🧪 Тестирование PortfolioTracker...\n")
    
    tracker = PortfolioTracker()
    
    # Симуляция сделок
    from core.order_executor import Order, OrderStatus
    from core.signal_generator import TradingSignal
    from core.deepseek_analyzer import MarketAnalysis
    
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
    
    test_order = Order(
        id='test_001',
        symbol='BTC/USDT',
        side='buy',
        amount=0.1,
        price=43500.0,
        order_type='market',
        status=OrderStatus.FILLED,
        filled_amount=0.1,
        average_price=43500.0,
        timestamp=datetime.now()
    )
    
    # Логирование сделки
    tracker.log_trade(test_order, test_signal)
    
    # Закрытие сделки
    tracker.update_trade_exit('test_001', 44500.0, 100.0, 'take_profit')
    
    # Снимки
    tracker.take_snapshot(10100.0, [])
    tracker.take_snapshot(10200.0, [])
    
    # Генерация отчёта
    print(tracker.generate_report())
    
    # Экспорт
    tracker.export_data('test_export.json')
    
    print("\n✅ Тесты завершены!")

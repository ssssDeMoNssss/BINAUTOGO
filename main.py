"""
BINAUTOGO - Главный файл (ПОЛНАЯ ИНТЕГРААЦИЯ)
Все функции интегрированы!
"""

import sys
import signal
import logging
import asyncio
from datetime import datetime
from typing import Dict, List
import schedule
import time

# Конфигурация
from config.settings import config
from config.strategies import select_strategy, STRATEGIES

# Основные компоненты
from core.market_data import MarketDataManager
from core.deepseek_analyzer import DeepSeekAnalyzer
from core.signal_generator import SignalGenerator
from core.risk_manager import RiskManager
from core.order_executor import OrderExecutor
from core.portfolio_tracker import PortfolioTracker
from core.pump_detector import PumpDetector
from core.coin_selector import CoinSelector

# Утилиты
from utils.logger import setup_logger
from utils.telegram_bot import TelegramNotifier, run_telegram_bot
from utils.ml_predictor import MLPredictor
from utils.sentiment_analyzer import SentimentAnalyzer
from utils.advanced_risk import AdvancedRiskManager

logger = setup_logger('BINAUTOGO')


class BINAUTOGO:
    """
    Главный класс BINAUTOGO
    Полная интеграция всех функций
    """
    
    def __init__(self, selected_strategy=None):
        """Инициализация с выбором стратегии"""
        logger.info("🚀 Инициализация BINAUTOGO...")
        
        # Выбор стратегии
        if selected_strategy:
            self.strategy = selected_strategy
        else:
            self.strategy = select_strategy()
        
        self.is_running = False
        self.cycle_count = 0
        
        # Применение параметров стратегии
        self._apply_strategy_params()
        
        try:
            # ===== ОСНОВНЫЕ КОМПОНЕНТЫ =====
            logger.info("Инициализация основных компонентов...")
            
            self.market_data = MarketDataManager()
            self.analyzer = DeepSeekAnalyzer()
            self.signal_generator = SignalGenerator(self.analyzer)
            self.risk_manager = RiskManager()
            self.order_executor = OrderExecutor()
            self.portfolio_tracker = PortfolioTracker()
            
            # ===== ДЕТЕКТОР ПАМПОВ =====
            if self.strategy.use_pump_detector:
                logger.info("✅ Инициализация детектора пампов...")
                self.pump_detector = PumpDetector(self.market_data, self.strategy)
            else:
                self.pump_detector = None
            
            # ===== АВТОВЫБОР МОНЕТ =====
            logger.info("✅ Инициализация автовыбора монет...")
            self.coin_selector = CoinSelector(self.analyzer, self.market_data)
            
            # ===== MACHINE LEARNING =====
            logger.info("✅ Инициализация ML предиктора...")
            self.ml_predictor = MLPredictor()
            
            # ===== SENTIMENT ANALYSIS =====
            logger.info("✅ Инициализация анализа настроений...")
            self.sentiment_analyzer = SentimentAnalyzer()
            
            # ===== ADVANCED RISK MANAGEMENT =====
            logger.info("✅ Инициализация продвинутого риск-менеджмента...")
            self.advanced_risk = AdvancedRiskManager(self.portfolio_tracker)
            
            # ===== TELEGRAM BOT =====
            if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID:
                logger.info("✅ Инициализация Telegram бота...")
                self.telegram = TelegramNotifier(
                    config.TELEGRAM_BOT_TOKEN,
                    config.TELEGRAM_CHAT_ID,
                    bot_instance=self
                )
                # Запуск Telegram в отдельном потоке
                self.telegram_task = None
            else:
                self.telegram = None
                logger.warning("⚠️ Telegram бот не настроен")
            
            logger.info("✅ Все компоненты инициализированы")
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка инициализации: {e}", exc_info=True)
            raise
        
        # Настройка graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def _apply_strategy_params(self):
        """Применение параметров выбранной стратегии"""
        logger.info(f"🎯 Применение стратегии: {self.strategy.name}")
        
        # Обновление конфига
        config.MAX_POSITION_SIZE_PERCENT = self.strategy.position_size_percent / 100
        config.MAX_POSITIONS = self.strategy.max_trade_pairs
        config.DEFAULT_STOP_LOSS_PERCENT = abs(self.strategy.buy_down_percent / 100)
        config.DEFAULT_TAKE_PROFIT_PERCENT = self.strategy.sell_up_percent / 100
        config.MIN_CONFIDENCE = 0.60 if self.strategy.deposit_size >= 3000 else 0.65
        
        # Интервал анализа - 3 минуты!
        config.ANALYSIS_INTERVAL_SECONDS = 180
        
        logger.info(f"  💰 Депозит: ${self.strategy.deposit_size:,}")
        logger.info(f"  📊 Макс. позиций: {self.strategy.max_trade_pairs}")
        logger.info(f"  📈 Размер позиции: {self.strategy.position_size_percent}%")
        logger.info(f"  ⏱️ Интервал: {config.ANALYSIS_INTERVAL_SECONDS}с (3 мин)")
    
    def signal_handler(self, signum, frame):
        """Обработка сигналов завершения"""
        logger.info("🛑 Получен сигнал завершения...")
        self.is_running = False
        self.shutdown()
        sys.exit(0)
    
    async def initialize_async_components(self):
        """Инициализация асинхронных компонентов"""
        # Запуск Telegram бота
        if self.telegram:
            self.telegram_task = asyncio.create_task(
                run_telegram_bot(self.telegram)
            )
            logger.info("✅ Telegram бот запущен асинхронно")
    
    def validate_setup(self) -> bool:
        """Валидация настроек"""
        logger.info("🔍 Проверка настроек...")
        
        try:
            # DeepSeek
            if not self.analyzer.test_connection():
                logger.error("❌ DeepSeek недоступен")
                return False
            logger.info("✅ DeepSeek подключён")
            
            # Binance
            balance = self.order_executor.get_balance()
            if balance is None:
                logger.error("❌ Binance недоступен")
                return False
            logger.info(f"✅ Binance: Баланс {balance:.2f} USDT")
            
            # Проверка торговых пар
            for symbol in config.TRADING_PAIRS:
                price = self.market_data.get_current_price(symbol)
                if price:
                    logger.info(f"  ✓ {symbol}: ${price:,.2f}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка валидации: {e}")
            return False
    
    def start(self):
        """Запуск бота"""
        logger.info("=" * 70)
        logger.info("🤖 BINAUTOGO - ЗАПУСК")
        logger.info("=" * 70)
        logger.info(f"📊 Стратегия: {self.strategy.name}")
        logger.info(f"💰 Депозит: ${self.strategy.deposit_size:,}")
        logger.info(f"🔧 Режим: {'TESTNET' if config.TESTNET else '⚠️ PRODUCTION'}")
        logger.info(f"⏱️ Интервал: {config.ANALYSIS_INTERVAL_SECONDS}с")
        logger.info(f"🚀 Детектор пампов: {'✅' if self.pump_detector else '❌'}")
        logger.info(f"🤖 ML предиктор: ✅")
        logger.info(f"📱 Telegram: {'✅' if self.telegram else '❌'}")
        logger.info("=" * 70)
        
        # Валидация
        if not self.validate_setup():
            logger.error("❌ Валидация не пройдена!")
            return
        
        # Инициализация асинхронных компонентов
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.initialize_async_components())
        
        self.is_running = True
        
        # Планирование задач
        schedule.every(config.ANALYSIS_INTERVAL_SECONDS).seconds.do(
            self.run_trading_cycle
        )
        schedule.every(1).hours.do(self.update_portfolio_snapshot)
        schedule.every().day.at("09:00").do(self.generate_daily_report)
        
        # Автовыбор монет каждые 6 часов
        schedule.every(6).hours.do(self.update_trading_pairs)
        
        logger.info("✅ Бот запущен! Ctrl+C для остановки")
        logger.info("")
        
        # Первый цикл сразу
        self.run_trading_cycle()
        
        # Основной цикл
        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(1)
            except KeyboardInterrupt:
                logger.info("⚠️ Прерывание пользователем")
                break
            except Exception as e:
                logger.error(f"❌ Ошибка в цикле: {e}")
                time.sleep(5)
        
        self.shutdown()
    
    def run_trading_cycle(self):
        """Цикл торговли с ВСЕМИ функциями"""
        self.cycle_count += 1
        logger.info("")
        logger.info(f"{'=' * 70}")
        logger.info(f"🔄 Цикл #{self.cycle_count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'=' * 70}")
        
        try:
            # Обновление позиций
            self.order_executor.update_positions()
            self.order_executor.check_open_orders()
            
            # ===== ДЕТЕКТОР ПАМПОВ =====
            if self.pump_detector:
                logger.info("🚀 Сканирование пампов...")
                pumps = self.pump_detector.scan_markets(config.TRADING_PAIRS)
                
                for pump in pumps:
                    logger.info(f"💥 ПАМП: {pump.symbol} +{pump.price_change_percent:.2f}%")
                    
                    # Создание сигнала из пампа
                    pump_signal = self.pump_detector.create_pump_signal(pump)
                    
                    # Валидация через ML
                    if self.ml_predictor.is_trained:
                        ml_confidence = self.ml_predictor.predict_trade_success(pump_signal)
                        logger.info(f"  🤖 ML уверенность: {ml_confidence*100:.0f}%")
                        
                        if ml_confidence < 0.5:
                            logger.info(f"  ⚠️ ML отклонил сигнал")
                            continue
                    
                    # Риск-менеджмент
                    market_data = self.market_data.get_market_summary(pump.symbol)
                    validated = self.risk_manager.validate_signal(pump_signal, market_data)
                    
                    # Продвинутый риск (Kelly Criterion)
                    if validated.is_valid:
                        kelly_size = self.advanced_risk.calculate_kelly_position_size(
                            validated,
                            self.portfolio_tracker.calculate_performance()
                        )
                        validated.quantity = kelly_size
                    
                    # Исполнение
                    if validated.is_valid:
                        order = self.order_executor.place_order(validated)
                        if order and self.telegram:
                            asyncio.create_task(
                                self.telegram.notify_trade_opened(order, validated)
                            )
            
            # ===== ОБЫЧНАЯ ТОРГОВЛЯ =====
            for symbol in config.TRADING_PAIRS:
                logger.info(f"📊 Анализ {symbol}...")
                self.analyze_and_trade(symbol)
            
            # Статус портфеля
            self.log_portfolio_status()
            
            logger.info(f"✅ Цикл #{self.cycle_count} завершён")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в цикле: {e}", exc_info=True)
    
    def analyze_and_trade(self, symbol: str):
        """Анализ и торговля с ML и Sentiment"""
        try:
            # Рыночные данные
            market_data = self.market_data.get_market_summary(symbol)
            if not market_data:
                return
            
            current_price = market_data['current_price']
            logger.info(f"  💰 Цена: ${current_price:,.2f}")
            
            # ===== SENTIMENT ANALYSIS =====
            sentiment = self.sentiment_analyzer.analyze_symbol(symbol)
            logger.info(f"  😊 Настроение: {sentiment['score']:.2f}")
            
            # ===== DEEPSEEK АНАЛИЗ =====
            signal = self.signal_generator.generate_signal(market_data)
            
            if not signal:
                logger.info(f"  📭 Нет сигнала")
                return
            
            logger.info(f"  📡 Сигнал: {signal.direction.upper()}")
            logger.info(f"  🎯 Уверенность DeepSeek: {signal.confidence*100:.0f}%")
            
            # ===== ML ПРЕДИКЦИЯ =====
            if self.ml_predictor.is_trained:
                ml_prediction = self.ml_predictor.predict_trade_success(signal)
                signal.confidence = (signal.confidence + ml_prediction) / 2
                logger.info(f"  🤖 ML скорректировал: {signal.confidence*100:.0f}%")
            
            # ===== SENTIMENT КОРРЕКТИРОВКА =====
            if sentiment['score'] < -0.5 and signal.direction == 'buy':
                logger.info(f"  ⚠️ Негативное настроение, снижаем уверенность")
                signal.confidence *= 0.8
            elif sentiment['score'] > 0.5 and signal.direction == 'buy':
                logger.info(f"  ✅ Позитивное настроение, повышаем уверенность")
                signal.confidence *= 1.1
            
            # ===== РИСК-МЕНЕДЖМЕНТ =====
            validated = self.risk_manager.validate_signal(signal, market_data)
            
            if not validated.is_valid:
                logger.info(f"  ⛔ Отклонён риск-менеджером")
                return
            
            # ===== KELLY CRITERION =====
            metrics = self.portfolio_tracker.calculate_performance()
            kelly_size = self.advanced_risk.calculate_kelly_position_size(
                validated, metrics
            )
            validated.quantity = kelly_size
            logger.info(f"  📊 Kelly размер: {kelly_size:.6f}")
            
            # ===== ИСПОЛНЕНИЕ =====
            order = self.order_executor.place_order(validated)
            
            if order:
                self.portfolio_tracker.log_trade(order, validated)
                logger.info(f"  ✅ Сделка: {order.side.upper()} @ ${order.average_price:.2f}")
                
                # Уведомление в Telegram
                if self.telegram:
                    asyncio.create_task(
                        self.telegram.notify_trade_opened(order, validated)
                    )
                
                # Обучение ML модели
                self.ml_predictor.add_training_data(signal, order)
            
        except Exception as e:
            logger.error(f"  ❌ Ошибка анализа {symbol}: {e}")
    
    def update_trading_pairs(self):
        """Автоматическое обновление торговых пар"""
        logger.info("🔄 Обновление списка торговых пар...")
        
        try:
            # Автовыбор лучших монет через DeepSeek
            best_coins = asyncio.run(
                self.coin_selector.select_best_coins(limit=10)
            )
            
            if best_coins:
                config.TRADING_PAIRS = best_coins
                logger.info(f"✅ Обновлены пары: {', '.join(best_coins)}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления пар: {e}")
    
    def log_portfolio_status(self):
        """Статус портфеля"""
        try:
            summary = self.order_executor.get_portfolio_summary()
            
            logger.info("")
            logger.info("💼 Статус портфеля:")
            logger.info(f"  💰 Стоимость: ${summary['total_value']:,.2f}")
            logger.info(f"  📊 P&L: ${summary['total_pnl']:+,.2f}")
            logger.info(f"  📈 Позиций: {summary['total_positions']}")
            
            if summary['positions']:
                logger.info("  📋 Позиции:")
                for pos in summary['positions']:
                    emoji = "🟢" if pos['unrealized_pnl'] > 0 else "🔴"
                    logger.info(
                        f"    {emoji} {pos['symbol']}: {pos['side'].upper()} "
                        f"{pos['size']:.6f} @ ${pos['entry_price']:,.2f} "
                        f"(P&L: ${pos['unrealized_pnl']:+,.2f})"
                    )
        except Exception as e:
            logger.error(f"Ошибка статуса: {e}")
    
    def update_portfolio_snapshot(self):
        """Ежечасный снимок"""
        try:
            summary = self.order_executor.get_portfolio_summary()
            self.portfolio_tracker.take_snapshot(
                summary['total_value'],
                summary['positions']
            )
            logger.info(f"📸 Снимок: ${summary['total_value']:,.2f}")
        except Exception as e:
            logger.error(f"Ошибка снимка: {e}")
    
    def generate_daily_report(self):
        """Ежедневный отчёт"""
        try:
            report = self.portfolio_tracker.generate_report()
            logger.info("=" * 70)
            logger.info("📊 ЕЖЕДНЕВНЫЙ ОТЧЁТ")
            logger.info("=" * 70)
            logger.info(report)
            
            # Отправка в Telegram
            if self.telegram:
                asyncio.create_task(
                    self.telegram.notify_daily_report(report)
                )
            
            # Экспорт данных
            self.portfolio_tracker.export_data()
            
            # Обучение ML модели
            self.ml_predictor.train_on_history(
                self.portfolio_tracker.trades_history
            )
            
        except Exception as e:
            logger.error(f"Ошибка отчёта: {e}")
    
    def get_status(self) -> Dict:
        """Статус для Telegram/Dashboard"""
        summary = self.order_executor.get_portfolio_summary()
        
        return {
            'running': self.is_running,
            'cycle': self.cycle_count,
            'portfolio_value': summary['total_value'],
            'positions': summary['total_positions'],
            'pnl': summary['total_pnl'],
            'strategy': self.strategy.name,
            'timestamp': datetime.now().isoformat()
        }
    
    def shutdown(self):
        """Graceful shutdown"""
        logger.info("")
        logger.info("=" * 70)
        logger.info("🔄 Завершение BINAUTOGO...")
        logger.info("=" * 70)
        
        try:
            # Отмена ордеров
            if config.CANCEL_ORDERS_ON_SHUTDOWN:
                self.order_executor.cancel_all_orders()
            
            # Финальный отчёт
            report = self.portfolio_tracker.generate_report()
            logger.info(report)
            
            # Экспорт
            self.portfolio_tracker.export_data("final_export.json")
            
            # Остановка Telegram
            if self.telegram:
                asyncio.run(self.telegram.shutdown())
            
            logger.info("✅ Завершение успешно")
            
        except Exception as e:
            logger.error(f"❌ Ошибка завершения: {e}")


def main():
    """Точка входа с выбором параметров"""
    print("""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║              🤖 BINAUTOGO Trading Bot 🤖                  ║
║                                                           ║
║     AI-Powered Trading with DeepSeek + ML + Sentiment    ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
    """)
    
    try:
        # Выбор стратегии интерактивно
        strategy = select_strategy()
        
        # Создание и запуск бота
        bot = BINAUTOGO(selected_strategy=strategy)
        bot.start()
        
    except KeyboardInterrupt:
        logger.info("🛑 Остановка пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
    finally:
        logger.info("Завершение программы")


if __name__ == "__main__":
    main()

"""
BINAUTOGO - Файл конфигурации
Все настройки бота в одном месте
"""

import os
from dataclasses import dataclass
from typing import List
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()


@dataclass
class BotConfig:
    """Конфигурация торгового бота"""
    
    # ============================================
    # НАСТРОЙКИ BINANCE
    # ============================================
    BINANCE_API_KEY: str = os.getenv('BINANCE_API_KEY', '')
    BINANCE_API_SECRET: str = os.getenv('BINANCE_API_SECRET', '')
    TESTNET: bool = os.getenv('TESTNET', 'True').lower() == 'true'
    
    # ============================================
    # ТОРГОВЫЕ ПАРЫ
    # ============================================
    TRADING_PAIRS: List[str] = None
    BASE_CURRENCY: str = 'USDT'
    
    def __post_init__(self):
        if self.TRADING_PAIRS is None:
            # По умолчанию торгуем основными парами
            self.TRADING_PAIRS = [
                'BTC/USDT',
                'ETH/USDT',
                'BNB/USDT'
            ]
    
    # ============================================
    # НАСТРОЙКИ DEEPSEEK / OLLAMA
    # ============================================
    OLLAMA_HOST: str = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
    DEEPSEEK_MODEL: str = os.getenv('DEEPSEEK_MODEL', 'deepseek-r1:7b')
    
    # Параметры модели
    MODEL_TEMPERATURE: float = 0.3  # Низкая температура для стабильности
    MODEL_MAX_TOKENS: int = 1000
    MODEL_TIMEOUT: int = 30  # Таймаут запроса в секундах
    
    # ============================================
    # ПАРАМЕТРЫ ТОРГОВЛИ
    # ============================================
    ANALYSIS_INTERVAL_SECONDS: int = 180  # 3 минут между анализами
    
    # Минимальная уверенность для открытия позиции
    MIN_CONFIDENCE: float = 0.65  # 65%
    
    # Минимальное соотношение риск/прибыль
    MIN_RISK_REWARD_RATIO: float = 1.5  # 1:1.5
    
    # ============================================
    # РИСК-МЕНЕДЖМЕНТ
    # ============================================
    # Максимальный риск на одну сделку (% от портфеля)
    MAX_PORTFOLIO_RISK: float = 0.02  # 2%
    
    # Максимальная просадка портфеля
    MAX_DRAWDOWN: float = 0.10  # 10%
    
    # Стоп-лосс по умолчанию
    DEFAULT_STOP_LOSS_PERCENT: float = 0.03  # 3%
    
    # Тейк-профит по умолчанию  
    DEFAULT_TAKE_PROFIT_PERCENT: float = 0.06  # 6%
    
    # Максимальный размер одной позиции
    MAX_POSITION_SIZE_PERCENT: float = 0.20  # 20% портфеля
    
    # Максимальное количество одновременных позиций
    MAX_POSITIONS: int = 5
    
    # Максимальная экспозиция по коррелированным активам
    MAX_CORRELATION_EXPOSURE: float = 0.40  # 40%
    
    # ============================================
    # НАСТРОЙКИ ОРДЕРОВ
    # ============================================
    # Тип ордера по умолчанию
    DEFAULT_ORDER_TYPE: str = 'market'  # 'market' или 'limit'
    
    # Проскальзывание для лимитных ордеров (%)
    LIMIT_ORDER_SLIPPAGE: float = 0.001  # 0.1%
    
    # Отменять ордера при выключении бота
    CANCEL_ORDERS_ON_SHUTDOWN: bool = True
    
    # ============================================
    # ТЕХНИЧЕСКИЕ ИНДИКАТОРЫ
    # ============================================
    # Периоды для расчета индикаторов
    RSI_PERIOD: int = 14
    MACD_FAST: int = 12
    MACD_SLOW: int = 26
    MACD_SIGNAL: int = 9
    BOLLINGER_PERIOD: int = 20
    BOLLINGER_STD: int = 2
    
    # Пороги RSI
    RSI_OVERSOLD: float = 30
    RSI_OVERBOUGHT: float = 70
    
    # ============================================
    # ДАННЫЕ И ТАЙМФРЕЙМЫ
    # ============================================
    # Таймфреймы для анализа
    TIMEFRAME_SHORT: str = '5m'   # Короткий
    TIMEFRAME_MEDIUM: str = '1h'  # Средний
    TIMEFRAME_LONG: str = '1d'    # Длинный
    
    # Количество свечей для анализа
    CANDLES_SHORT: int = 100
    CANDLES_MEDIUM: int = 48
    CANDLES_LONG: int = 30
    
    # ============================================
    # ОПТИМИЗАЦИЯ И КЭШИРОВАНИЕ
    # ============================================
    ENABLE_DATA_CACHING: bool = True
    CACHE_EXPIRY_MINUTES: int = 3
    
    # Динамическая корректировка интервала анализа
    DYNAMIC_INTERVAL: bool = True
    
    # ============================================
    # ЛОГИРОВАНИЕ И МОНИТОРИНГ
    # ============================================
    LOG_LEVEL: str = 'INFO'  # DEBUG, INFO, WARNING, ERROR
    LOG_TO_FILE: bool = True
    LOG_FILE: str = 'logs/binautogo.log'
    
    # Максимальный размер лог-файла (MB)
    LOG_MAX_SIZE_MB: int = 50
    LOG_BACKUP_COUNT: int = 5
    
    # Уведомления
    ENABLE_NOTIFICATIONS: bool = False
    TELEGRAM_BOT_TOKEN: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_CHAT_ID: str = os.getenv('TELEGRAM_CHAT_ID', '')
    
    # ============================================
    # БЭКТЕСТИНГ
    # ============================================
    BACKTEST_COMMISSION: float = 0.001  # 0.1% комиссия
    BACKTEST_SLIPPAGE: float = 0.0005   # 0.05% проскальзывание
    
    # ============================================
    # БЕЗОПАСНОСТЬ
    # ============================================
    # Проверка баланса перед сделкой
    VERIFY_BALANCE: bool = True
    
    # Минимальный баланс для торговли (USDT)
    MIN_BALANCE: float = 100.0
    
    # Защита от паники - максимум сделок в час
    MAX_TRADES_PER_HOUR: int = 10
    
    # Аварийная остановка при достижении просадки
    EMERGENCY_STOP_DRAWDOWN: float = 0.15  # 15%
    
    # ============================================
    # ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ
    # ============================================
    # Режим отладки
    DEBUG_MODE: bool = False
    
    # Сохранять все сигналы (даже отклоненные)
    LOG_ALL_SIGNALS: bool = True
    
    # Экспортировать данные каждый день
    AUTO_EXPORT_DAILY: bool = True
    
    # Директория для экспорта данных
    EXPORT_DIR: str = 'exports'
    
    def validate(self) -> bool:
        """Валидация конфигурации"""
        errors = []
        
        # Проверка API ключей
        if not self.BINANCE_API_KEY:
            errors.append("BINANCE_API_KEY не установлен")
        if not self.BINANCE_API_SECRET:
            errors.append("BINANCE_API_SECRET не установлен")
        
        # Проверка Ollama
        if not self.DEEPSEEK_MODEL:
            errors.append("DEEPSEEK_MODEL не установлен")
        
        # Проверка торговых параметров
        if self.MAX_PORTFOLIO_RISK <= 0 or self.MAX_PORTFOLIO_RISK > 0.1:
            errors.append("MAX_PORTFOLIO_RISK должен быть между 0 и 0.1")
        
        if self.MIN_CONFIDENCE < 0.5 or self.MIN_CONFIDENCE > 1.0:
            errors.append("MIN_CONFIDENCE должен быть между 0.5 и 1.0")
        
        if errors:
            print("❌ Ошибки конфигурации:")
            for error in errors:
                print(f"  • {error}")
            return False
        
        return True
    
    def print_config(self):
        """Вывод текущей конфигурации"""
        print("\n" + "=" * 60)
        print("⚙️  КОНФИГУРАЦИЯ BINAUTOGO")
        print("=" * 60)
        print(f"Режим: {'TESTNET' if self.TESTNET else 'PRODUCTION'}")
        print(f"Торговые пары: {', '.join(self.TRADING_PAIRS)}")
        print(f"DeepSeek модель: {self.DEEPSEEK_MODEL}")
        print(f"Интервал анализа: {self.ANALYSIS_INTERVAL_SECONDS}с")
        print(f"Макс. риск: {self.MAX_PORTFOLIO_RISK * 100:.1f}%")
        print(f"Макс. позиций: {self.MAX_POSITIONS}")
        print(f"Мин. уверенность: {self.MIN_CONFIDENCE * 100:.0f}%")
        print("=" * 60 + "\n")


# Создание глобального экземпляра конфигурации
config = BotConfig()


# Проверка конфигурации при импорте
if __name__ == "__main__":
    config.print_config()
    
    if config.validate():
        print("✅ Конфигурация валидна")
    else:
        print("❌ Конфигурация содержит ошибки")

"""
BINAUTOGO - Logger Utility
Настройка логирования с ротацией и форматированием
"""

import logging
import logging.handlers
import os
from pathlib import Path
from datetime import datetime
import sys


class ColoredFormatter(logging.Formatter):
    """Форматтер с цветным выводом для консоли"""
    
    # ANSI цветовые коды
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    EMOJIS = {
        'DEBUG': '🔍',
        'INFO': 'ℹ️',
        'WARNING': '⚠️',
        'ERROR': '❌',
        'CRITICAL': '🚨'
    }
    
    def format(self, record):
        # Добавляем цвет и эмодзи
        if record.levelname in self.COLORS:
            record.levelname_colored = (
                f"{self.COLORS[record.levelname]}"
                f"{self.EMOJIS.get(record.levelname, '')} "
                f"{record.levelname}"
                f"{self.COLORS['RESET']}"
            )
        else:
            record.levelname_colored = record.levelname
        
        # Форматирование сообщения
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname_colored)s - %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        return formatter.format(record)


def setup_logger(name='BINAUTOGO', log_level='INFO', 
                log_to_file=True, log_file='logs/binautogo.log',
                max_file_size_mb=50, backup_count=5):
    """
    Настройка логгера с поддержкой консоли и файла
    
    Args:
        name: Имя логгера
        log_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Сохранять ли логи в файл
        log_file: Путь к файлу логов
        max_file_size_mb: Максимальный размер файла лога в MB
        backup_count: Количество резервных копий логов
    
    Returns:
        Logger instance
    """
    
    # Создание логгера
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Очистка существующих обработчиков
    logger.handlers.clear()
    
    # ===== КОНСОЛЬНЫЙ ОБРАБОТЧИК =====
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    
    # Проверяем поддержку цветов
    if sys.stdout.isatty():
        console_formatter = ColoredFormatter()
    else:
        # Без цветов для pipe/redirect
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # ===== ФАЙЛОВЫЙ ОБРАБОТЧИК =====
    if log_to_file:
        # Создание директории для логов
        log_dir = Path(log_file).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Ротирующийся файловый обработчик
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_file_size_mb * 1024 * 1024,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        
        # Формат для файла (без цветов)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)-8s - %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    # ===== ОБРАБОТЧИК ОШИБОК =====
    # Отдельный файл для ошибок
    if log_to_file:
        error_log = log_file.replace('.log', '_errors.log')
        error_handler = logging.handlers.RotatingFileHandler(
            error_log,
            maxBytes=10 * 1024 * 1024,  # 10 MB для ошибок
            backupCount=3,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        logger.addHandler(error_handler)
    
    # Предотвращение дублирования логов
    logger.propagate = False
    
    return logger


class TradeLogger:
    """Специализированный логгер для сделок"""
    
    def __init__(self, name='BINAUTOGO.Trades'):
        self.logger = logging.getLogger(name)
        self._setup_trade_logger()
    
    def _setup_trade_logger(self):
        """Настройка логгера сделок"""
        # Создание отдельного файла для сделок
        trades_dir = Path('logs/trades')
        trades_dir.mkdir(parents=True, exist_ok=True)
        
        # Файл с именем по дате
        trade_file = trades_dir / f"trades_{datetime.now().strftime('%Y%m%d')}.log"
        
        handler = logging.FileHandler(trade_file, encoding='utf-8')
        handler.setLevel(logging.INFO)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
    
    def log_order(self, order_type: str, symbol: str, quantity: float, 
                 price: float, **kwargs):
        """Логирование ордера"""
        msg = (
            f"ORDER | {order_type.upper()} | {symbol} | "
            f"Qty: {quantity:.6f} | Price: ${price:.2f}"
        )
        
        if kwargs:
            extra_info = " | ".join(f"{k}: {v}" for k, v in kwargs.items())
            msg += f" | {extra_info}"
        
        self.logger.info(msg)
    
    def log_fill(self, symbol: str, side: str, quantity: float, 
                avg_price: float, pnl: float = None):
        """Логирование исполнения"""
        msg = (
            f"FILL | {side.upper()} | {symbol} | "
            f"Qty: {quantity:.6f} | Avg: ${avg_price:.2f}"
        )
        
        if pnl is not None:
            msg += f" | P&L: ${pnl:+,.2f}"
        
        self.logger.info(msg)
    
    def log_position(self, symbol: str, side: str, size: float, 
                    entry: float, current: float, pnl: float):
        """Логирование позиции"""
        pnl_percent = (pnl / (size * entry)) * 100 if entry > 0 else 0
        
        msg = (
            f"POSITION | {side.upper()} | {symbol} | "
            f"Size: {size:.6f} | Entry: ${entry:.2f} | "
            f"Current: ${current:.2f} | P&L: ${pnl:+,.2f} ({pnl_percent:+.2f}%)"
        )
        
        self.logger.info(msg)


class PerformanceLogger:
    """Логгер производительности"""
    
    def __init__(self, name='BINAUTOGO.Performance'):
        self.logger = logging.getLogger(name)
        self._setup_performance_logger()
    
    def _setup_performance_logger(self):
        """Настройка логгера производительности"""
        perf_dir = Path('logs/performance')
        perf_dir.mkdir(parents=True, exist_ok=True)
        
        perf_file = perf_dir / f"performance_{datetime.now().strftime('%Y%m')}.log"
        
        handler = logging.FileHandler(perf_file, encoding='utf-8')
        formatter = logging.Formatter(
            '%(asctime)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
    
    def log_metrics(self, **metrics):
        """Логирование метрик"""
        metrics_str = " | ".join(f"{k}: {v}" for k, v in metrics.items())
        self.logger.info(f"METRICS | {metrics_str}")
    
    def log_daily_summary(self, date: str, pnl: float, trades: int, 
                         win_rate: float, **kwargs):
        """Дневная сводка"""
        msg = (
            f"DAILY | {date} | P&L: ${pnl:+,.2f} | "
            f"Trades: {trades} | Win Rate: {win_rate:.1%}"
        )
        
        if kwargs:
            extra = " | ".join(f"{k}: {v}" for k, v in kwargs.items())
            msg += f" | {extra}"
        
        self.logger.info(msg)


def get_logger(name='BINAUTOGO'):
    """Получение логгера по имени"""
    return logging.getLogger(name)


def set_log_level(level: str):
    """Изменение уровня логирования"""
    logging.getLogger('BINAUTOGO').setLevel(getattr(logging, level.upper()))


# Примеры использования
if __name__ == "__main__":
    print("🧪 Тестирование логгера...\n")
    
    # Основной логгер
    logger = setup_logger('BINAUTOGO.Test', log_level='DEBUG')
    
    logger.debug("Это debug сообщение")
    logger.info("Это info сообщение")
    logger.warning("Это warning сообщение")
    logger.error("Это error сообщение")
    logger.critical("Это critical сообщение")
    
    print("\n" + "="*60)
    
    # Логгер сделок
    print("\n📊 Тестирование TradeLogger:\n")
    trade_logger = TradeLogger()
    
    trade_logger.log_order('buy', 'BTC/USDT', 0.1, 43500.0, 
                          stop_loss=42500, take_profit=45000)
    
    trade_logger.log_fill('BTC/USDT', 'buy', 0.1, 43500.0)
    
    trade_logger.log_position('BTC/USDT', 'long', 0.1, 43500.0, 44500.0, 100.0)
    
    print("\n" + "="*60)
    
    # Логгер производительности
    print("\n📈 Тестирование PerformanceLogger:\n")
    perf_logger = PerformanceLogger()
    
    perf_logger.log_metrics(
        portfolio_value=10500.0,
        total_pnl=500.0,
        open_positions=3,
        win_rate=0.68
    )
    
    perf_logger.log_daily_summary(
        date='2025-01-08',
        pnl=125.50,
        trades=5,
        win_rate=0.80,
        largest_win=75.0,
        largest_loss=-25.0
    )
    
    print("\n✅ Тестирование завершено!")
    print(f"\nЛоги сохранены в:")
    print(f"  - logs/binautogo.log")
    print(f"  - logs/binautogo_errors.log")
    print(f"  - logs/trades/trades_{datetime.now().strftime('%Y%m%d')}.log")
    print(f"  - logs/performance/performance_{datetime.now().strftime('%Y%m')}.log")

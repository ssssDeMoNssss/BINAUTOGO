"""
BINAUTOGO - Order Executor
Исполнение ордеров на Binance
"""

import ccxt
import logging
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

from config.settings import config
from core.signal_generator import TradingSignal

logger = logging.getLogger('BINAUTOGO.OrderExecutor')


class OrderStatus(Enum):
    """Статусы ордеров"""
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class Order:
    """Ордер"""
    id: str
    symbol: str
    side: str  # 'buy' или 'sell'
    amount: float
    price: float
    order_type: str  # 'market', 'limit'
    status: OrderStatus
    filled_amount: float = 0.0
    average_price: float = 0.0
    timestamp: datetime = None
    exchange_order_id: str = None
    stop_loss_order_id: str = None
    take_profit_order_id: str = None


@dataclass
class Position:
    """Позиция"""
    symbol: str
    side: str  # 'long' или 'short'
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float
    stop_loss: float
    take_profit: float
    timestamp: datetime
    order_id: str = None


class OrderExecutor:
    """
    Исполнитель ордеров
    Взаимодействие с Binance для выполнения сделок
    """
    
    def __init__(self):
        """Инициализация подключения к Binance"""
        try:
            self.exchange = ccxt.binance({
                'apiKey': config.BINANCE_API_KEY,
                'secret': config.BINANCE_API_SECRET,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'spot',
                    'adjustForTimeDifference': True
                }
            })
            
            # Testnet или Production
            if config.TESTNET:
                self.exchange.set_sandbox_mode(True)
                logger.info("📍 OrderExecutor: TESTNET mode")
            else:
                logger.warning("⚠️ OrderExecutor: PRODUCTION mode!")
            
            # Хранилище ордеров и позиций
            self.orders: Dict[str, Order] = {}
            self.positions: Dict[str, Position] = {}
            self.order_counter = 0
            
            logger.info("✅ OrderExecutor инициализирован")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации OrderExecutor: {e}")
            raise
    
    def place_order(self, signal: TradingSignal) -> Optional[Order]:
        """
        Размещение ордера на основе сигнала
        
        Args:
            signal: Торговый сигнал
            
        Returns:
            Order или None при ошибке
        """
        if not signal or not signal.is_valid:
            logger.warning(f"❌ Невалидный сигнал для {signal.symbol if signal else 'unknown'}")
            return None
        
        try:
            logger.info(f"📝 Размещение ордера: {signal.symbol} {signal.direction.upper()}")
            
            # Создание объекта ордера
            order = self._create_order_from_signal(signal)
            
            # Выполнение на бирже
            if config.DEFAULT_ORDER_TYPE == 'market':
                exchange_order = self._execute_market_order(order)
            else:
                exchange_order = self._execute_limit_order(order)
            
            if not exchange_order:
                order.status = OrderStatus.FAILED
                logger.error(f"❌ Не удалось разместить ордер для {signal.symbol}")
                return None
            
            # Обновление данных ордера
            order.exchange_order_id = exchange_order['id']
            order.status = OrderStatus.FILLED if exchange_order['status'] == 'closed' else OrderStatus.OPEN
            
            if order.status == OrderStatus.FILLED:
                order.filled_amount = exchange_order.get('filled', order.amount)
                order.average_price = exchange_order.get('average', exchange_order.get('price', order.price))
                
                # Создание позиции
                self._create_position(order, signal)
                
                # Установка защитных ордеров
                self._set_protective_orders(order, signal)
                
                logger.info(
                    f"✅ Ордер исполнен: {order.side.upper()} "
                    f"{order.filled_amount:.6f} {order.symbol} @ ${order.average_price:.2f}"
                )
            
            # Сохранение ордера
            self.orders[order.id] = order
            
            return order
            
        except ccxt.InsufficientFunds:
            logger.error(f"❌ Недостаточно средств для {signal.symbol}")
            return None
        except ccxt.InvalidOrder as e:
            logger.error(f"❌ Невалидный ордер: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка размещения ордера: {e}")
            return None
    
    def _create_order_from_signal(self, signal: TradingSignal) -> Order:
        """Создание объекта ордера из сигнала"""
        self.order_counter += 1
        
        return Order(
            id=f"order_{self.order_counter:06d}",
            symbol=signal.symbol,
            side=signal.direction,  # 'buy' или 'sell'
            amount=signal.quantity,
            price=signal.price,
            order_type=config.DEFAULT_ORDER_TYPE,
            status=OrderStatus.PENDING,
            timestamp=datetime.now()
        )
    
    def _execute_market_order(self, order: Order) -> Optional[dict]:
        """Исполнение market ордера"""
        try:
            logger.debug(f"📊 Market order: {order.side} {order.amount:.6f} {order.symbol}")
            
            exchange_order = self.exchange.create_market_order(
                symbol=order.symbol,
                side=order.side,
                amount=order.amount
            )
            
            return exchange_order
            
        except Exception as e:
            logger.error(f"Ошибка market ордера: {e}")
            return None
    
    def _execute_limit_order(self, order: Order) -> Optional[dict]:
        """Исполнение limit ордера"""
        try:
            # Добавляем небольшое проскальзывание для лучшего исполнения
            if order.side == 'buy':
                limit_price = order.price * (1 + config.LIMIT_ORDER_SLIPPAGE)
            else:
                limit_price = order.price * (1 - config.LIMIT_ORDER_SLIPPAGE)
            
            logger.debug(
                f"📊 Limit order: {order.side} {order.amount:.6f} "
                f"{order.symbol} @ ${limit_price:.2f}"
            )
            
            exchange_order = self.exchange.create_limit_order(
                symbol=order.symbol,
                side=order.side,
                amount=order.amount,
                price=limit_price
            )
            
            return exchange_order
            
        except Exception as e:
            logger.error(f"Ошибка limit ордера: {e}")
            return None
    
    def _create_position(self, order: Order, signal: TradingSignal):
        """Создание или обновление позиции"""
        symbol = order.symbol
        
        if symbol not in self.positions:
            # Новая позиция
            self.positions[symbol] = Position(
                symbol=symbol,
                side='long' if order.side == 'buy' else 'short',
                size=order.filled_amount,
                entry_price=order.average_price,
                current_price=order.average_price,
                unrealized_pnl=0.0,
                realized_pnl=0.0,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit,
                timestamp=order.timestamp,
                order_id=order.id
            )
            logger.info(f"📊 Открыта позиция: {symbol} {self.positions[symbol].side.upper()}")
        else:
            # Обновление существующей позиции
            position = self.positions[symbol]
            
            if position.side == ('long' if order.side == 'buy' else 'short'):
                # Добавление к позиции
                total_cost = (position.size * position.entry_price) + (order.filled_amount * order.average_price)
                total_size = position.size + order.filled_amount
                position.entry_price = total_cost / total_size
                position.size = total_size
                logger.info(f"📈 Увеличена позиция: {symbol} до {total_size:.6f}")
            else:
                # Закрытие или уменьшение позиции
                if order.filled_amount >= position.size:
                    # Полное закрытие
                    self._close_position(symbol, order.average_price)
                else:
                    # Частичное закрытие
                    position.size -= order.filled_amount
                    logger.info(f"📉 Уменьшена позиция: {symbol} до {position.size:.6f}")
    
    def _set_protective_orders(self, order: Order, signal: TradingSignal):
        """
        Установка защитных ордеров (стоп-лосс и тейк-профит)
        Из вашей стратегии: order_timer, buy_down, max_trade_pairs
        """
        if order.status != OrderStatus.FILLED:
            return
        
        try:
            symbol = order.symbol
            
            # Стоп-лосс ордер
            if signal.stop_loss and signal.stop_loss != order.average_price:
                try:
                    stop_side = 'sell' if order.side == 'buy' else 'buy'
                    
                    # Binance stop-loss market order
                    stop_order = self.exchange.create_order(
                        symbol=symbol,
                        type='STOP_LOSS',
                        side=stop_side,
                        amount=order.filled_amount,
                        params={
                            'stopPrice': signal.stop_loss,
                            'type': 'STOP_LOSS'
                        }
                    )
                    
                    order.stop_loss_order_id = stop_order['id']
                    logger.info(f"🛡️ Стоп-лосс установлен: ${signal.stop_loss:.2f}")
                    
                except Exception as e:
                    logger.error(f"Ошибка установки стоп-лосс: {e}")
            
            # Тейк-профит ордер
            if signal.take_profit and signal.take_profit != order.average_price:
                try:
                    tp_side = 'sell' if order.side == 'buy' else 'buy'
                    
                    # Binance take-profit limit order
                    tp_order = self.exchange.create_order(
                        symbol=symbol,
                        type='TAKE_PROFIT_LIMIT',
                        side=tp_side,
                        amount=order.filled_amount,
                        price=signal.take_profit,
                        params={
                            'stopPrice': signal.take_profit,
                            'type': 'TAKE_PROFIT_LIMIT',
                            'timeInForce': 'GTC'
                        }
                    )
                    
                    order.take_profit_order_id = tp_order['id']
                    logger.info(f"🎯 Тейк-профит установлен: ${signal.take_profit:.2f}")
                    
                except Exception as e:
                    logger.error(f"Ошибка установки тейк-профит: {e}")
                    
        except Exception as e:
            logger.error(f"Ошибка установки защитных ордеров: {e}")
    
    def _close_position(self, symbol: str, exit_price: float):
        """Закрытие позиции и расчёт P&L"""
        if symbol not in self.positions:
            return
        
        position = self.positions[symbol]
        
        # Расчёт P&L
        if position.side == 'long':
            pnl = (exit_price - position.entry_price) * position.size
        else:  # short
            pnl = (position.entry_price - exit_price) * position.size
        
        position.realized_pnl = pnl
        
        logger.info(
            f"🔒 Позиция закрыта: {symbol} "
            f"P&L: ${pnl:+.2f} ({(pnl/(position.entry_price * position.size))*100:+.2f}%)"
        )
        
        # Удаление позиции
        del self.positions[symbol]
    
    def update_positions(self):
        """Обновление текущих цен и P&L всех позиций"""
        for symbol, position in self.positions.items():
            try:
                # Получение текущей цены
                ticker = self.exchange.fetch_ticker(symbol)
                current_price = ticker['last']
                
                position.current_price = current_price
                
                # Расчёт нереализованного P&L
                if position.side == 'long':
                    position.unrealized_pnl = (current_price - position.entry_price) * position.size
                else:
                    position.unrealized_pnl = (position.entry_price - current_price) * position.size
                
            except Exception as e:
                logger.error(f"Ошибка обновления позиции {symbol}: {e}")
    
    def check_open_orders(self):
        """Проверка статуса открытых ордеров"""
        for order_id, order in list(self.orders.items()):
            if order.status in [OrderStatus.OPEN, OrderStatus.PENDING]:
                try:
                    exchange_order = self.exchange.fetch_order(
                        order.exchange_order_id, 
                        order.symbol
                    )
                    
                    if exchange_order['status'] == 'closed':
                        order.status = OrderStatus.FILLED
                        order.filled_amount = exchange_order['filled']
                        order.average_price = exchange_order.get('average', order.price)
                        logger.info(f"✅ Ордер исполнен: {order_id}")
                        
                    elif exchange_order['status'] == 'canceled':
                        order.status = OrderStatus.CANCELLED
                        logger.info(f"❌ Ордер отменён: {order_id}")
                        
                except Exception as e:
                    logger.error(f"Ошибка проверки ордера {order_id}: {e}")
    
    def cancel_order(self, order_id: str) -> bool:
        """Отмена ордера"""
        if order_id not in self.orders:
            logger.warning(f"⚠️ Ордер {order_id} не найден")
            return False
        
        order = self.orders[order_id]
        
        try:
            self.exchange.cancel_order(order.exchange_order_id, order.symbol)
            order.status = OrderStatus.CANCELLED
            logger.info(f"❌ Ордер отменён: {order_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка отмены ордера {order_id}: {e}")
            return False
    
    def cancel_all_orders(self):
        """Отмена всех открытых ордеров"""
        cancelled = 0
        for order_id, order in self.orders.items():
            if order.status == OrderStatus.OPEN:
                if self.cancel_order(order_id):
                    cancelled += 1
        
        logger.info(f"❌ Отменено ордеров: {cancelled}")
        return cancelled
    
    def get_balance(self, currency: str = 'USDT') -> Optional[float]:
        """Получение баланса"""
        try:
            balance = self.exchange.fetch_balance()
            return balance['free'].get(currency, 0.0)
        except Exception as e:
            logger.error(f"Ошибка получения баланса: {e}")
            return None
    
    def get_portfolio_summary(self) -> dict:
        """Получение сводки по портфелю"""
        self.update_positions()
        
        total_value = 0.0
        total_pnl = 0.0
        position_details = []
        
        for symbol, position in self.positions.items():
            position_value = position.size * position.current_price
            total_value += position_value
            total_pnl += position.unrealized_pnl
            
            position_details.append({
                'symbol': symbol,
                'side': position.side,
                'size': position.size,
                'entry_price': position.entry_price,
                'current_price': position.current_price,
                'value': position_value,
                'unrealized_pnl': position.unrealized_pnl,
                'pnl_percent': (position.unrealized_pnl / (position.size * position.entry_price)) * 100
            })
        
        return {
            'total_positions': len(self.positions),
            'total_value': total_value,
            'total_pnl': total_pnl,
            'positions': position_details,
            'timestamp': datetime.now()
        }


# Тестирование
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    print("🧪 Тестирование OrderExecutor...\n")
    
    try:
        executor = OrderExecutor()
        
        # Тест баланса
        print("1️⃣ Тест получения баланса:")
        balance = executor.get_balance('USDT')
        if balance is not None:
            print(f"   ✅ Баланс USDT: {balance:.2f}")
        else:
            print("   ❌ Не удалось получить баланс")
        
        # Тест портфеля
        print("\n2️⃣ Тест портфеля:")
        summary = executor.get_portfolio_summary()
        print(f"   Позиций: {summary['total_positions']}")
        print(f"   Стоимость: ${summary['total_value']:,.2f}")
        print(f"   P&L: ${summary['total_pnl']:+,.2f}")
        
        print("\n✅ Тесты завершены!")
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")

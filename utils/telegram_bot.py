"""
BINAUTOGO - Telegram Bot
Уведомления и управление ботом через Telegram
"""

import logging
import asyncio
from datetime import datetime
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, 
    CommandHandler, 
    CallbackQueryHandler,
    ContextTypes
)

from config.settings import config

logger = logging.getLogger('BINAUTOGO.TelegramBot')


class TelegramNotifier:
    """
    Telegram бот для уведомлений и управления
    
    Функции:
    - Уведомления о сделках
    - PANIC-SALE кнопка
    - Статус бота
    - Отчёты
    """
    
    def __init__(self, token: str, chat_id: str, bot_instance=None):
        """
        Args:
            token: Telegram Bot Token
            chat_id: Telegram Chat ID
            bot_instance: Ссылка на основной бот BINAUTOGO
        """
        self.token = token
        self.chat_id = chat_id
        self.bot_instance = bot_instance
        self.application = None
        self.is_running = False
        
        logger.info("✅ TelegramNotifier инициализирован")
    
    async def initialize(self):
        """Инициализация Telegram бота"""
        try:
            # Создание приложения
            self.application = Application.builder().token(self.token).build()
            
            # Регистрация обработчиков команд
            self.application.add_handler(CommandHandler("start", self.cmd_start))
            self.application.add_handler(CommandHandler("status", self.cmd_status))
            self.application.add_handler(CommandHandler("positions", self.cmd_positions))
            self.application.add_handler(CommandHandler("stats", self.cmd_stats))
            self.application.add_handler(CommandHandler("help", self.cmd_help))
            
            # Обработчик кнопок
            self.application.add_handler(CallbackQueryHandler(self.button_handler))
            
            # Запуск бота
            await self.application.initialize()
            await self.application.start()
            self.is_running = True
            
            logger.info("✅ Telegram бот запущен")
            
            # Отправка приветственного сообщения
            await self.send_message(
                "🤖 *BINAUTOGO запущен!*\n\n"
                "Бот готов к работе.\n"
                "Используйте /help для списка команд."
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации Telegram бота: {e}")
    
    async def shutdown(self):
        """Остановка Telegram бота"""
        if self.application:
            await self.application.stop()
            await self.application.shutdown()
            self.is_running = False
            logger.info("🛑 Telegram бот остановлен")
    
    # ============================================
    # КОМАНДЫ БОТА
    # ============================================
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        keyboard = [
            [
                InlineKeyboardButton("📊 Статус", callback_data="status"),
                InlineKeyboardButton("💼 Позиции", callback_data="positions")
            ],
            [
                InlineKeyboardButton("📈 Статистика", callback_data="stats"),
                InlineKeyboardButton("❓ Помощь", callback_data="help")
            ],
            [
                InlineKeyboardButton("🚨 PANIC-SALE 🚨", callback_data="panic_sale")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🤖 *BINAUTOGO Control Panel*\n\n"
            "Добро пожаловать в панель управления!\n"
            "Выберите действие:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /status - статус бота"""
        if not self.bot_instance:
            await update.message.reply_text("❌ Бот не подключён")
            return
        
        try:
            status = self.bot_instance.get_status()
            
            message = (
                f"🤖 *Статус BINAUTOGO*\n\n"
                f"🔄 Работает: {'✅ Да' if status['running'] else '❌ Нет'}\n"
                f"🔢 Цикл: #{status['cycle']}\n"
                f"💰 Стоимость портфеля: ${status['portfolio_value']:,.2f}\n"
                f"📊 P&L: ${status['pnl']:+,.2f}\n"
                f"📈 Позиций: {status['positions']}\n"
                f"🕐 Обновлено: {datetime.now().strftime('%H:%M:%S')}"
            )
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    async def cmd_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /positions - открытые позиции"""
        if not self.bot_instance:
            await update.message.reply_text("❌ Бот не подключён")
            return
        
        try:
            summary = self.bot_instance.order_executor.get_portfolio_summary()
            
            if not summary['positions']:
                await update.message.reply_text("📭 Нет открытых позиций")
                return
            
            message = "💼 *Открытые позиции:*\n\n"
            
            for pos in summary['positions']:
                pnl_emoji = "🟢" if pos['unrealized_pnl'] > 0 else "🔴"
                message += (
                    f"{pnl_emoji} *{pos['symbol']}*\n"
                    f"   Вход: ${pos['entry_price']:,.2f}\n"
                    f"   Текущая: ${pos['current_price']:,.2f}\n"
                    f"   P&L: ${pos['unrealized_pnl']:+,.2f} ({pos['pnl_percent']:+.2f}%)\n\n"
                )
            
            message += f"💰 *Общий P&L:* ${summary['total_pnl']:+,.2f}"
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /stats - статистика"""
        if not self.bot_instance:
            await update.message.reply_text("❌ Бот не подключён")
            return
        
        try:
            metrics = self.bot_instance.portfolio_tracker.calculate_performance()
            
            if not metrics:
                await update.message.reply_text("📊 Недостаточно данных для статистики")
                return
            
            message = (
                f"📊 *Статистика торговли*\n\n"
                f"🔢 Сделок: {metrics['total_trades']}\n"
                f"✅ Выигрышных: {metrics['winning_trades']} ({metrics['win_rate']*100:.1f}%)\n"
                f"❌ Проигрышных: {metrics['losing_trades']}\n\n"
                f"💰 Общая прибыль: ${metrics['total_pnl']:+,.2f}\n"
                f"📈 Profit Factor: {metrics['profit_factor']:.2f}\n"
                f"📉 Макс. просадка: {metrics['max_drawdown']*100:.2f}%\n"
                f"⚡ Sharpe Ratio: {metrics['sharpe_ratio']:.2f}\n\n"
                f"🏆 Крупнейший выигрыш: ${metrics['largest_win']:,.2f}\n"
                f"📉 Крупнейший проигрыш: ${metrics['largest_loss']:,.2f}"
            )
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /help - помощь"""
        message = (
            "❓ *Доступные команды:*\n\n"
            "/start - Главное меню\n"
            "/status - Статус бота\n"
            "/positions - Открытые позиции\n"
            "/stats - Статистика торговли\n"
            "/help - Эта справка\n\n"
            "🔘 *Кнопки:*\n"
            "• 🚨 PANIC-SALE - Экстренное закрытие всех позиций\n"
            "• 📊 Статус - Текущее состояние бота\n"
            "• 💼 Позиции - Открытые позиции\n"
            "• 📈 Статистика - Производительность\n\n"
            "⚠️ *Внимание:* PANIC-SALE закроет ВСЕ позиции по рыночной цене!"
        )
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    # ============================================
    # ОБРАБОТЧИК КНОПОК
    # ============================================
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатий на кнопки"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "status":
            await self._button_status(query)
        elif query.data == "positions":
            await self._button_positions(query)
        elif query.data == "stats":
            await self._button_stats(query)
        elif query.data == "help":
            await self._button_help(query)
        elif query.data == "panic_sale":
            await self._button_panic_sale(query)
        elif query.data == "panic_confirm":
            await self._execute_panic_sale(query)
        elif query.data == "panic_cancel":
            await query.edit_message_text("✅ PANIC-SALE отменён")
    
    async def _button_status(self, query):
        """Кнопка статуса"""
        if not self.bot_instance:
            await query.edit_message_text("❌ Бот не подключён")
            return
        
        status = self.bot_instance.get_status()
        
        message = (
            f"🤖 *Статус BINAUTOGO*\n\n"
            f"🔄 Работает: {'✅ Да' if status['running'] else '❌ Нет'}\n"
            f"🔢 Цикл: #{status['cycle']}\n"
            f"💰 Портфель: ${status['portfolio_value']:,.2f}\n"
            f"📊 P&L: ${status['pnl']:+,.2f}\n"
            f"📈 Позиций: {status['positions']}\n"
            f"🕐 {datetime.now().strftime('%H:%M:%S')}"
        )
        
        await query.edit_message_text(message, parse_mode='Markdown')
    
    async def _button_positions(self, query):
        """Кнопка позиций"""
        if not self.bot_instance:
            await query.edit_message_text("❌ Бот не подключён")
            return
        
        summary = self.bot_instance.order_executor.get_portfolio_summary()
        
        if not summary['positions']:
            await query.edit_message_text("📭 Нет открытых позиций")
            return
        
        message = "💼 *Открытые позиции:*\n\n"
        
        for pos in summary['positions'][:5]:  # Только 5 первых
            pnl_emoji = "🟢" if pos['unrealized_pnl'] > 0 else "🔴"
            message += (
                f"{pnl_emoji} *{pos['symbol']}* "
                f"${pos['unrealized_pnl']:+,.2f} ({pos['pnl_percent']:+.1f}%)\n"
            )
        
        if len(summary['positions']) > 5:
            message += f"\n_...и ещё {len(summary['positions']) - 5}_"
        
        await query.edit_message_text(message, parse_mode='Markdown')
    
    async def _button_stats(self, query):
        """Кнопка статистики"""
        if not self.bot_instance:
            await query.edit_message_text("❌ Бот не подключён")
            return
        
        metrics = self.bot_instance.portfolio_tracker.calculate_performance()
        
        if not metrics:
            await query.edit_message_text("📊 Недостаточно данных")
            return
        
        message = (
            f"📊 *Статистика*\n\n"
            f"Сделок: {metrics['total_trades']}\n"
            f"Win Rate: {metrics['win_rate']*100:.1f}%\n"
            f"Profit Factor: {metrics['profit_factor']:.2f}\n"
            f"P&L: ${metrics['total_pnl']:+,.2f}"
        )
        
        await query.edit_message_text(message, parse_mode='Markdown')
    
    async def _button_help(self, query):
        """Кнопка помощи"""
        message = (
            "❓ *Команды:*\n"
            "/status, /positions, /stats\n\n"
            "🚨 *PANIC-SALE:*\n"
            "Закроет ВСЕ позиции по рыночной цене!"
        )
        await query.edit_message_text(message, parse_mode='Markdown')
    
    async def _button_panic_sale(self, query):
        """Кнопка PANIC-SALE - запрос подтверждения"""
        keyboard = [
            [
                InlineKeyboardButton("✅ ПОДТВЕРДИТЬ", callback_data="panic_confirm"),
                InlineKeyboardButton("❌ Отмена", callback_data="panic_cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if not self.bot_instance:
            await query.edit_message_text("❌ Бот не подключён")
            return
        
        summary = self.bot_instance.order_executor.get_portfolio_summary()
        
        message = (
            "🚨 *ВНИМАНИЕ! PANIC-SALE*\n\n"
            "⚠️ Это действие:\n"
            "• Закроет ВСЕ открытые позиции\n"
            "• Продаст по рыночной цене\n"
            "• Конвертирует всё в USDT\n\n"
            f"📊 Текущих позиций: {summary['total_positions']}\n"
            f"💰 Общая стоимость: ${summary['total_value']:,.2f}\n"
            f"📈 P&L: ${summary['total_pnl']:+,.2f}\n\n"
            "Вы уверены?"
        )
        
        await query.edit_message_text(
            message, 
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def _execute_panic_sale(self, query):
        """Выполнение PANIC-SALE"""
        await query.edit_message_text("🚨 Выполняется PANIC-SALE...")
        
        if not self.bot_instance:
            await query.message.reply_text("❌ Бот не подключён")
            return
        
        try:
            # Получение всех позиций
            positions = self.bot_instance.order_executor.positions.copy()
            
            if not positions:
                await query.message.reply_text("✅ Нет открытых позиций для закрытия")
                return
            
            closed_count = 0
            total_pnl = 0.0
            errors = []
            
            # Закрытие каждой позиции
            for symbol, position in positions.items():
                try:
                    # Создание ордера на закрытие
                    close_side = 'sell' if position.side == 'long' else 'buy'
                    
                    order = self.bot_instance.order_executor.exchange.create_market_order(
                        symbol=symbol,
                        side=close_side,
                        amount=position.size
                    )
                    
                    # Расчёт P&L
                    if order['status'] == 'closed':
                        exit_price = order.get('average', order.get('price', position.current_price))
                        
                        if position.side == 'long':
                            pnl = (exit_price - position.entry_price) * position.size
                        else:
                            pnl = (position.entry_price - exit_price) * position.size
                        
                        total_pnl += pnl
                        closed_count += 1
                        
                        logger.info(f"🚨 PANIC-SALE: Закрыта {symbol}, P&L: ${pnl:+,.2f}")
                    
                except Exception as e:
                    error_msg = f"{symbol}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(f"Ошибка закрытия {symbol}: {e}")
            
            # Очистка позиций
            self.bot_instance.order_executor.positions.clear()
            
            # Отчёт
            report = (
                f"✅ *PANIC-SALE завершён*\n\n"
                f"🔒 Закрыто позиций: {closed_count}\n"
                f"💰 Общий P&L: ${total_pnl:+,.2f}\n"
            )
            
            if errors:
                report += f"\n⚠️ Ошибки ({len(errors)}):\n"
                for error in errors[:3]:  # Только 3 первые
                    report += f"• {error}\n"
            
            report += f"\n🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            await query.message.reply_text(report, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка PANIC-SALE: {e}")
            await query.message.reply_text(
                f"❌ *Ошибка PANIC-SALE*\n\n{str(e)}",
                parse_mode='Markdown'
            )
    
    # ============================================
    # УВЕДОМЛЕНИЯ
    # ============================================
    
    async def send_message(self, text: str, parse_mode: str = 'Markdown'):
        """Отправка сообщения"""
        if not self.application:
            logger.warning("Telegram приложение не инициализировано")
            return
        
        try:
            await self.application.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode=parse_mode
            )
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}")
    
    async def notify_trade_opened(self, order, signal):
        """Уведомление об открытии позиции"""
        message = (
            f"🟢 *Новая позиция открыта*\n\n"
            f"📊 {order.symbol}\n"
            f"📈 {order.side.upper()}\n"
            f"💰 Цена: ${order.average_price:,.2f}\n"
            f"📦 Количество: {order.filled_amount:.6f}\n"
            f"🎯 TP: ${signal.take_profit:,.2f}\n"
            f"🛡️ SL: ${signal.stop_loss:,.2f}\n"
            f"🤖 Уверенность DeepSeek: {signal.confidence*100:.0f}%\n\n"
            f"💭 _{signal.reasoning[:100]}_..."
        )
        
        await self.send_message(message)
    
    async def notify_trade_closed(self, symbol: str, side: str, entry: float, 
                                  exit: float, pnl: float, pnl_percent: float,
                                  duration: str):
        """Уведомление о закрытии позиции"""
        emoji = "🟢" if pnl > 0 else "🔴"
        
        message = (
            f"{emoji} *Позиция закрыта*\n\n"
            f"📊 {symbol}\n"
            f"📈 {side.upper()}\n"
            f"🔹 Вход: ${entry:,.2f}\n"
            f"🔹 Выход: ${exit:,.2f}\n"
            f"💰 P&L: ${pnl:+,.2f} ({pnl_percent:+.2f}%)\n"
            f"⏱️ Длительность: {duration}\n"
            f"🕐 {datetime.now().strftime('%H:%M:%S')}"
        )
        
        await self.send_message(message)
    
    async def notify_error(self, error_msg: str):
        """Уведомление об ошибке"""
        message = f"❌ *Ошибка*\n\n{error_msg}"
        await self.send_message(message)
    
    async def notify_daily_report(self, report: str):
        """Ежедневный отчёт"""
        await self.send_message(f"📊 *Ежедневный отчёт*\n\n{report}")


# Функция для запуска бота в отдельном потоке
async def run_telegram_bot(notifier: TelegramNotifier):
    """Запуск Telegram бота"""
    await notifier.initialize()
    
    # Держать бота активным
    while notifier.is_running:
        await asyncio.sleep(1)


# Тестирование
if __name__ == "__main__":
    import os
    
    # Загрузка переменных окружения
    from dotenv import load_dotenv
    load_dotenv()
    
    TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
    
    if not TOKEN or not CHAT_ID:
        print("❌ Установите TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID в .env")
        exit(1)
    
    print("🧪 Тестирование Telegram бота...\n")
    
    # Создание и запуск
    notifier = TelegramNotifier(TOKEN, CHAT_ID)
    
    try:
        asyncio.run(run_telegram_bot(notifier))
    except KeyboardInterrupt:
        print("\n🛑 Остановка бота...")
        asyncio.run(notifier.shutdown())

"""
BINAUTOGO - Market Data Manager
Получение и обработка рыночных данных с Binance
"""

import ccxt
import pandas as pd
import numpy as np
import logging
from datetime import datetime
from typing import Dict, Optional, List
import time

from config.settings import config

logger = logging.getLogger('BINAUTOGO.MarketData')


class MarketDataManager:
    """
    Менеджер рыночных данных
    Получение цен, свечей и расчет технических индикаторов
    """
    
    def __init__(self):
        """Инициализация подключения к Binance"""
        try:
            # Инициализация CCXT для Binance
            self.exchange = ccxt.binance({
                'apiKey': config.BINANCE_API_KEY,
                'secret': config.BINANCE_API_SECRET,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'spot',  # spot trading
                    'adjustForTimeDifference': True
                }
            })
            
            # Testnet или Production
            if config.TESTNET:
                self.exchange.set_sandbox_mode(True)
                logger.info("📍 Режим: TESTNET (demo)")
            else:
                logger.warning("⚠️ Режим: PRODUCTION (реальная торговля!)")
            
            # Кэш для данных
            self.cache = {}
            self.cache_timestamps = {}
            
            logger.info("✅ MarketDataManager инициализирован")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации MarketDataManager: {e}")
            raise
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """
        Получение текущей цены
        
        Args:
            symbol: Торговая пара (например, 'BTC/USDT')
            
        Returns:
            Цена или None при ошибке
        """
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            price = ticker['last']
            logger.debug(f"💰 {symbol}: ${price:,.2f}")
            return price
            
        except Exception as e:
            logger.error(f"Ошибка получения цены {symbol}: {e}")
            return None
    
    def get_ohlcv(self, symbol: str, timeframe: str = '5m', limit: int = 100) -> pd.DataFrame:
        """
        Получение OHLCV данных (свечей)
        
        Args:
            symbol: Торговая пара
            timeframe: Таймфрейм ('1m', '5m', '1h', '1d')
            limit: Количество свечей
            
        Returns:
            DataFrame с OHLCV данными
        """
        try:
            # Проверка кэша
            cache_key = f"{symbol}_{timeframe}_{limit}"
            if self._is_cache_valid(cache_key):
                logger.debug(f"📦 Использование кэша для {cache_key}")
                return self.cache[cache_key].copy()
            
            # Получение данных
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            
            # Конвертация в DataFrame
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            
            # Конвертация timestamp
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # Сохранение в кэш
            if config.ENABLE_DATA_CACHING:
                self.cache[cache_key] = df.copy()
                self.cache_timestamps[cache_key] = time.time()
            
            logger.debug(f"📊 Получено {len(df)} свечей для {symbol} ({timeframe})")
            return df
            
        except Exception as e:
            logger.error(f"Ошибка получения OHLCV {symbol}: {e}")
            return pd.DataFrame()
    
    def get_market_summary(self, symbol: str) -> Optional[Dict]:
        """
        Получение полной сводки по рынку
        
        Args:
            symbol: Торговая пара
            
        Returns:
            Словарь с рыночными данными и индикаторами
        """
        try:
            # Получение ticker данных
            ticker = self.exchange.fetch_ticker(symbol)
            
            # Получение OHLCV для разных таймфреймов
            df_5m = self.get_ohlcv(symbol, config.TIMEFRAME_SHORT, config.CANDLES_SHORT)
            df_1h = self.get_ohlcv(symbol, config.TIMEFRAME_MEDIUM, config.CANDLES_MEDIUM)
            df_1d = self.get_ohlcv(symbol, config.TIMEFRAME_LONG, config.CANDLES_LONG)
            
            if df_5m.empty:
                logger.warning(f"⚠️ Нет данных для {symbol}")
                return None
            
            # Расчет индикаторов
            indicators = self.calculate_indicators(df_5m, df_1h, df_1d)
            
            # Формирование сводки
            summary = {
                'symbol': symbol,
                'current_price': ticker['last'],
                'price_change_24h': ticker['percentage'] or 0,
                'volume_24h': ticker['baseVolume'] or 0,
                'high_24h': ticker['high'] or ticker['last'],
                'low_24h': ticker['low'] or ticker['last'],
                'bid': ticker['bid'],
                'ask': ticker['ask'],
                'timestamp': datetime.now(),
                'indicators': indicators,
                'ohlcv_5m': df_5m,
                'ohlcv_1h': df_1h,
                'ohlcv_1d': df_1d
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Ошибка получения сводки {symbol}: {e}")
            return None
    
    def calculate_indicators(self, df_5m: pd.DataFrame, df_1h: pd.DataFrame, 
                           df_1d: pd.DataFrame) -> Dict:
        """
        Расчет технических индикаторов
        
        Args:
            df_5m: DataFrame 5-минутных свечей
            df_1h: DataFrame часовых свечей
            df_1d: DataFrame дневных свечей
            
        Returns:
            Словарь с индикаторами
        """
        indicators = {}
        
        try:
            # RSI для разных таймфреймов
            if not df_5m.empty and len(df_5m) >= config.RSI_PERIOD:
                indicators['rsi_5m'] = self._calculate_rsi(
                    df_5m['close'], 
                    config.RSI_PERIOD
                )
            else:
                indicators['rsi_5m'] = 50.0
            
            if not df_1h.empty and len(df_1h) >= config.RSI_PERIOD:
                indicators['rsi_1h'] = self._calculate_rsi(
                    df_1h['close'], 
                    config.RSI_PERIOD
                )
            else:
                indicators['rsi_1h'] = 50.0
            
            # MACD
            if not df_5m.empty and len(df_5m) >= config.MACD_SLOW + config.MACD_SIGNAL:
                macd_data = self._calculate_macd(
                    df_5m['close'],
                    config.MACD_FAST,
                    config.MACD_SLOW,
                    config.MACD_SIGNAL
                )
                indicators.update(macd_data)
            else:
                indicators.update({
                    'macd': 0.0,
                    'macd_signal': 0.0,
                    'macd_histogram': 0.0
                })
            
            # Bollinger Bands
            if not df_5m.empty and len(df_5m) >= config.BOLLINGER_PERIOD:
                bb_data = self._calculate_bollinger_bands(
                    df_5m['close'],
                    config.BOLLINGER_PERIOD,
                    config.BOLLINGER_STD
                )
                indicators.update(bb_data)
            else:
                current_price = df_5m['close'].iloc[-1] if not df_5m.empty else 0
                indicators.update({
                    'bb_upper': current_price * 1.02,
                    'bb_middle': current_price,
                    'bb_lower': current_price * 0.98,
                    'bb_position': 0.5
                })
            
            # Анализ объема
            if not df_5m.empty and len(df_5m) >= 20:
                volume_sma = df_5m['volume'].rolling(20).mean().iloc[-1]
                current_volume = df_5m['volume'].iloc[-1]
                indicators['volume_sma_20'] = volume_sma
                indicators['volume_ratio'] = current_volume / volume_sma if volume_sma > 0 else 1.0
            else:
                indicators['volume_sma_20'] = 0
                indicators['volume_ratio'] = 1.0
            
            # EMA тренды
            if not df_1h.empty and len(df_1h) >= 26:
                indicators['ema_12_1h'] = df_1h['close'].ewm(span=12).mean().iloc[-1]
                indicators['ema_26_1h'] = df_1h['close'].ewm(span=26).mean().iloc[-1]
            else:
                current_price = df_1h['close'].iloc[-1] if not df_1h.empty else 0
                indicators['ema_12_1h'] = current_price
                indicators['ema_26_1h'] = current_price
            
        except Exception as e:
            logger.error(f"Ошибка расчета индикаторов: {e}")
        
        return indicators
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """Расчет RSI (Relative Strength Index)"""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            return float(rsi.iloc[-1]) if not rsi.empty else 50.0
            
        except Exception as e:
            logger.error(f"Ошибка расчета RSI: {e}")
            return 50.0
    
    def _calculate_macd(self, prices: pd.Series, fast: int = 12, 
                       slow: int = 26, signal: int = 9) -> Dict:
        """Расчет MACD (Moving Average Convergence Divergence)"""
        try:
            ema_fast = prices.ewm(span=fast).mean()
            ema_slow = prices.ewm(span=slow).mean()
            
            macd = ema_fast - ema_slow
            macd_signal = macd.ewm(span=signal).mean()
            macd_histogram = macd - macd_signal
            
            return {
                'macd': float(macd.iloc[-1]) if not macd.empty else 0.0,
                'macd_signal': float(macd_signal.iloc[-1]) if not macd_signal.empty else 0.0,
                'macd_histogram': float(macd_histogram.iloc[-1]) if not macd_histogram.empty else 0.0
            }
            
        except Exception as e:
            logger.error(f"Ошибка расчета MACD: {e}")
            return {'macd': 0.0, 'macd_signal': 0.0, 'macd_histogram': 0.0}
    
    def _calculate_bollinger_bands(self, prices: pd.Series, period: int = 20, 
                                  std_dev: int = 2) -> Dict:
        """Расчет Bollinger Bands"""
        try:
            sma = prices.rolling(window=period).mean()
            std = prices.rolling(window=period).std()
            
            upper_band = sma + (std * std_dev)
            lower_band = sma - (std * std_dev)
            
            current_price = prices.iloc[-1]
            bb_upper = upper_band.iloc[-1]
            bb_lower = lower_band.iloc[-1]
            bb_middle = sma.iloc[-1]
            
            # Позиция цены относительно bands (0 = нижняя, 1 = верхняя)
            bb_position = (current_price - bb_lower) / (bb_upper - bb_lower) if bb_upper != bb_lower else 0.5
            
            return {
                'bb_upper': float(bb_upper) if not pd.isna(bb_upper) else current_price * 1.02,
                'bb_middle': float(bb_middle) if not pd.isna(bb_middle) else current_price,
                'bb_lower': float(bb_lower) if not pd.isna(bb_lower) else current_price * 0.98,
                'bb_position': float(bb_position) if not pd.isna(bb_position) else 0.5
            }
            
        except Exception as e:
            logger.error(f"Ошибка расчета Bollinger Bands: {e}")
            current_price = prices.iloc[-1] if not prices.empty else 0
            return {
                'bb_upper': current_price * 1.02,
                'bb_middle': current_price,
                'bb_lower': current_price * 0.98,
                'bb_position': 0.5
            }
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Проверка валидности кэша"""
        if not config.ENABLE_DATA_CACHING:
            return False
        
        if cache_key not in self.cache:
            return False
        
        # Проверка времени жизни кэша
        cache_age = time.time() - self.cache_timestamps.get(cache_key, 0)
        return cache_age < (config.CACHE_EXPIRY_MINUTES * 60)
    
    def clear_cache(self):
        """Очистка кэша"""
        self.cache.clear()
        self.cache_timestamps.clear()
        logger.info("🗑️ Кэш очищен")
    
    def get_account_balance(self, currency: str = 'USDT') -> Optional[float]:
        """
        Получение баланса аккаунта
        
        Args:
            currency: Валюта (по умолчанию USDT)
            
        Returns:
            Баланс или None
        """
        try:
            balance = self.exchange.fetch_balance()
            free_balance = balance['free'].get(currency, 0)
            logger.debug(f"💰 Баланс {currency}: {free_balance:.2f}")
            return free_balance
            
        except Exception as e:
            logger.error(f"Ошибка получения баланса: {e}")
            return None
    
    def get_all_tickers(self, symbols: List[str] = None) -> Dict[str, float]:
        """
        Получение цен для нескольких символов
        
        Args:
            symbols: Список торговых пар (если None, используется из config)
            
        Returns:
            Словарь {symbol: price}
        """
        if symbols is None:
            symbols = config.TRADING_PAIRS
        
        tickers = {}
        
        try:
            # Получение всех tickers одним запросом (эффективнее)
            all_tickers = self.exchange.fetch_tickers(symbols)
            
            for symbol in symbols:
                if symbol in all_tickers:
                    tickers[symbol] = all_tickers[symbol]['last']
                    
            return tickers
            
        except Exception as e:
            logger.error(f"Ошибка получения tickers: {e}")
            
            # Fallback: получение по одному
            for symbol in symbols:
                price = self.get_current_price(symbol)
                if price:
                    tickers[symbol] = price
            
            return tickers


# Тестирование при прямом запуске
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    print("🔍 Тестирование MarketDataManager...\n")
    
    try:
        # Инициализация
        manager = MarketDataManager()
        
        # Тест 1: Получение текущей цены
        print("1️⃣ Тест получения цены:")
        price = manager.get_current_price('BTC/USDT')
        if price:
            print(f"   ✅ BTC/USDT: ${price:,.2f}")
        else:
            print("   ❌ Не удалось получить цену")
        
        # Тест 2: Получение OHLCV
        print("\n2️⃣ Тест получения OHLCV:")
        df = manager.get_ohlcv('BTC/USDT', '5m', 50)
        if not df.empty:
            print(f"   ✅ Получено {len(df)} свечей")
            print(f"   Последняя свеча:")
            print(f"     Open:  ${df['open'].iloc[-1]:,.2f}")
            print(f"     High:  ${df['high'].iloc[-1]:,.2f}")
            print(f"     Low:   ${df['low'].iloc[-1]:,.2f}")
            print(f"     Close: ${df['close'].iloc[-1]:,.2f}")
        else:
            print("   ❌ Не удалось получить OHLCV")
        
        # Тест 3: Полная сводка
        print("\n3️⃣ Тест полной сводки:")
        summary = manager.get_market_summary('BTC/USDT')
        if summary:
            print(f"   ✅ Сводка получена")
            print(f"   Цена: ${summary['current_price']:,.2f}")
            print(f"   Изменение 24ч: {summary['price_change_24h']:+.2f}%")
            print(f"   Индикаторы:")
            for key, value in summary['indicators'].items():
                if isinstance(value, float):
                    print(f"     {key}: {value:.2f}")
        else:
            print("   ❌ Не удалось получить сводку")
        
        # Тест 4: Баланс
        print("\n4️⃣ Тест получения баланса:")
        balance = manager.get_account_balance('USDT')
        if balance is not None:
            print(f"   ✅ Баланс USDT: {balance:.2f}")
        else:
            print("   ❌ Не удалось получить баланс")
        
        print("\n✅ Все тесты завершены!")
        
    except Exception as e:
        print(f"\n❌ Ошибка тестирования: {e}")

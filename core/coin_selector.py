"""
BINAUTOGO - Coin Selector
Автоматический выбор лучших монет через DeepSeek AI
"""

import logging
import asyncio
from typing import List, Dict
from datetime import datetime, timedelta
import json

logger = logging.getLogger('BINAUTOGO.CoinSelector')


class CoinSelector:
    """
    Автоматический селектор монет
    Использует DeepSeek для выбора наиболее перспективных активов
    """
    
    def __init__(self, deepseek_analyzer, market_data):
        """
        Args:
            deepseek_analyzer: DeepSeek анализатор
            market_data: Менеджер рыночных данных
        """
        self.analyzer = deepseek_analyzer
        self.market_data = market_data
        
        # История выбора
        self.selection_history = []
        
        # Кэш оценок
        self.coin_scores_cache = {}
        self.cache_timeout = 3600  # 1 час
        
        logger.info("✅ CoinSelector инициализирован")
    
    async def select_best_coins(self, limit: int = 10, 
                                min_volume: float = 1000000.0) -> List[str]:
        """
        Выбор лучших монет для торговли
        
        Args:
            limit: Количество монет для выбора
            min_volume: Минимальный суточный объём (USD)
            
        Returns:
            Список символов торговых пар
        """
        logger.info(f"🔍 Поиск {limit} лучших монет для торговли...")
        
        try:
            # Получение всех доступных пар на Binance
            markets = self.market_data.exchange.fetch_markets()
            
            # Фильтрация: только USDT пары, активные, с достаточным объёмом
            usdt_pairs = []
            for market in markets:
                if (market['quote'] == 'USDT' and 
                    market['active'] and 
                    not market['info'].get('isMarginTradingAllowed', False)):
                    usdt_pairs.append(market['symbol'])
            
            logger.info(f"  📊 Найдено {len(usdt_pairs)} USDT пар")
            
            # Предварительная фильтрация по объёму
            logger.info(f"  🔍 Фильтрация по объёму > ${min_volume:,.0f}...")
            
            high_volume_pairs = []
            for symbol in usdt_pairs[:100]:  # Топ 100 по ликвидности
                try:
                    ticker = self.market_data.exchange.fetch_ticker(symbol)
                    volume_usd = ticker.get('quoteVolume', 0)
                    
                    if volume_usd >= min_volume:
                        high_volume_pairs.append({
                            'symbol': symbol,
                            'volume': volume_usd,
                            'price': ticker['last'],
                            'change_24h': ticker.get('percentage', 0)
                        })
                except Exception as e:
                    logger.debug(f"Ошибка получения данных {symbol}: {e}")
                    continue
            
            logger.info(f"  ✅ Отобрано {len(high_volume_pairs)} пар с достаточным объёмом")
            
            # Анализ каждой монеты через DeepSeek
            logger.info(f"  🧠 Анализ через DeepSeek AI...")
            
            coin_scores = []
            
            for i, pair_data in enumerate(high_volume_pairs[:50], 1):  # Топ 50 для анализа
                symbol = pair_data['symbol']
                
                # Проверка кэша
                if symbol in self.coin_scores_cache:
                    cached = self.coin_scores_cache[symbol]
                    if (datetime.now() - cached['timestamp']).seconds < self.cache_timeout:
                        coin_scores.append(cached)
                        logger.debug(f"  [{i}/50] {symbol}: кэш {cached['score']}")
                        continue
                
                # Анализ через DeepSeek
                score = await self._analyze_coin_with_deepseek(pair_data)
                
                result = {
                    'symbol': symbol,
                    'score': score,
                    'volume': pair_data['volume'],
                    'price': pair_data['price'],
                    'change_24h': pair_data['change_24h'],
                    'timestamp': datetime.now()
                }
                
                coin_scores.append(result)
                self.coin_scores_cache[symbol] = result
                
                logger.info(f"  [{i}/50] {symbol}: оценка {score}/100")
                
                # Задержка чтобы не перегружать DeepSeek
                await asyncio.sleep(2)
            
            # Сортировка по оценке
            coin_scores.sort(key=lambda x: x['score'], reverse=True)
            
            # Выбор топа
            selected = [coin['symbol'] for coin in coin_scores[:limit]]
            
            # Сохранение в историю
            self.selection_history.append({
                'timestamp': datetime.now(),
                'selected': selected,
                'scores': coin_scores[:limit]
            })
            
            logger.info(f"✅ Выбрано {len(selected)} монет:")
            for i, symbol in enumerate(selected, 1):
                score_data = next(c for c in coin_scores if c['symbol'] == symbol)
                logger.info(
                    f"   {i}. {symbol} - {score_data['score']}/100 "
                    f"(объём: ${score_data['volume']:,.0f})"
                )
            
            return selected
            
        except Exception as e:
            logger.error(f"❌ Ошибка выбора монет: {e}")
            # Возврат дефолтных пар
            return ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'ADA/USDT']
    
    async def _analyze_coin_with_deepseek(self, pair_data: Dict) -> int:
        """
        Анализ монеты через DeepSeek
        
        Args:
            pair_data: Данные о паре
            
        Returns:
            Оценка от 0 до 100
        """
        try:
            symbol = pair_data['symbol']
            
            # Создание промпта для DeepSeek
            prompt = f"""Ты - эксперт по криптовалютам. Оцени перспективность {symbol} для краткосрочной торговли (1-7 дней).

📊 Данные:
- Цена: ${pair_data['price']:,.4f}
- Суточный объём: ${pair_data['volume']:,.0f}
- Изменение 24ч: {pair_data['change_24h']:+.2f}%

Критерии оценки:
1. Ликвидность и объём торгов (30%)
2. Волатильность и возможность прибыли (25%)
3. Технический анализ и тренд (25%)
4. Рыночные условия и риски (20%)

Ответь ТОЛЬКО одним числом от 0 до 100, где:
- 90-100: Отличная возможность
- 70-89: Хорошая возможность
- 50-69: Умеренная
- 30-49: Слабая
- 0-29: Избегать

Число:"""
            
            # Запрос к DeepSeek
            response = self.analyzer._call_deepseek(prompt)
            
            if not response:
                return 50  # Нейтральная оценка
            
            # Извлечение числа из ответа
            score = self._extract_score(response)
            
            return score
            
        except Exception as e:
            logger.error(f"Ошибка анализа {pair_data['symbol']}: {e}")
            return 50
    
    def _extract_score(self, response: str) -> int:
        """Извлечение оценки из ответа DeepSeek"""
        try:
            # Очистка ответа
            response = response.strip()
            
            # Поиск числа
            import re
            numbers = re.findall(r'\b(\d+)\b', response)
            
            if numbers:
                score = int(numbers[0])
                # Валидация диапазона
                return max(0, min(score, 100))
            
            # Если не нашли число, пробуем найти ключевые слова
            response_lower = response.lower()
            
            if any(word in response_lower for word in ['отлично', 'excellent', 'great']):
                return 85
            elif any(word in response_lower for word in ['хорошо', 'good', 'positive']):
                return 70
            elif any(word in response_lower for word in ['умеренно', 'moderate', 'neutral']):
                return 55
            elif any(word in response_lower for word in ['слабо', 'weak', 'poor']):
                return 40
            elif any(word in response_lower for word in ['избегать', 'avoid', 'negative']):
                return 25
            
            return 50  # Дефолт
            
        except Exception as e:
            logger.error(f"Ошибка извлечения оценки: {e}")
            return 50
    
    def get_selection_history(self, days: int = 7) -> List[Dict]:
        """
        Получение истории выбора монет
        
        Args:
            days: Количество дней
            
        Returns:
            История выборов
        """
        cutoff = datetime.now() - timedelta(days=days)
        
        return [
            entry for entry in self.selection_history
            if entry['timestamp'] > cutoff
        ]
    
    def export_scores(self, filename: str = None):
        """Экспорт оценок в файл"""
        if filename is None:
            filename = f"coin_scores_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        data = {
            'timestamp': datetime.now().isoformat(),
            'scores': [
                {
                    **score,
                    'timestamp': score['timestamp'].isoformat()
                }
                for score in self.coin_scores_cache.values()
            ]
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"📁 Оценки экспортированы: {filename}")


# Тестирование
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    
    from core.deepseek_analyzer import DeepSeekAnalyzer
    from core.market_data import MarketDataManager
    
    print("🧪 Тестирование CoinSelector...\n")
    
    # Инициализация
    analyzer = DeepSeekAnalyzer()
    market_data = MarketDataManager()
    selector = CoinSelector(analyzer, market_data)
    
    # Проверка подключения к DeepSeek
    if not analyzer.test_connection():
        print("❌ DeepSeek не доступен. Убедитесь что Ollama запущен!")
        sys.exit(1)
    
    # Выбор монет
    print("🔍 Начало выбора лучших монет...")
    print("⏱️ Это займёт 2-3 минуты...\n")
    
    selected = asyncio.run(selector.select_best_coins(limit=5, min_volume=5000000))
    
    print(f"\n✅ Тест завершён!")
    print(f"Выбрано монет: {len(selected)}")

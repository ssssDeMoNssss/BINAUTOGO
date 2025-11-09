"""
BINAUTOGO - DeepSeek Analyzer
Интеграция с локальной моделью DeepSeek через Ollama API
"""

import json
import logging
from datetime import datetime
from typing import Dict, Optional
from dataclasses import dataclass
import requests

from config.settings import config

logger = logging.getLogger('BINAUTOGO.DeepSeek')


@dataclass
class MarketAnalysis:
    """Результат анализа рынка от DeepSeek"""
    symbol: str
    direction: str  # 'bullish', 'bearish', 'neutral'
    confidence: float  # 0.0 - 1.0
    entry_price: float
    target_price: float
    stop_loss: float
    position_size: float  # % от портфеля
    reasoning: str
    risk_score: int  # 1-10
    timeframe: str
    timestamp: datetime
    is_valid: bool = True


class DeepSeekAnalyzer:
    """
    Анализатор рынка на основе DeepSeek через Ollama
    """
    
    def __init__(self):
        self.ollama_url = f"{config.OLLAMA_HOST}/api/chat"
        self.model = config.DEEPSEEK_MODEL
        self.temperature = config.MODEL_TEMPERATURE
        self.max_tokens = config.MODEL_MAX_TOKENS
        self.timeout = config.MODEL_TIMEOUT
        
        logger.info(f"Инициализация DeepSeek Analyzer: {self.model}")
    
    def test_connection(self) -> bool:
        """Проверка подключения к Ollama"""
        try:
            # Простой тестовый запрос
            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "user", "content": "Привет! Ты работаешь?"}
                    ],
                    "stream": False
                },
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("✅ Соединение с Ollama установлено")
                return True
            else:
                logger.error(f"❌ Ошибка соединения: {response.status_code}")
                return False
                
        except requests.exceptions.ConnectionError:
            logger.error("❌ Не удается подключиться к Ollama. Убедитесь, что Ollama запущен!")
            logger.error("   Запустите: ollama serve")
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка проверки соединения: {e}")
            return False
    
    def analyze_market(self, market_data: Dict) -> Optional[MarketAnalysis]:
        """
        Анализ рыночных данных с помощью DeepSeek
        
        Args:
            market_data: Словарь с рыночными данными
            
        Returns:
            MarketAnalysis или None при ошибке
        """
        try:
            # Создание промпта для DeepSeek
            prompt = self._create_analysis_prompt(market_data)
            
            # Получение ответа от DeepSeek
            response = self._call_deepseek(prompt)
            
            if not response:
                return self._create_neutral_analysis(market_data)
            
            # Парсинг ответа
            analysis = self._parse_response(response, market_data)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Ошибка анализа рынка: {e}")
            return self._create_neutral_analysis(market_data)
    
    def _create_analysis_prompt(self, market_data: Dict) -> str:
        """Создание промпта для анализа"""
        indicators = market_data.get('indicators', {})
        
        prompt = f"""Ты - эксперт по криптовалютной торговле. Проанализируй следующие рыночные данные и дай торговую рекомендацию.

📊 РЫНОЧНЫЕ ДАННЫЕ для {market_data['symbol']}:

Цена и объем:
- Текущая цена: ${market_data['current_price']:,.2f}
- Изменение 24ч: {market_data.get('price_change_24h', 0):+.2f}%
- Объем 24ч: ${market_data.get('volume_24h', 0):,.0f}
- Макс 24ч: ${market_data.get('high_24h', 0):,.2f}
- Мин 24ч: ${market_data.get('low_24h', 0):,.2f}

Технические индикаторы:
- RSI (5m): {indicators.get('rsi_5m', 50):.1f}
- RSI (1h): {indicators.get('rsi_1h', 50):.1f}
- MACD: {indicators.get('macd', 0):.4f}
- MACD Signal: {indicators.get('macd_signal', 0):.4f}
- MACD Histogram: {indicators.get('macd_histogram', 0):.4f}
- Bollinger Bands позиция: {indicators.get('bb_position', 0.5):.2f}
- Соотношение объема: {indicators.get('volume_ratio', 1.0):.2f}x

Время анализа: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}

ЗАДАНИЕ:
Проанализируй данные и дай торговую рекомендацию. Ответ дай СТРОГО в формате JSON:

{{
  "direction": "bullish" | "bearish" | "neutral",
  "confidence": 0.0-1.0,
  "entry_price": число,
  "target_price": число,
  "stop_loss": число,
  "position_size": 0.0-1.0,
  "risk_score": 1-10,
  "timeframe": "5m" | "1h" | "4h" | "1d",
  "reasoning": "подробное объяснение рекомендации"
}}

ВАЖНО:
- direction: "bullish" (покупка), "bearish" (продажа), "neutral" (не торговать)
- confidence: уверенность от 0 до 1 (например, 0.75 = 75%)
- entry_price: цена входа (близко к текущей)
- target_price: целевая цена (take profit)
- stop_loss: стоп-лосс (защита от убытков)
- position_size: размер позиции от портфеля (0.1 = 10%)
- risk_score: оценка риска от 1 (низкий) до 10 (высокий)
- reasoning: объяснение на русском языке

Отвечай ТОЛЬКО JSON, без дополнительного текста!"""
        
        return prompt
    
    def _call_deepseek(self, prompt: str) -> Optional[str]:
        """Запрос к Ollama DeepSeek API"""
        try:
            system_prompt = """Ты - профессиональный криптотрейдер с глубокими знаниями:
- Технического анализа и графических паттернов
- Психологии рынка и анализа настроений
- Риск-менеджмента и управления позициями
- Макроэкономических факторов

Твой анализ должен быть:
1. Основан на данных и объективен
2. С учетом рисков и четкими уровнями стоп-лосс
3. Конкретным с точными ценами входа/выхода
4. Уверенным но реалистичным
5. Ориентированным на практические торговые решения

Отвечай только в формате JSON, без markdown и дополнительного текста."""

            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    "stream": False,
                    "options": {
                        "temperature": self.temperature,
                        "num_predict": self.max_tokens
                    }
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get('message', {}).get('content', '')
                logger.debug(f"DeepSeek ответ: {content[:200]}...")
                return content
            else:
                logger.error(f"Ошибка API: {response.status_code}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error("Таймаут запроса к DeepSeek")
            return None
        except Exception as e:
            logger.error(f"Ошибка вызова DeepSeek: {e}")
            return None
    
    def _parse_response(self, response: str, market_data: Dict) -> MarketAnalysis:
        """Парсинг ответа DeepSeek в структуру данных"""
        try:
            # Очистка ответа от markdown
            response = response.strip()
            if response.startswith('```json'):
                response = response[7:]
            if response.startswith('```'):
                response = response[3:]
            if response.endswith('```'):
                response = response[:-3]
            response = response.strip()
            
            # Поиск JSON в ответе
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                raise ValueError("JSON не найден в ответе")
            
            json_str = response[start_idx:end_idx]
            data = json.loads(json_str)
            
            # Валидация и создание анализа
            analysis = MarketAnalysis(
                symbol=market_data['symbol'],
                direction=data.get('direction', 'neutral').lower(),
                confidence=float(data.get('confidence', 0.5)),
                entry_price=float(data.get('entry_price', market_data['current_price'])),
                target_price=float(data.get('target_price', market_data['current_price'])),
                stop_loss=float(data.get('stop_loss', market_data['current_price'] * 0.97)),
                position_size=float(data.get('position_size', 0.1)),
                reasoning=data.get('reasoning', 'Нет объяснения'),
                risk_score=int(data.get('risk_score', 5)),
                timeframe=data.get('timeframe', '1h'),
                timestamp=datetime.now()
            )
            
            # Валидация значений
            if analysis.confidence < 0 or analysis.confidence > 1:
                analysis.confidence = 0.5
            
            if analysis.direction not in ['bullish', 'bearish', 'neutral']:
                analysis.direction = 'neutral'
            
            if analysis.risk_score < 1 or analysis.risk_score > 10:
                analysis.risk_score = 5
            
            logger.info(f"✅ Анализ от DeepSeek: {analysis.direction.upper()}, "
                       f"уверенность {analysis.confidence*100:.0f}%")
            
            return analysis
            
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON: {e}")
            logger.debug(f"Ответ: {response[:500]}")
            return self._create_neutral_analysis(market_data)
        except Exception as e:
            logger.error(f"Ошибка обработки ответа: {e}")
            return self._create_neutral_analysis(market_data)
    
    def _create_neutral_analysis(self, market_data: Dict) -> MarketAnalysis:
        """Создание нейтрального анализа при ошибках"""
        return MarketAnalysis(
            symbol=market_data['symbol'],
            direction='neutral',
            confidence=0.1,
            entry_price=market_data['current_price'],
            target_price=market_data['current_price'],
            stop_loss=market_data['current_price'] * 0.97,
            position_size=0.0,
            reasoning='Анализ недоступен - нейтральная позиция',
            risk_score=10,
            timeframe='1h',
            timestamp=datetime.now(),
            is_valid=False
        )
    
    def get_market_sentiment(self, symbols: list) -> Dict:
        """Анализ общего настроения рынка по нескольким активам"""
        sentiments = []
        
        for symbol in symbols:
            # Здесь нужно получить market_data для каждого символа
            # Пока возвращаем заглушку
            pass
        
        return {
            'overall_sentiment': 'neutral',
            'sentiment_strength': 0.5,
            'timestamp': datetime.now()
        }


# Тестирование при прямом запуске
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    analyzer = DeepSeekAnalyzer()
    
    # Тест подключения
    if analyzer.test_connection():
        print("✅ Ollama DeepSeek работает!")
        
        # Тест анализа
        test_data = {
            'symbol': 'BTC/USDT',
            'current_price': 43250.0,
            'price_change_24h': 2.5,
            'volume_24h': 28500000000,
            'high_24h': 44000,
            'low_24h': 42000,
            'indicators': {
                'rsi_5m': 65.5,
                'rsi_1h': 58.2,
                'macd': 125.5,
                'macd_signal': 110.2,
                'macd_histogram': 15.3,
                'bb_position': 0.65,
                'volume_ratio': 1.35
            }
        }
        
        print("\n🔍 Тестовый анализ...")
        analysis = analyzer.analyze_market(test_data)
        
        if analysis:
            print(f"\n📊 Результат анализа:")
            print(f"  Направление: {analysis.direction.upper()}")
            print(f"  Уверенность: {analysis.confidence*100:.1f}%")
            print(f"  Вход: ${analysis.entry_price:,.2f}")
            print(f"  Цель: ${analysis.target_price:,.2f}")
            print(f"  Стоп: ${analysis.stop_loss:,.2f}")
            print(f"  Риск: {analysis.risk_score}/10")
            print(f"  Размер: {analysis.position_size*100:.1f}%")
            print(f"\n  💭 Обоснование:")
            print(f"  {analysis.reasoning}")
    else:
        print("❌ Не удается подключиться к Ollama DeepSeek")
        print("\nУбедитесь что:")
        print("1. Ollama установлен: https://ollama.ai")
        print("2. Ollama запущен: ollama serve")
        print("3. DeepSeek загружен: ollama pull deepseek-r1:7b")

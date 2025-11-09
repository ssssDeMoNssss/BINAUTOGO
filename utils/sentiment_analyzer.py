"""
BINAUTOGO - Sentiment Analyzer
Анализ настроений из Twitter и Reddit
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List
import tweepy
import praw
from textblob import TextBlob
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from collections import defaultdict

logger = logging.getLogger('BINAUTOGO.SentimentAnalyzer')


class SentimentAnalyzer:
    """
    Анализатор настроений из социальных сетей
    
    Источники:
    - Twitter
    - Reddit (r/cryptocurrency, r/CryptoMarkets)
    """
    
    def __init__(self):
        """Инициализация подключений к API"""
        self.vader = SentimentIntensityAnalyzer()
        
        # Twitter API (опционально)
        self.twitter_client = None
        self._init_twitter()
        
        # Reddit API (опционально)
        self.reddit_client = None
        self._init_reddit()
        
        # Кэш настроений
        self.sentiment_cache = {}
        self.cache_timeout = 300  # 5 минут
        
        logger.info("✅ SentimentAnalyzer инициализирован")
    
    def _init_twitter(self):
        """Инициализация Twitter API"""
        try:
            api_key = os.getenv('TWITTER_API_KEY')
            api_secret = os.getenv('TWITTER_API_SECRET')
            access_token = os.getenv('TWITTER_ACCESS_TOKEN')
            access_secret = os.getenv('TWITTER_ACCESS_SECRET')
            
            if not all([api_key, api_secret, access_token, access_secret]):
                logger.warning("⚠️ Twitter API не настроен (опционально)")
                return
            
            # Аутентификация Twitter
            auth = tweepy.OAuthHandler(api_key, api_secret)
            auth.set_access_token(access_token, access_secret)
            
            self.twitter_client = tweepy.API(auth, wait_on_rate_limit=True)
            
            # Проверка подключения
            self.twitter_client.verify_credentials()
            logger.info("✅ Twitter API подключён")
            
        except Exception as e:
            logger.warning(f"⚠️ Не удалось подключить Twitter: {e}")
            self.twitter_client = None
    
    def _init_reddit(self):
        """Инициализация Reddit API"""
        try:
            client_id = os.getenv('REDDIT_CLIENT_ID')
            client_secret = os.getenv('REDDIT_CLIENT_SECRET')
            user_agent = os.getenv('REDDIT_USER_AGENT', 'BINAUTOGO:v1.0')
            username = os.getenv('REDDIT_USERNAME')
            password = os.getenv('REDDIT_PASSWORD')
            
            if not all([client_id, client_secret]):
                logger.warning("⚠️ Reddit API не настроен (опционально)")
                return
            
            # Подключение к Reddit
            self.reddit_client = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent,
                username=username,
                password=password
            )
            
            # Проверка подключения
            self.reddit_client.user.me()
            logger.info("✅ Reddit API подключён")
            
        except Exception as e:
            logger.warning(f"⚠️ Не удалось подключить Reddit: {e}")
            self.reddit_client = None
    
    def analyze_symbol(self, symbol: str) -> Dict:
        """
        Анализ настроений для символа
        
        Args:
            symbol: Торговая пара (например, 'BTC/USDT')
            
        Returns:
            Словарь с результатами анализа
        """
        # Проверка кэша
        if symbol in self.sentiment_cache:
            cached = self.sentiment_cache[symbol]
            if (datetime.now() - cached['timestamp']).seconds < self.cache_timeout:
                logger.debug(f"Использование кэша для {symbol}")
                return cached
        
        # Извлечение токена (BTC из BTC/USDT)
        token = symbol.split('/')[0]
        
        # Сбор данных
        twitter_sentiment = self._analyze_twitter(token)
        reddit_sentiment = self._analyze_reddit(token)
        
        # Объединение результатов
        combined_score = self._combine_sentiments(twitter_sentiment, reddit_sentiment)
        
        result = {
            'symbol': symbol,
            'token': token,
            'score': combined_score,  # -1 до +1
            'twitter': twitter_sentiment,
            'reddit': reddit_sentiment,
            'sentiment': self._classify_sentiment(combined_score),
            'timestamp': datetime.now()
        }
        
        # Сохранение в кэш
        self.sentiment_cache[symbol] = result
        
        logger.info(
            f"😊 Настроение {symbol}: {result['sentiment']} "
            f"({combined_score:+.2f})"
        )
        
        return result
    
    def _analyze_twitter(self, token: str) -> Dict:
        """Анализ Twitter"""
        if not self.twitter_client:
            return {'score': 0.0, 'count': 0, 'available': False}
        
        try:
            # Поиск твитов
            query = f"${token} OR #{token} -filter:retweets"
            tweets = tweepy.Cursor(
                self.twitter_client.search_tweets,
                q=query,
                lang='en',
                tweet_mode='extended',
                count=100
            ).items(100)
            
            sentiments = []
            
            for tweet in tweets:
                text = tweet.full_text
                
                # VADER анализ
                vader_scores = self.vader.polarity_scores(text)
                sentiments.append(vader_scores['compound'])
            
            if sentiments:
                avg_score = sum(sentiments) / len(sentiments)
                return {
                    'score': avg_score,
                    'count': len(sentiments),
                    'available': True
                }
            else:
                return {'score': 0.0, 'count': 0, 'available': True}
            
        except Exception as e:
            logger.error(f"Ошибка анализа Twitter: {e}")
            return {'score': 0.0, 'count': 0, 'available': False}
    
    def _analyze_reddit(self, token: str) -> Dict:
        """Анализ Reddit"""
        if not self.reddit_client:
            return {'score': 0.0, 'count': 0, 'available': False}
        
        try:
            sentiments = []
            
            # Поиск в популярных крипто сабреддитах
            subreddits = ['cryptocurrency', 'CryptoMarkets', 'Bitcoin', 'ethtrader']
            
            for subreddit_name in subreddits:
                try:
                    subreddit = self.reddit_client.subreddit(subreddit_name)
                    
                    # Поиск постов с упоминанием токена
                    for submission in subreddit.search(token, limit=25, time_filter='day'):
                        # Анализ заголовка
                        title_sentiment = self.vader.polarity_scores(submission.title)
                        sentiments.append(title_sentiment['compound'])
                        
                        # Анализ текста поста
                        if submission.selftext:
                            text_sentiment = self.vader.polarity_scores(submission.selftext)
                            sentiments.append(text_sentiment['compound'])
                        
                        # Анализ топ комментариев
                        submission.comments.replace_more(limit=0)
                        for comment in submission.comments[:5]:
                            if hasattr(comment, 'body'):
                                comment_sentiment = self.vader.polarity_scores(comment.body)
                                sentiments.append(comment_sentiment['compound'])
                
                except Exception as e:
                    logger.debug(f"Ошибка сабреддита {subreddit_name}: {e}")
                    continue
            
            if sentiments:
                avg_score = sum(sentiments) / len(sentiments)
                return {
                    'score': avg_score,
                    'count': len(sentiments),
                    'available': True
                }
            else:
                return {'score': 0.0, 'count': 0, 'available': True}
            
        except Exception as e:
            logger.error(f"Ошибка анализа Reddit: {e}")
            return {'score': 0.0, 'count': 0, 'available': False}
    
    def _combine_sentiments(self, twitter: Dict, reddit: Dict) -> float:
        """
        Объединение результатов из разных источников
        
        Returns:
            Общий score от -1 до +1
        """
        scores = []
        weights = []
        
        # Twitter (вес 40%)
        if twitter.get('available') and twitter['count'] > 0:
            scores.append(twitter['score'])
            weights.append(0.4)
        
        # Reddit (вес 60% - более качественные обсуждения)
        if reddit.get('available') and reddit['count'] > 0:
            scores.append(reddit['score'])
            weights.append(0.6)
        
        # Если нет данных
        if not scores:
            return 0.0
        
        # Взвешенное среднее
        total_weight = sum(weights)
        weighted_score = sum(s * w for s, w in zip(scores, weights)) / total_weight
        
        return weighted_score
    
    def _classify_sentiment(self, score: float) -> str:
        """Классификация настроения"""
        if score >= 0.5:
            return 'Very Positive'
        elif score >= 0.1:
            return 'Positive'
        elif score >= -0.1:
            return 'Neutral'
        elif score >= -0.5:
            return 'Negative'
        else:
            return 'Very Negative'
    
    def get_trending_tokens(self, limit: int = 10) -> List[Dict]:
        """
        Получение трендовых токенов из социальных сетей
        
        Args:
            limit: Количество токенов
            
        Returns:
            Список словарей с информацией о токенах
        """
        trending = defaultdict(lambda: {'mentions': 0, 'sentiment': 0.0})
        
        try:
            # Анализ Reddit
            if self.reddit_client:
                subreddit = self.reddit_client.subreddit('cryptocurrency')
                
                for submission in subreddit.hot(limit=100):
                    # Простое извлечение токенов из заголовка
                    words = submission.title.upper().split()
                    
                    for word in words:
                        if word.startswith('$') or len(word) <= 5:
                            token = word.replace('$', '')
                            
                            sentiment = self.vader.polarity_scores(submission.title)
                            
                            trending[token]['mentions'] += 1
                            trending[token]['sentiment'] += sentiment['compound']
            
            # Сортировка по количеству упоминаний
            sorted_tokens = sorted(
                trending.items(),
                key=lambda x: x[1]['mentions'],
                reverse=True
            )[:limit]
            
            result = []
            for token, data in sorted_tokens:
                result.append({
                    'token': token,
                    'mentions': data['mentions'],
                    'avg_sentiment': data['sentiment'] / data['mentions'] if data['mentions'] > 0 else 0
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка получения трендов: {e}")
            return []
    
    def clear_cache(self):
        """Очистка кэша"""
        self.sentiment_cache.clear()
        logger.info("🗑️ Кэш настроений очищен")


# Тестирование
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    print("🧪 Тестирование SentimentAnalyzer...\n")
    
    analyzer = SentimentAnalyzer()
    
    # Тест анализа
    test_symbols = ['BTC/USDT', 'ETH/USDT']
    
    for symbol in test_symbols:
        print(f"\n📊 Анализ {symbol}:")
        result = analyzer.analyze_symbol(symbol)
        
        print(f"  Общий score: {result['score']:+.2f}")
        print(f"  Настроение: {result['sentiment']}")
        
        if result['twitter']['available']:
            print(f"  Twitter: {result['twitter']['score']:+.2f} ({result['twitter']['count']} твитов)")
        
        if result['reddit']['available']:
            print(f"  Reddit: {result['reddit']['score']:+.2f} ({result['reddit']['count']} постов)")
    
    # Тест трендов
    print("\n\n🔥 Трендовые токены:")
    trending = analyzer.get_trending_tokens(5)
    
    for i, token_data in enumerate(trending, 1):
        print(
            f"{i}. {token_data['token']}: "
            f"{token_data['mentions']} упоминаний, "
            f"настроение {token_data['avg_sentiment']:+.2f}"
        )
    
    print("\n✅ Тест завершён!")
    print("\n💡 Для работы Twitter/Reddit настройте переменные окружения:")
    print("   TWITTER_API_KEY, TWITTER_API_SECRET")
    print("   TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET")
    print("   REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET")
    print("   REDDIT_USERNAME, REDDIT_PASSWORD")

"""
BINAUTOGO - Multiple Trading Strategies
Четыре стратегии для разных размеров депозита
"""

from dataclasses import dataclass
from typing import Dict


@dataclass
class TradingStrategy:
    """Базовый класс торговой стратегии"""
    
    # Название стратегии
    name: str
    deposit_size: int
    
    # ===== УПРАВЛЕНИЕ КАПИТАЛОМ =====
    min_bnb: float
    min_balance_percent: float
    position_size_percent: float
    
    # ===== УСЛОВИЯ ОТКРЫТИЯ =====
    min_order_multiplier: float
    min_price_usd: float
    min_daily_percent: float
    daily_percent: float
    auto_daily_percent: bool
    
    # ===== ОБЪЁМЫ И ЛИМИТЫ =====
    min_value_usd: float
    sell_up_percent: float
    max_trade_pairs: int
    
    # ===== УСРЕДНЕНИЕ =====
    buy_down_percent: float
    quantity_aver_multiplier: float
    average_percent: float
    max_aver: int
    step_aver_percent: float
    
    # ===== ТРЕЙЛИНГ-СТОП =====
    use_trailing_stop: bool
    trailing_percent: float
    trailing_part_percent: float
    trailing_value_usd: float
    
    # ===== АВТОМАТИЗАЦИЯ =====
    auto_trade_pairs: bool
    progressive_max_pairs: bool
    delta_deep: bool
    individual_depth: bool
    
    # ===== ДЕТЕКТОР ПАМПОВ =====
    use_pump_detector: bool
    pump_order_multiplier: float
    pump_up_percent: float
    max_pump_pairs: int
    trailing_pump: bool
    
    # ===== ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ =====
    delisting_sale: bool
    new_listing: bool
    user_order: bool
    reinvest_position: bool
    double_asset: bool
    
    def to_dict(self) -> Dict:
        """Конвертация в словарь"""
        return {
            'name': self.name,
            'deposit': self.deposit_size,
            'min_bnb': self.min_bnb,
            'min_balance': self.min_balance_percent,
            'position_size': self.position_size_percent,
            'min_order': self.min_order_multiplier,
            'min_price': self.min_price_usd,
            'min_daily_percent': self.min_daily_percent,
            'daily_percent': self.daily_percent,
            'min_value': self.min_value_usd,
            'sell_up': self.sell_up_percent,
            'max_trade_pairs': self.max_trade_pairs,
            'buy_down': self.buy_down_percent,
            'quantity_aver': self.quantity_aver_multiplier,
            'average_percent': self.average_percent,
            'max_aver': self.max_aver,
            'step_aver': self.step_aver_percent,
            'trailing_stop': self.use_trailing_stop,
            'trailing_percent': self.trailing_percent,
            'trailing_part': self.trailing_part_percent,
            'pump_detector': self.use_pump_detector,
        }


# ============================================
# СТРАТЕГИЯ 1: Депозит $100
# ============================================
STRATEGY_100 = TradingStrategy(
    name="Консервативная стратегия для $100",
    deposit_size=100,
    
    # Капитал
    min_bnb=0.04,
    min_balance_percent=30.0,  # 30% свободного баланса
    position_size_percent=18.0,  # 18% макс на позицию
    
    # Условия входа
    min_order_multiplier=1.5,
    min_price_usd=0.02,  # Снижено с 0.05 для большего выбора
    min_daily_percent=-7.0,  # Покупать при падении > -7%
    daily_percent=5.0,  # Целевая прибыль 5%
    auto_daily_percent=True,
    
    # Объёмы
    min_value_usd=20000.0,  # Мин суточный объём
    sell_up_percent=5.0,  # 5% прибыль
    max_trade_pairs=4,  # Макс 4 позиции
    
    # Усреднение
    buy_down_percent=4.0,  # Усреднять при -4%
    quantity_aver_multiplier=1.2,  # x1.2 размер усреднения
    average_percent=8.0,  # 8% от рыночной цены
    max_aver=4,  # Макс 4 усреднения
    step_aver_percent=1.35,  # Шаг 1.35%
    
    # Трейлинг
    use_trailing_stop=True,
    trailing_percent=1.0,  # 1% от максимума
    trailing_part_percent=5.0,  # 5% частичная продажа
    trailing_value_usd=50.0,  # Мин $50 для активации
    
    # Автоматизация
    auto_trade_pairs=True,
    progressive_max_pairs=True,
    delta_deep=True,
    individual_depth=True,
    
    # Детектор пампов
    use_pump_detector=True,
    pump_order_multiplier=2.5,
    pump_up_percent=0.3,
    max_pump_pairs=5,
    trailing_pump=False,
    
    # Дополнительно
    delisting_sale=True,
    new_listing=False,
    user_order=True,
    reinvest_position=False,
    double_asset=False
)


# ============================================
# СТРАТЕГИЯ 2: Депозит $1000
# ============================================
STRATEGY_1000 = TradingStrategy(
    name="Сбалансированная стратегия для $1000",
    deposit_size=1000,
    
    # Капитал
    min_bnb=0.04,
    min_balance_percent=30.0,
    position_size_percent=20.0,  # Увеличено до 20%
    
    # Условия входа
    min_order_multiplier=1.5,
    min_price_usd=0.02,  # Снижено для большего выбора
    min_daily_percent=-5.0,  # Более агрессивно: -5%
    daily_percent=7.0,  # Целевая прибыль 7%
    auto_daily_percent=True,
    
    # Объёмы
    min_value_usd=10000.0,  # Снижено до 10k
    sell_up_percent=5.0,
    max_trade_pairs=5,  # Увеличено до 5 позиций
    
    # Усреднение
    buy_down_percent=4.0,
    quantity_aver_multiplier=1.3,  # Более агрессивно: x1.3
    average_percent=8.0,
    max_aver=4,
    step_aver_percent=1.35,
    
    # Трейлинг
    use_trailing_stop=True,
    trailing_percent=1.0,
    trailing_part_percent=5.0,
    trailing_value_usd=50.0,
    
    # Автоматизация
    auto_trade_pairs=True,
    progressive_max_pairs=True,
    delta_deep=True,
    individual_depth=True,
    
    # Детектор пампов
    use_pump_detector=True,
    pump_order_multiplier=2.5,
    pump_up_percent=0.3,
    max_pump_pairs=8,  # Увеличено до 8
    trailing_pump=False,
    
    # Дополнительно
    delisting_sale=True,
    new_listing=False,
    user_order=True,
    reinvest_position=False,
    double_asset=False
)


# ============================================
# СТРАТЕГИЯ 3: Депозит $3000
# ============================================
STRATEGY_3000 = TradingStrategy(
    name="Агрессивная стратегия для $3000",
    deposit_size=3000,
    
    # Капитал
    min_bnb=0.04,
    min_balance_percent=30.0,
    position_size_percent=20.0,
    
    # Условия входа
    min_order_multiplier=1.5,
    min_price_usd=0.02,
    min_daily_percent=-5.0,
    daily_percent=7.0,
    auto_daily_percent=True,
    
    # Объёмы
    min_value_usd=20000.0,  # Снижено до 20k
    sell_up_percent=5.0,
    max_trade_pairs=6,  # 6 позиций
    
    # Усреднение
    buy_down_percent=4.0,
    quantity_aver_multiplier=1.4,  # x1.4
    average_percent=8.0,
    max_aver=5,  # Увеличено до 5
    step_aver_percent=1.35,
    
    # Трейлинг
    use_trailing_stop=True,
    trailing_percent=1.0,
    trailing_part_percent=5.0,
    trailing_value_usd=50.0,
    
    # Автоматизация
    auto_trade_pairs=True,
    progressive_max_pairs=True,
    delta_deep=True,
    individual_depth=True,
    
    # Детектор пампов
    use_pump_detector=True,
    pump_order_multiplier=3.0,  # Увеличено
    pump_up_percent=0.3,
    max_pump_pairs=10,
    trailing_pump=True,  # Включён трейлинг для пампов
    
    # Дополнительно
    delisting_sale=True,
    new_listing=False,
    user_order=True,
    reinvest_position=True,  # Включён реинвест
    double_asset=False
)


# ============================================
# СТРАТЕГИЯ 4: Депозит $6000
# ============================================
STRATEGY_6000 = TradingStrategy(
    name="Профессиональная стратегия для $6000",
    deposit_size=6000,
    
    # Капитал
    min_bnb=0.04,
    min_balance_percent=30.0,
    position_size_percent=20.0,
    
    # Условия входа
    min_order_multiplier=1.5,
    min_price_usd=0.02,
    min_daily_percent=-5.0,
    daily_percent=7.0,
    auto_daily_percent=True,
    
    # Объёмы
    min_value_usd=30000.0,  # 30k для более ликвидных активов
    sell_up_percent=5.0,
    max_trade_pairs=7,  # 7 позиций
    
    # Усреднение
    buy_down_percent=4.0,
    quantity_aver_multiplier=1.5,  # x1.5 - максимально агрессивно
    average_percent=8.0,
    max_aver=5,
    step_aver_percent=1.35,
    
    # Трейлинг
    use_trailing_stop=True,
    trailing_percent=1.0,
    trailing_part_percent=5.0,
    trailing_value_usd=50.0,
    
    # Автоматизация
    auto_trade_pairs=True,
    progressive_max_pairs=True,
    delta_deep=True,
    individual_depth=True,
    
    # Детектор пампов
    use_pump_detector=True,
    pump_order_multiplier=3.5,  # Максимально
    pump_up_percent=0.3,
    max_pump_pairs=12,  # 12 пампов одновременно
    trailing_pump=True,
    
    # Дополнительно
    delisting_sale=True,
    new_listing=True,  # Включён new listing
    user_order=True,
    reinvest_position=True,
    double_asset=True  # Включён double asset
)


# Словарь всех стратегий
STRATEGIES = {
    100: STRATEGY_100,
    1000: STRATEGY_1000,
    3000: STRATEGY_3000,
    6000: STRATEGY_6000
}


def select_strategy() -> TradingStrategy:
    """
    Интерактивный выбор стратегии
    
    Returns:
        Выбранная стратегия
    """
    print("\n" + "="*70)
    print("🎯 BINAUTOGO - Выбор торговой стратегии")
    print("="*70)
    print("\nДоступные стратегии:\n")
    
    print("1️⃣  Консервативная - Депозит $100")
    print("    • 4 позиции максимум")
    print("    • 18% размер позиции")
    print("    • 5% целевая прибыль")
    print("    • Консервативное усреднение (x1.2)")
    
    print("\n2️⃣  Сбалансированная - Депозит $1,000")
    print("    • 5 позиций максимум")
    print("    • 20% размер позиции")
    print("    • 5-7% целевая прибыль")
    print("    • Умеренное усреднение (x1.3)")
    
    print("\n3️⃣  Агрессивная - Депозит $3,000")
    print("    • 6 позиций максимум")
    print("    • 20% размер позиции")
    print("    • 7% целевая прибыль")
    print("    • Агрессивное усреднение (x1.4)")
    print("    • Реинвестирование включено")
    
    print("\n4️⃣  Профессиональная - Депозит $6,000")
    print("    • 7 позиций максимум")
    print("    • 20% размер позиции")
    print("    • 7% целевая прибыль")
    print("    • Максимальное усреднение (x1.5)")
    print("    • New Listing включён")
    print("    • Double Asset включён")
    
    print("\n" + "="*70)
    
    while True:
        try:
            choice = input("\nВыберите стратегию (1-4): ").strip()
            
            if choice == '1':
                strategy = STRATEGY_100
                break
            elif choice == '2':
                strategy = STRATEGY_1000
                break
            elif choice == '3':
                strategy = STRATEGY_3000
                break
            elif choice == '4':
                strategy = STRATEGY_6000
                break
            else:
                print("❌ Неверный выбор. Введите число от 1 до 4.")
        except KeyboardInterrupt:
            print("\n\n❌ Выход из программы")
            exit(0)
    
    # Подтверждение
    print("\n" + "="*70)
    print(f"✅ Выбрана стратегия: {strategy.name}")
    print(f"💰 Депозит: ${strategy.deposit_size:,}")
    print(f"📊 Макс. позиций: {strategy.max_trade_pairs}")
    print(f"📈 Размер позиции: {strategy.position_size_percent}%")
    print(f"🎯 Целевая прибыль: {strategy.sell_up_percent}%")
    print("="*70)
    
    confirm = input("\nПродолжить с этой стратегией? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Повторный выбор...\n")
        return select_strategy()
    
    return strategy


def print_strategy_comparison():
    """Вывод сравнительной таблицы стратегий"""
    print("\n" + "="*100)
    print("📊 СРАВНЕНИЕ СТРАТЕГИЙ")
    print("="*100)
    
    headers = ["Параметр", "$100", "$1,000", "$3,000", "$6,000"]
    print(f"{headers[0]:<30} {headers[1]:<15} {headers[2]:<15} {headers[3]:<15} {headers[4]:<15}")
    print("-" * 100)
    
    rows = [
        ("Макс. позиций", "4", "5", "6", "7"),
        ("Размер позиции", "18%", "20%", "20%", "20%"),
        ("Целевая прибыль", "5%", "5-7%", "7%", "7%"),
        ("Усреднение", "x1.2", "x1.3", "x1.4", "x1.5"),
        ("Макс. усреднений", "4", "4", "5", "5"),
        ("Детектор пампов", "5", "8", "10", "12"),
        ("Реинвестирование", "❌", "❌", "✅", "✅"),
        ("New Listing", "❌", "❌", "❌", "✅"),
        ("Double Asset", "❌", "❌", "❌", "✅"),
    ]
    
    for row in rows:
        print(f"{row[0]:<30} {row[1]:<15} {row[2]:<15} {row[3]:<15} {row[4]:<15}")
    
    print("="*100 + "\n")


# Тестирование
if __name__ == "__main__":
    # Сравнение стратегий
    print_strategy_comparison()
    
    # Интерактивный выбор
    selected = select_strategy()
    
    print(f"\n✅ Стратегия загружена и готова к использованию!")
    print(f"\nПараметры стратегии:")
    for key, value in selected.to_dict().items():
        print(f"  {key}: {value}")

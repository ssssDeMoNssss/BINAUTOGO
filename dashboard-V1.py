"""
BINAUTOGO - Web Dashboard
Интерактивный веб-интерфейс для мониторинга бота
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import time
import json
from pathlib import Path

# Настройка страницы
st.set_page_config(
    page_title="BINAUTOGO Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)


class BotDashboard:
    """Web Dashboard для мониторинга BINAUTOGO"""
    
    def __init__(self):
        self.refresh_interval = 5  # секунд
        self.data_dir = Path('exports')
        self.logs_dir = Path('logs')
    
    def run(self):
        """Запуск dashboard"""
        # Заголовок
        st.title("🤖 BINAUTOGO - AI Trading Bot Dashboard")
        st.caption("Мониторинг в реальном времени с DeepSeek AI")
        
        # Sidebar
        self.render_sidebar()
        
        # Главная панель
        tabs = st.tabs([
            "📊 Обзор", 
            "💼 Позиции", 
            "📈 Производительность",
            "🧠 DeepSeek AI",
            "⚙️ Настройки"
        ])
        
        with tabs[0]:
            self.render_overview_tab()
        
        with tabs[1]:
            self.render_positions_tab()
        
        with tabs[2]:
            self.render_performance_tab()
        
        with tabs[3]:
            self.render_deepseek_tab()
        
        with tabs[4]:
            self.render_settings_tab()
        
        # Авто-обновление
        time.sleep(self.refresh_interval)
        st.rerun()
    
    def render_sidebar(self):
        """Боковая панель"""
        st.sidebar.header("🎛️ Управление")
        
        # Статус бота
        status = self.load_bot_status()
        
        if status.get('running'):
            st.sidebar.success("✅ Бот работает")
        else:
            st.sidebar.error("❌ Бот остановлен")
        
        st.sidebar.metric("Цикл", f"#{status.get('cycle', 0)}")
        
        # Кнопки управления
        st.sidebar.subheader("Управление")
        
        col1, col2 = st.sidebar.columns(2)
        
        with col1:
            if st.button("▶️ Старт", use_container_width=True):
                st.sidebar.success("Бот запущен")
        
        with col2:
            if st.button("⏸️ Пауза", use_container_width=True):
                st.sidebar.warning("Бот приостановлен")
        
        if st.sidebar.button("🚨 PANIC-SALE 🚨", type="primary", use_container_width=True):
            if st.sidebar.checkbox("Я понимаю последствия"):
                st.sidebar.error("PANIC-SALE выполнен!")
                st.balloons()
        
        # Фильтры
        st.sidebar.subheader("Фильтры")
        
        self.timeframe = st.sidebar.selectbox(
            "Период",
            ["1 час", "24 часа", "7 дней", "30 дней", "Всё время"]
        )
        
        self.show_closed = st.sidebar.checkbox("Показать закрытые", value=False)
        
        # Информация
        st.sidebar.subheader("ℹ️ Информация")
        st.sidebar.info(
            f"Последнее обновление:\n{datetime.now().strftime('%H:%M:%S')}"
        )
    
    def render_overview_tab(self):
        """Вкладка обзора"""
        # Метрики в верхней части
        col1, col2, col3, col4 = st.columns(4)
        
        status = self.load_bot_status()
        
        with col1:
            st.metric(
                "💰 Портфель",
                f"${status.get('portfolio_value', 0):,.2f}",
                delta=f"${status.get('pnl', 0):+,.2f}"
            )
        
        with col2:
            st.metric(
                "📈 Позиций",
                status.get('positions', 0),
                delta=None
            )
        
        with col3:
            win_rate = self.calculate_win_rate()
            st.metric(
                "🎯 Win Rate",
                f"{win_rate:.1f}%",
                delta=None
            )
        
        with col4:
            daily_pnl = self.get_daily_pnl()
            st.metric(
                "📊 P&L Сегодня",
                f"${daily_pnl:+,.2f}",
                delta=f"{(daily_pnl/status.get('portfolio_value', 1)*100):+.2f}%"
            )
        
        st.divider()
        
        # Графики
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📈 Динамика портфеля")
            self.plot_portfolio_chart()
        
        with col2:
            st.subheader("🥧 Распределение позиций")
            self.plot_positions_pie()
        
        # Недавняя активность
        st.subheader("📋 Недавняя активность")
        self.show_recent_activity()
    
    def render_positions_tab(self):
        """Вкладка позиций"""
        st.subheader("💼 Открытые позиции")
        
        positions = self.load_positions()
        
        if not positions:
            st.info("📭 Нет открытых позиций")
            return
        
        # Таблица позиций
        df = pd.DataFrame(positions)
        
        # Форматирование
        df['Entry'] = df['entry_price'].apply(lambda x: f"${x:,.2f}")
        df['Current'] = df['current_price'].apply(lambda x: f"${x:,.2f}")
        df['P&L'] = df['unrealized_pnl'].apply(lambda x: f"${x:+,.2f}")
        df['P&L %'] = df['pnl_percent'].apply(lambda x: f"{x:+.2f}%")
        df['Value'] = df['value'].apply(lambda x: f"${x:,.2f}")
        
        # Цветовая кодировка
        def highlight_pnl(row):
            if row['unrealized_pnl'] > 0:
                return ['background-color: #90EE90'] * len(row)
            elif row['unrealized_pnl'] < 0:
                return ['background-color: #FFB6C1'] * len(row)
            return [''] * len(row)
        
        styled_df = df[['symbol', 'side', 'size', 'Entry', 'Current', 'P&L', 'P&L %', 'Value']].style.apply(
            highlight_pnl, axis=1
        )
        
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
        # Детали по позициям
        st.subheader("📊 Детали позиций")
        
        for pos in positions:
            with st.expander(f"{pos['symbol']} - {pos['side'].upper()}"):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Вход", f"${pos['entry_price']:,.2f}")
                    st.metric("Размер", f"{pos['size']:.6f}")
                
                with col2:
                    st.metric("Текущая", f"${pos['current_price']:,.2f}")
                    st.metric("Стоимость", f"${pos['value']:,.2f}")
                
                with col3:
                    st.metric(
                        "P&L", 
                        f"${pos['unrealized_pnl']:+,.2f}",
                        delta=f"{pos['pnl_percent']:+.2f}%"
                    )
    
    def render_performance_tab(self):
        """Вкладка производительности"""
        st.subheader("📈 Производительность")
        
        metrics = self.load_performance_metrics()
        
        if not metrics:
            st.warning("⚠️ Недостаточно данных")
            return
        
        # Ключевые метрики
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Всего сделок", metrics.get('total_trades', 0))
            st.metric("Win Rate", f"{metrics.get('win_rate', 0)*100:.1f}%")
        
        with col2:
            st.metric("Выигрышных", metrics.get('winning_trades', 0))
            st.metric("Проигрышных", metrics.get('losing_trades', 0))
        
        with col3:
            st.metric("Profit Factor", f"{metrics.get('profit_factor', 0):.2f}")
            st.metric("Sharpe Ratio", f"{metrics.get('sharpe_ratio', 0):.2f}")
        
        with col4:
            st.metric("Общий P&L", f"${metrics.get('total_pnl', 0):+,.2f}")
            st.metric("Макс. просадка", f"{metrics.get('max_drawdown', 0)*100:.2f}%")
        
        st.divider()
        
        # Графики
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("💰 История P&L")
            self.plot_pnl_history()
        
        with col2:
            st.subheader("📊 Распределение прибыли")
            self.plot_pnl_distribution()
        
        # Детальная таблица сделок
        st.subheader("📋 История сделок")
        self.show_trades_table()
    
    def render_deepseek_tab(self):
        """Вкладка DeepSeek AI"""
        st.subheader("🧠 DeepSeek AI Анализ")
        
        # Последние анализы
        st.subheader("📊 Последние анализы")
        
        analyses = self.load_recent_analyses()
        
        if not analyses:
            st.info("Нет данных об анализах")
            return
        
        for analysis in analyses[:5]:
            with st.expander(
                f"{analysis.get('symbol', 'Unknown')} - "
                f"{analysis.get('direction', 'neutral').upper()} "
                f"({analysis.get('confidence', 0)*100:.0f}%)"
            ):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.write("**Обоснование:**")
                    st.write(analysis.get('reasoning', 'Нет данных'))
                
                with col2:
                    st.metric("Уверенность", f"{analysis.get('confidence', 0)*100:.0f}%")
                    st.metric("Риск", f"{analysis.get('risk_score', 5)}/10")
                    st.metric("Цена входа", f"${analysis.get('entry_price', 0):,.2f}")
        
        # Статистика DeepSeek
        st.subheader("📈 Статистика анализов")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Всего анализов", len(analyses))
        
        with col2:
            bullish = sum(1 for a in analyses if a.get('direction') == 'bullish')
            st.metric("Bullish сигналов", bullish)
        
        with col3:
            avg_confidence = sum(a.get('confidence', 0) for a in analyses) / len(analyses) if analyses else 0
            st.metric("Средняя уверенность", f"{avg_confidence*100:.1f}%")
    
    def render_settings_tab(self):
        """Вкладка настроек"""
        st.subheader("⚙️ Настройки бота")
        
        # Текущая стратегия
        st.subheader("🎯 Текущая стратегия")
        
        strategy = self.load_current_strategy()
        
        if strategy:
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Название:** {strategy.get('name', 'Unknown')}")
                st.write(f"**Депозит:** ${strategy.get('deposit', 0):,}")
                st.write(f"**Макс. позиций:** {strategy.get('max_trade_pairs', 0)}")
                st.write(f"**Размер позиции:** {strategy.get('position_size', 0)}%")
            
            with col2:
                st.write(f"**Целевая прибыль:** {strategy.get('sell_up', 0)}%")
                st.write(f"**Усреднение:** x{strategy.get('quantity_aver', 0)}")
                st.write(f"**Трейлинг-стоп:** {'✅' if strategy.get('trailing_stop') else '❌'}")
                st.write(f"**Детектор пампов:** {'✅' if strategy.get('pump_detector') else '❌'}")
        
        st.divider()
        
        # Параметры
        st.subheader("🔧 Параметры")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.slider("Интервал анализа (мин)", 1, 10, 3)
            st.slider("Минимальная уверенность (%)", 50, 90, 65)
            st.slider("Макс. риск на сделку (%)", 1, 5, 2)
        
        with col2:
            st.selectbox("DeepSeek модель", ["deepseek-r1:7b", "deepseek-r1:32b"])
            st.checkbox("Авто-регулировка пар", value=True)
            st.checkbox("Delta Deep", value=True)
        
        if st.button("💾 Сохранить настройки", type="primary"):
            st.success("✅ Настройки сохранены!")
    
    # ============================================
    # ГРАФИКИ
    # ============================================
    
    def plot_portfolio_chart(self):
        """График динамики портфеля"""
        data = self.load_portfolio_history()
        
        if not data:
            st.info("Нет данных для графика")
            return
        
        df = pd.DataFrame(data)
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df['timestamp'],
            y=df['value'],
            mode='lines',
            name='Портфель',
            line=dict(color='#00D4AA', width=2),
            fill='tozeroy'
        ))
        
        fig.update_layout(
            xaxis_title="Время",
            yaxis_title="Стоимость (USD)",
            hovermode='x unified',
            height=300
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    def plot_positions_pie(self):
        """Круговая диаграмма позиций"""
        positions = self.load_positions()
        
        if not positions:
            st.info("Нет открытых позиций")
            return
        
        df = pd.DataFrame(positions)
        
        fig = px.pie(
            df,
            values='value',
            names='symbol',
            title='',
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        
        fig.update_layout(height=300)
        
        st.plotly_chart(fig, use_container_width=True)
    
    def plot_pnl_history(self):
        """График истории P&L"""
        trades = self.load_trades()
        
        if not trades:
            st.info("Нет данных о сделках")
            return
        
        df = pd.DataFrame(trades)
        df['cumulative_pnl'] = df['pnl'].cumsum()
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df.index,
            y=df['cumulative_pnl'],
            mode='lines',
            name='Накопленный P&L',
            line=dict(color='#4CAF50', width=2)
        ))
        
        fig.update_layout(
            xaxis_title="Сделка #",
            yaxis_title="P&L (USD)",
            height=300
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    def plot_pnl_distribution(self):
        """Распределение прибыли"""
        trades = self.load_trades()
        
        if not trades:
            st.info("Нет данных")
            return
        
        df = pd.DataFrame(trades)
        
        fig = go.Figure()
        
        fig.add_trace(go.Histogram(
            x=df['pnl'],
            nbinsx=30,
            name='P&L',
            marker_color='#2196F3'
        ))
        
        fig.update_layout(
            xaxis_title="P&L (USD)",
            yaxis_title="Количество",
            height=300
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # ============================================
    # ТАБЛИЦЫ
    # ============================================
    
    def show_recent_activity(self):
        """Недавняя активность"""
        trades = self.load_trades()
        
        if not trades:
            st.info("Нет недавней активности")
            return
        
        df = pd.DataFrame(trades[-10:])  # Последние 10
        
        df = df[['timestamp', 'symbol', 'side', 'pnl', 'pnl_percent']]
        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime('%H:%M:%S')
        df['pnl'] = df['pnl'].apply(lambda x: f"${x:+,.2f}")
        df['pnl_percent'] = df['pnl_percent'].apply(lambda x: f"{x:+.2f}%")
        
        st.dataframe(df, use_container_width=True, hide_index=True)
    
    def show_trades_table(self):
        """Таблица всех сделок"""
        trades = self.load_trades()
        
        if not trades:
            st.info("Нет сделок")
            return
        
        df = pd.DataFrame(trades)
        
        st.dataframe(
            df[['timestamp', 'symbol', 'side', 'entry_price', 'exit_price', 'pnl', 'pnl_percent']],
            use_container_width=True
        )
    
    # ============================================
    # ЗАГРУЗКА ДАННЫХ
    # ============================================
    
    def load_bot_status(self) -> dict:
        """Загрузка статуса бота"""
        # Здесь должна быть загрузка реальных данных
        # Пока возвращаем mock данные
        return {
            'running': True,
            'cycle': 142,
            'portfolio_value': 12450.75,
            'pnl': 2450.75,
            'positions': 3,
            'timestamp': datetime.now()
        }
    
    def load_positions(self) -> list:
        """Загрузка позиций"""
        return [
            {
                'symbol': 'BTC/USDT',
                'side': 'long',
                'size': 0.1,
                'entry_price': 43500.0,
                'current_price': 44200.0,
                'value': 4420.0,
                'unrealized_pnl': 70.0,
                'pnl_percent': 1.6
            },
            {
                'symbol': 'ETH/USDT',
                'side': 'long',
                'size': 2.5,
                'entry_price': 2850.0,
                'current_price': 2920.0,
                'value': 7300.0,
                'unrealized_pnl': 175.0,
                'pnl_percent': 2.5
            }
        ]
    
    def load_performance_metrics(self) -> dict:
        """Загрузка метрик производительности"""
        return {
            'total_trades': 45,
            'winning_trades': 32,
            'losing_trades': 13,
            'win_rate': 0.71,
            'profit_factor': 2.15,
            'sharpe_ratio': 1.85,
            'total_pnl': 2450.75,
            'max_drawdown': -0.08
        }
    
    def load_trades(self) -> list:
        """Загрузка сделок"""
        return []
    
    def load_portfolio_history(self) -> list:
        """История портфеля"""
        return []
    
    def load_recent_analyses(self) -> list:
        """Последние анализы DeepSeek"""
        return []
    
    def load_current_strategy(self) -> dict:
        """Текущая стратегия"""
        return {
            'name': 'Консервативная $100',
            'deposit': 100,
            'max_trade_pairs': 4,
            'position_size': 18,
            'sell_up': 5,
            'quantity_aver': 1.2,
            'trailing_stop': True,
            'pump_detector': True
        }
    
    def calculate_win_rate(self) -> float:
        """Расчёт win rate"""
        return 71.0
    
    def get_daily_pnl(self) -> float:
        """P&L за сегодня"""
        return 125.50


# Запуск dashboard
if __name__ == "__main__":
    dashboard = BotDashboard()
    dashboard.run()

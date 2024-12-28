from typing import List

from vnpy_ctastrategy import (
    CtaTemplate,
    StopOrder,
    TickData,
    BarData,
    TradeData,
    OrderData,
    BarGenerator,
    ArrayManager,
)

from vnpy.trader.object import PositionData
from vnpy.trader.constant import Interval, Direction, Offset


class JinGang(CtaTemplate):
    """"""

    author = "张强"

    fixed_size = 1  # 开仓手数
    twenty_window = 20
    twenty_mas = None

    parameters = ["twenty_window"]
    variables = ["twenty_mas"]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        self.bg = BarGenerator(self.on_bar, 15, self.on_15min_bar)
        self.am = ArrayManager()
        self.orders: List[OrderData] = []
        self.flag = 0
        self.stop_flag = False
        self.positions: List[PositionData] = []
        self.stop_long_price = 0  # 多单止损价位
        self.stop_short_price = 0  # 空单止损价位

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")
        self.load_bar(10)

    def on_start(self):
        """
        Callback when strategy is started.
        """
        self.write_log("策略启动")
        self.put_event()

    def on_stop(self):
        """
        Callback when strategy is stopped.
        """
        self.write_log("策略停止")

        self.put_event()

    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        """
        self.bg.update_tick(tick)

        # 开仓
        self.open_position(tick)
        # 止盈
        self.take_profit(tick)

    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        self.bg.update_bar(bar)

    def open_position(self, tick: TickData):
        bar: BarData = BarData(
            symbol=tick.symbol,
            exchange=tick.exchange,
            interval=Interval.MINUTE,
            datetime=tick.datetime,
            gateway_name=tick.gateway_name,
            open_price=tick.last_price,
            high_price=tick.last_price,
            low_price=tick.last_price,
            close_price=tick.last_price,
            open_interest=tick.open_interest
        )
        self.on_15min_bar(bar)

    def on_15min_bar(self, bar: BarData):
        # 初始化计算指标
        if bar.interval == Interval.FIFTEEN:
            # 重置开仓开关，保证15分钟最多只开一次仓
            self.flag = 0
            self.stop_flag = False
            self.am.update_bar(bar)
            if not self.am.inited:
                return
            # 清除上个15分钟内没有成交的单子，保证这个15分钟状态是干净的
            self.cancel_all()
            self.twenty_mas = self.am.sma(self.twenty_window, True)
            self.orders = self.cta_engine.main_engine.get_all_orders()

        if not self.trading:
            return
        if (bar.high_price > self.twenty_mas[-1]  and bar.high_price > self.am.high[-1] and
                self.am.close[-1] <= self.twenty_mas[-2]):
            price = bar.high_price + 2
            if self.pos == 0:
                if self.flag < 0:
                    return

                self.buy(price, self.fixed_size)
                self.write_log(f"开多单，开仓预设价{price}, 仓位{self.fixed_size}")
                self.flag  = -1
        elif (bar.low_price < self.twenty_mas[-1] and bar.low_price < self.am.low[-1] and
              self.am.high[-1] > self.twenty_mas[-2]):
            price = bar.low_price - 2
            if self.pos == 0:
                if self.flag < 0:
                    return
                self.short(price, self.fixed_size)
                self.write_log(f"开空单，开仓预设价{price}, 仓位{self.fixed_size}")
                self.flag = -1
        self.put_event()

    def take_profit(self, tick: TickData):
        """止盈"""
        orders = self.orders
        if self.pos == 0:
            return
        elif self.pos > 0:
            if tick.last_price < self.am.low[-1]:
                if orders:
                    for order in orders:
                        if (order.vt_symbol == self.vt_symbol and order.direction == Direction.SHORT
                                and order.offset == Offset.CLOSE):
                            return
                        else:
                            if self.stop_flag:
                                return
                            else:
                                self.sell(tick.last_price - 2, self.pos)
                                self.stop_flag = True
        else:
            if tick.last_price > self.am.high[-1]:
                if orders:
                    for order in orders:
                        if (order.vt_symbol == self.vt_symbol and order.direction == Direction.SHORT
                                and order.offset == Offset.CLOSE):
                            return
                        else:
                            if self.stop_flag:
                                return
                            else:
                                self.cover(tick.last_price + 2, abs(self.pos))
                                self.stop_flag = True

    def on_order(self, order: OrderData):
        """
        Callback of new order data update.
        """
        pass

    def on_trade(self, trade: TradeData):
        """
        Callback of new trade data update.
        """
        self.positions = self.cta_engine.main_engine.get_all_positions()
        if trade.direction == Direction.LONG and trade.offset == Offset.OPEN:
            self.stop_long_price = self.am.low[-1]
            self.sell(float(self.stop_long_price), trade.volume, True)
        elif trade.direction == Direction.SHORT and trade.offset == Offset.OPEN:
            self.stop_short_price = self.am.high[-1]
            self.cover(float(self.am.high[-1]), trade.volume, True)
        self.write_log(f"{trade.vt_symbol}:{trade.direction}:{trade.offset},设置止损成功")
        self.put_event()

    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update.
        """
        pass

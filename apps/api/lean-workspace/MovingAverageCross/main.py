from datetime import datetime

from AlgorithmImports import *


class MovingAverageCrossAlgorithm(QCAlgorithm):
    def Initialize(self):
        symbol_value = str(self.GetParameter("symbol", "AAPL")).upper()
        start_date = datetime.strptime(str(self.GetParameter("start_date", "2020-01-01")), "%Y-%m-%d")
        end_date = datetime.strptime(str(self.GetParameter("end_date", "2021-01-01")), "%Y-%m-%d")
        cash = float(self.GetParameter("cash", 100000))
        fast_period = int(self.GetParameter("fast_period", 20))
        slow_period = int(self.GetParameter("slow_period", 50))

        self.SetStartDate(start_date.year, start_date.month, start_date.day)
        self.SetEndDate(end_date.year, end_date.month, end_date.day)
        self.SetCash(cash)

        self.symbol = self.AddEquity(symbol_value, Resolution.Daily).Symbol
        self.fast = self.SMA(self.symbol, fast_period, Resolution.Daily)
        self.slow = self.SMA(self.symbol, slow_period, Resolution.Daily)
        self.previous_fast_above_slow = None
        self.SetWarmUp(slow_period, Resolution.Daily)

    def OnData(self, data):
        if self.IsWarmingUp or not self.fast.IsReady or not self.slow.IsReady:
            return

        fast_above_slow = self.fast.Current.Value > self.slow.Current.Value
        if self.previous_fast_above_slow is None:
            self.previous_fast_above_slow = fast_above_slow
            return

        if fast_above_slow and not self.previous_fast_above_slow:
            self.SetHoldings(self.symbol, 1.0)
        elif not fast_above_slow and self.previous_fast_above_slow:
            self.Liquidate(self.symbol)

        self.previous_fast_above_slow = fast_above_slow

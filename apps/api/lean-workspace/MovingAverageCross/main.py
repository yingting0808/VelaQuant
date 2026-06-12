from AlgorithmImports import *


class MovingAverageCrossAlgorithm(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2020, 1, 1)
        self.SetEndDate(2021, 1, 1)
        self.SetCash(100000)

        self.symbol = self.AddEquity("AAPL", Resolution.Daily).Symbol
        self.fast = self.SMA(self.symbol, 20, Resolution.Daily)
        self.slow = self.SMA(self.symbol, 50, Resolution.Daily)
        self.previous_fast_above_slow = None
        self.SetWarmUp(50, Resolution.Daily)

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

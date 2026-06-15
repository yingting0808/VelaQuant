from datetime import datetime, timedelta

from AlgorithmImports import *


class OpenBBDailyBar(PythonData):
    def GetSource(self, config, date, isLiveMode):
        symbol = config.Symbol.Value.lower()
        path = f"{Globals.DataFolder}/custom/openbb/{symbol}.csv"
        return SubscriptionDataSource(path, SubscriptionTransportMedium.LocalFile, FileFormat.Csv)

    def Reader(self, config, line, date, isLiveMode):
        if not line or line.startswith("date"):
            return None

        fields = line.split(",")
        bar = OpenBBDailyBar()
        bar.Symbol = config.Symbol
        bar.Time = datetime.strptime(fields[0], "%Y-%m-%d")
        bar.EndTime = bar.Time + timedelta(days=1)
        bar.Value = float(fields[4])
        bar["open"] = float(fields[1])
        bar["high"] = float(fields[2])
        bar["low"] = float(fields[3])
        bar["close"] = float(fields[4])
        bar["volume"] = float(fields[5])
        return bar


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

        self.symbol = self.AddData(OpenBBDailyBar, symbol_value, Resolution.Daily).Symbol
        self.SetBenchmark(self.symbol)
        self.fast = self.SMA(self.symbol, fast_period, Resolution.Daily)
        self.slow = self.SMA(self.symbol, slow_period, Resolution.Daily)
        self.previous_fast_above_slow = None
        self.SetWarmUp(slow_period, Resolution.Daily)

    def OnData(self, data):
        if not data.ContainsKey(self.symbol):
            return

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

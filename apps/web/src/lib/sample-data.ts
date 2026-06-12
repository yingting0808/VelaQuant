export const sampleDashboard = {
  portfolio: {
    name: "主组合",
    total_market_value: 4253.95,
    positions: [
      { ticker: "AAPL", market_value: 2101.2, weight: 0.49394 },
      { ticker: "MSFT", market_value: 2152.75, weight: 0.50606 }
    ]
  },
  alerts: [
    {
      ticker: "AAPL",
      title: "AAPL 10-Q filed",
      reason: "SEC filing",
      source: "mock_sec"
    }
  ],
  ai_prompts: [
    "解释当前页面",
    "识别组合风险",
    "生成多/中/空情景",
    "起草交易计划"
  ]
};

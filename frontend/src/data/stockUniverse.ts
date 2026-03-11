// ── Mock stock universe for GlobalSearchBar fuzzy search ──────────────────────

export interface StockEntry {
  ticker:   string;
  name:     string;
  exchange: string;
  country:  string;
  flag:     string;
  type:     "Equity" | "ETF";
  listings: number;
  logoUrl?: string;   // populated later from a real logo API
}

export const STOCK_UNIVERSE: StockEntry[] = [
  { ticker: "AAPL",    name: "Apple Inc.",                           exchange: "NASDAQ",         country: "United States", flag: "🇺🇸", type: "Equity", listings: 1 },
  { ticker: "MSFT",    name: "Microsoft Corporation",                exchange: "NASDAQ",         country: "United States", flag: "🇺🇸", type: "Equity", listings: 1 },
  { ticker: "TSLA",    name: "Tesla Inc.",                           exchange: "NASDAQ",         country: "United States", flag: "🇺🇸", type: "Equity", listings: 1 },
  { ticker: "GOOGL",   name: "Alphabet Inc.",                        exchange: "NASDAQ",         country: "United States", flag: "🇺🇸", type: "Equity", listings: 2 },
  { ticker: "AMZN",    name: "Amazon.com Inc.",                      exchange: "NASDAQ",         country: "United States", flag: "🇺🇸", type: "Equity", listings: 1 },
  { ticker: "BRK-B",   name: "Berkshire Hathaway Inc.",              exchange: "NYSE",           country: "United States", flag: "🇺🇸", type: "Equity", listings: 2 },
  { ticker: "SPY",     name: "SPDR S&P 500 ETF Trust",              exchange: "NYSE Arca",      country: "United States", flag: "🇺🇸", type: "ETF",    listings: 1 },
  { ticker: "NICE.TA", name: "NICE Ltd.",                            exchange: "TASE",           country: "Israel",        flag: "🇮🇱", type: "Equity", listings: 2 },
  { ticker: "BMW.DE",  name: "Bayerische Motoren Werke AG",          exchange: "XETRA",          country: "Germany",       flag: "🇩🇪", type: "Equity", listings: 3 },
  { ticker: "VOD.L",   name: "Vodafone Group Plc",                   exchange: "LSE",            country: "United Kingdom", flag: "🇬🇧", type: "Equity", listings: 2 },
  { ticker: "GMG.AX",  name: "Goodman Group",                        exchange: "ASX",            country: "Australia",     flag: "🇦🇺", type: "Equity", listings: 1 },
  { ticker: "NESN.SW", name: "Nestlé S.A.",                          exchange: "SIX Swiss Exchange", country: "Switzerland", flag: "🇨🇭", type: "Equity", listings: 1 },
  { ticker: "7203.T",  name: "Toyota Motor Corporation",             exchange: "TSE",            country: "Japan",         flag: "🇯🇵", type: "Equity", listings: 2 },
  { ticker: "MC.PA",   name: "LVMH Moët Hennessy Louis Vuitton",     exchange: "Euronext Paris", country: "France",        flag: "🇫🇷", type: "Equity", listings: 1 },
  { ticker: "2222.SR", name: "Saudi Aramco",                         exchange: "Tadawul",        country: "Saudi Arabia",  flag: "🇸🇦", type: "Equity", listings: 1 },
];

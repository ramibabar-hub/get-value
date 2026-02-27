from enum import Enum
from dataclasses import dataclass


class StatementType(Enum):
    INCOME = "income-statement"
    BALANCE = "balance-sheet-statement"
    CASHFLOW = "cash-flow-statement"


class ItemType(Enum):
    FLOW = "flow"    # Summed over 4 quarters for TTM (Income Stmt, Cash Flow)
    STOCK = "stock"  # Point-in-time, use latest quarter for TTM (Balance Sheet)


@dataclass
class FinancialItem:
    fmp_key: str
    label: str
    statement: StatementType
    item_type: ItemType


SCHEMA: list[FinancialItem] = [
    # ── Income Statement ──────────────────────────────────────────────────────
    FinancialItem("revenue",                              "Revenue",                StatementType.INCOME,   ItemType.FLOW),
    FinancialItem("costOfRevenue",                        "Cost of Revenue",        StatementType.INCOME,   ItemType.FLOW),
    FinancialItem("grossProfit",                          "Gross Profit",           StatementType.INCOME,   ItemType.FLOW),
    FinancialItem("grossProfitRatio",                     "Gross Margin %",         StatementType.INCOME,   ItemType.FLOW),
    FinancialItem("operatingExpenses",                    "Operating Expenses",     StatementType.INCOME,   ItemType.FLOW),
    FinancialItem("operatingIncome",                      "Operating Income",       StatementType.INCOME,   ItemType.FLOW),
    FinancialItem("operatingIncomeRatio",                 "Operating Margin %",     StatementType.INCOME,   ItemType.FLOW),
    FinancialItem("ebitda",                               "EBITDA",                 StatementType.INCOME,   ItemType.FLOW),
    FinancialItem("incomeBeforeTax",                      "Pre-tax Income",         StatementType.INCOME,   ItemType.FLOW),
    FinancialItem("incomeTaxExpense",                     "Income Tax",             StatementType.INCOME,   ItemType.FLOW),
    FinancialItem("netIncome",                            "Net Income",             StatementType.INCOME,   ItemType.FLOW),
    FinancialItem("netIncomeRatio",                       "Net Margin %",           StatementType.INCOME,   ItemType.FLOW),
    FinancialItem("eps",                                  "EPS",                    StatementType.INCOME,   ItemType.FLOW),
    FinancialItem("epsdiluted",                           "EPS Diluted",            StatementType.INCOME,   ItemType.FLOW),
    FinancialItem("weightedAverageShsOutDil",             "Diluted Shares",         StatementType.INCOME,   ItemType.FLOW),

    # ── Balance Sheet ─────────────────────────────────────────────────────────
    FinancialItem("cashAndCashEquivalents",               "Cash & Equivalents",     StatementType.BALANCE,  ItemType.STOCK),
    FinancialItem("shortTermInvestments",                 "Short-term Investments", StatementType.BALANCE,  ItemType.STOCK),
    FinancialItem("netReceivables",                       "Receivables",            StatementType.BALANCE,  ItemType.STOCK),
    FinancialItem("totalCurrentAssets",                   "Current Assets",         StatementType.BALANCE,  ItemType.STOCK),
    FinancialItem("totalNonCurrentAssets",                "Non-current Assets",     StatementType.BALANCE,  ItemType.STOCK),
    FinancialItem("totalAssets",                          "Total Assets",           StatementType.BALANCE,  ItemType.STOCK),
    FinancialItem("totalCurrentLiabilities",              "Current Liabilities",    StatementType.BALANCE,  ItemType.STOCK),
    FinancialItem("totalNonCurrentLiabilities",           "Non-current Liabilities",StatementType.BALANCE,  ItemType.STOCK),
    FinancialItem("totalLiabilities",                     "Total Liabilities",      StatementType.BALANCE,  ItemType.STOCK),
    FinancialItem("shortTermDebt",                        "Short-term Debt",        StatementType.BALANCE,  ItemType.STOCK),
    FinancialItem("longTermDebt",                         "Long-term Debt",         StatementType.BALANCE,  ItemType.STOCK),
    FinancialItem("totalDebt",                            "Total Debt",             StatementType.BALANCE,  ItemType.STOCK),
    FinancialItem("totalStockholdersEquity",              "Shareholders' Equity",   StatementType.BALANCE,  ItemType.STOCK),
    FinancialItem("retainedEarnings",                     "Retained Earnings",      StatementType.BALANCE,  ItemType.STOCK),

    # ── Cash Flow Statement ───────────────────────────────────────────────────
    FinancialItem("operatingCashFlow",                    "Operating Cash Flow",    StatementType.CASHFLOW, ItemType.FLOW),
    FinancialItem("capitalExpenditure",                   "CapEx",                  StatementType.CASHFLOW, ItemType.FLOW),
    FinancialItem("freeCashFlow",                         "Free Cash Flow",         StatementType.CASHFLOW, ItemType.FLOW),
    FinancialItem("dividendsPaid",                        "Dividends Paid",         StatementType.CASHFLOW, ItemType.FLOW),
    FinancialItem("commonStockRepurchased",               "Share Buybacks",         StatementType.CASHFLOW, ItemType.FLOW),
    FinancialItem("netCashUsedForInvestingActivites",     "Investing Cash Flow",    StatementType.CASHFLOW, ItemType.FLOW),
    FinancialItem("netCashUsedProvidedByFinancingActivities", "Financing Cash Flow",StatementType.CASHFLOW, ItemType.FLOW),
    FinancialItem("netChangeInCash",                      "Net Change in Cash",     StatementType.CASHFLOW, ItemType.FLOW),
]

# Lookup helpers
ITEMS_BY_KEY: dict[str, FinancialItem] = {item.fmp_key: item for item in SCHEMA}

ITEMS_BY_STATEMENT: dict[StatementType, list[FinancialItem]] = {}
for _item in SCHEMA:
    ITEMS_BY_STATEMENT.setdefault(_item.statement, []).append(_item)

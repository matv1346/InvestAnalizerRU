//
//  PortfolioPosition.swift
//  BrokerReportsApp
//
//  Модель позиции портфеля и сводных метрик
//

import Foundation
import SwiftData

/// Позиция по инструменту (рассчитанная по FIFO)
@Model
public final class PortfolioPosition {
    public var ticker: String
    public var name: String
    public var quantity: Double
    public var averagePrice: Double
    public var currentPrice: Double
    public var marketValue: Double
    public var unrealizedPnL: Double
    public var realizedPnL: Double
    public var assetType: AssetType
    public var currency: String
    public var weightPercent: Double
    
    public init(
        ticker: String,
        name: String = "",
        quantity: Double = 0,
        averagePrice: Double = 0,
        currentPrice: Double = 0,
        assetType: AssetType = .stock,
        currency: String = "RUB"
    ) {
        self.ticker = ticker
        self.name = name
        self.quantity = quantity
        self.averagePrice = averagePrice
        self.currentPrice = currentPrice
        self.marketValue = quantity * currentPrice
        self.unrealizedPnL = (currentPrice - averagePrice) * quantity
        self.realizedPnL = 0
        self.assetType = assetType
        self.currency = currency
        self.weightPercent = 0
    }
}

/// Тип актива
public enum AssetType: String, Codable, CaseIterable {
    case stock = "Акции"
    case bond = "Облигации"
    case fund = "Фонды (ETF/БПИФ)"
    case futures = "Фьючерсы"
    case options = "Опционы"
    case cash = "Кэш"
    case other = "Прочее"
    
    public var displayValue: String { rawValue }
}

/// Сводные метрики портфеля
@Model
public final class PortfolioMetrics {
    public var periodStart: Date
    public var periodEnd: Date
    public var totalValue: Double
    public var totalCost: Double
    public var totalPnL: Double
    public var roi: Double
    public var cagr: Double
    public var maxDrawdown: Double
    public var volatility: Double
    public var dividendYield: Double
    public var totalDividends: Double
    public var totalCoupons: Double
    public var totalCommissions: Double
    public var totalTaxes: Double
    public var cashFlow: Double
    public var allocation: [String: Double]
    
    public init(
        periodStart: Date = Date(),
        periodEnd: Date = Date(),
        totalValue: Double = 0,
        totalCost: Double = 0,
        totalPnL: Double = 0,
        roi: Double = 0,
        cagr: Double = 0,
        maxDrawdown: Double = 0,
        volatility: Double = 0,
        dividendYield: Double = 0,
        totalDividends: Double = 0,
        totalCoupons: Double = 0,
        totalCommissions: Double = 0,
        totalTaxes: Double = 0,
        cashFlow: Double = 0,
        allocation: [String: Double] = [:]
    ) {
        self.periodStart = periodStart
        self.periodEnd = periodEnd
        self.totalValue = totalValue
        self.totalCost = totalCost
        self.totalPnL = totalPnL
        self.roi = roi
        self.cagr = cagr
        self.maxDrawdown = maxDrawdown
        self.volatility = volatility
        self.dividendYield = dividendYield
        self.totalDividends = totalDividends
        self.totalCoupons = totalCoupons
        self.totalCommissions = totalCommissions
        self.totalTaxes = totalTaxes
        self.cashFlow = cashFlow
        self.allocation = allocation
    }
}

/// Дневная оценка портфеля для графиков
@Model
public final class DailyPortfolioValue {
    public var date: Date
    public var value: Double
    public var cost: Double
    
    public init(date: Date, value: Double, cost: Double = 0) {
        self.date = date
        self.value = value
        self.cost = cost
    }
}

extension PortfolioMetrics: Hashable {
    public func hash(into hasher: inout Hasher) {
        hasher.combine(periodStart)
        hasher.combine(periodEnd)
    }
    
    public static func == (lhs: PortfolioMetrics, rhs: PortfolioMetrics) -> Bool {
        lhs.periodStart == rhs.periodStart && lhs.periodEnd == rhs.periodEnd
    }
}

extension PortfolioPosition: Hashable {
    public func hash(into hasher: inout Hasher) {
        hasher.combine(ticker)
    }
    
    public static func == (lhs: PortfolioPosition, rhs: PortfolioPosition) -> Bool {
        lhs.ticker == rhs.ticker
    }
}

extension DailyPortfolioValue: Hashable {
    public func hash(into hasher: inout Hasher) {
        hasher.combine(date)
    }
    
    public static func == (lhs: DailyPortfolioValue, rhs: DailyPortfolioValue) -> Bool {
        lhs.date == rhs.date
    }
}

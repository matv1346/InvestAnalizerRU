//
//  MetricsCalculator.swift
//  BrokerReportsApp
//
//  Калькулятор инвестиционных метрик портфеля
//

import Foundation

/// Калькулятор метрик портфеля
public actor MetricsCalculator {
    
    /// Результат расчёта метрик
    public struct MetricsResult {
        public let metrics: PortfolioMetrics
        public let dailyValues: [DailyPortfolioValue]
        public let dividendsByMonth: [(month: String, amount: Double)]
        public let couponsByMonth: [(month: String, amount: Double)]
        public let cashFlowWaterfall: [(date: Date, deposit: Double, withdrawal: Double, net: Double)]
        
        public init(
            metrics: PortfolioMetrics,
            dailyValues: [DailyPortfolioValue] = [],
            dividendsByMonth: [(month: String, amount: Double)] = [],
            couponsByMonth: [(month: String, amount: Double)] = [],
            cashFlowWaterfall: [(date: Date, deposit: Double, withdrawal: Double, net: Double)] = []
        ) {
            self.metrics = metrics
            self.dailyValues = dailyValues
            self.dividendsByMonth = dividendsByMonth
            self.couponsByMonth = couponsByMonth
            self.cashFlowWaterfall = cashFlowWaterfall
        }
    }
    
    /// Расчёт всех метрик
    public func calculate(
        transactions: [Transaction],
        positions: [PortfolioPosition],
        currentPrices: [String: Double] = [:]
    ) async -> MetricsResult {
        print("📈 Расчёт инвестиционных метрик...")
        
        guard !transactions.isEmpty else {
            return MetricsResult(metrics: PortfolioMetrics())
        }
        
        // Сортировка транзакций
        let sortedTx = transactions.sorted { $0.date < $1.date }
        
        let periodStart = sortedTx.first!.date
        let periodEnd = sortedTx.last!.date
        
        // Денежные потоки
        let totalDeposits = transactions.filter { $0.type == .deposit }.reduce(0) { $0 + $1.amount }
        let totalWithdrawals = transactions.filter { $0.type == .withdrawal }.reduce(0) { $0 + abs($1.amount) }
        let totalDividends = transactions.filter { $0.type == .dividend }.reduce(0) { $0 + $1.amount }
        let totalCoupons = transactions.filter { $0.type == .coupon }.reduce(0) { $0 + $1.amount }
        let totalCommissions = transactions.filter { $0.type == .commission }.reduce(0) { $0 + $1.commission }
        let totalTaxes = transactions.filter { $0.type == .tax }.reduce(0) { $0 + abs($1.amount) }
        
        // Оценка портфеля
        var totalValue: Double = 0
        var totalCost: Double = 0
        
        for position in positions {
            // Обновляем цену если предоставлена
            if let currentPrice = currentPrices[position.ticker] {
                position.currentPrice = currentPrice
                position.marketValue = position.quantity * currentPrice
                position.unrealizedPnL = (currentPrice - position.averagePrice) * position.quantity
            }
            
            totalValue += position.marketValue
            totalCost += position.quantity * position.averagePrice
        }
        
        // Добавляем кэш (остаток от денежных операций)
        let cashBalance = totalDeposits - totalWithdrawals - totalCommissions - totalTaxes
        totalValue += cashBalance
        
        // P&L
        let totalRealizedPnL = positions.reduce(0) { $0 + $1.realizedPnL }
        let totalUnrealizedPnL = positions.reduce(0) { $0 + $1.unrealizedPnL }
        let totalPnL = totalRealizedPnL + totalUnrealizedPnL + totalDividends + totalCoupons
        
        // ROI
        let investedCapital = totalDeposits - totalWithdrawals
        let roi = investedCapital > 0 ? (totalPnL / investedCapital) * 100 : 0
        
        // CAGR
        let yearsFraction = periodEnd.timeIntervalSince(periodStart) / (365 * 24 * 3600)
        let cagr = yearsFraction > 0 && investedCapital > 0
            ? (pow((investedCapital + totalPnL) / investedCapital, 1 / yearsFraction) - 1) * 100
            : 0
        
        // Аллокация
        let allocation = calculateAllocation(positions: positions, cash: cashBalance)
        
        // Максимальная просадка и волатильность
        let dailyValues = await calculateDailyValues(transactions: sortedTx, positions: positions)
        let maxDrawdown = calculateMaxDrawdown(dailyValues: dailyValues)
        let volatility = calculateVolatility(dailyValues: dailyValues)
        
        // Дивидендная доходность
        let dividendYield = totalValue > 0 ? (totalDividends / totalValue) * 100 : 0
        
        // Группировка по месяцам
        let dividendsByMonth = groupByMonth(transactions: transactions.filter { $0.type == .dividend })
        let couponsByMonth = groupByMonth(transactions: transactions.filter { $0.type == .coupon })
        
        // Waterfall cashflow
        let cashFlowWaterfall = calculateCashFlowWaterfall(transactions: sortedTx)
        
        let metrics = PortfolioMetrics(
            periodStart: periodStart,
            periodEnd: periodEnd,
            totalValue: totalValue,
            totalCost: totalCost,
            totalPnL: totalPnL,
            roi: roi,
            cagr: cagr,
            maxDrawdown: maxDrawdown,
            volatility: volatility,
            dividendYield: dividendYield,
            totalDividends: totalDividends,
            totalCoupons: totalCoupons,
            totalCommissions: totalCommissions,
            totalTaxes: totalTaxes,
            cashFlow: cashBalance,
            allocation: allocation
        )
        
        print("✅ Метрики рассчитаны: ROI=\(String(format: "%.2f", roi))%, P&L=\(String(format: "%.2f", totalPnL))")
        
        return MetricsResult(
            metrics: metrics,
            dailyValues: dailyValues,
            dividendsByMonth: dividendsByMonth,
            couponsByMonth: couponsByMonth,
            cashFlowWaterfall: cashFlowWaterfall
        )
    }
    
    /// Расчёт аллокации портфеля
    private func calculateAllocation(positions: [PortfolioPosition], cash: Double) -> [String: Double] {
        var allocation: [String: Double] = [:]
        
        let totalValue = positions.reduce(0) { $0 + $1.marketValue } + cash
        
        guard totalValue > 0 else { return allocation }
        
        // По типам активов
        for assetType in AssetType.allCases {
            let typeValue = positions.filter { $0.assetType == assetType }.reduce(0) { $0 + $1.marketValue }
            allocation[assetType.displayValue] = (typeValue / totalValue) * 100
        }
        
        // Кэш
        allocation["Кэш"] = (cash / totalValue) * 100
        
        return allocation
    }
    
    /// Расчёт дневных значений портфеля
    private func calculateDailyValues(transactions: [Transaction], positions: [PortfolioPosition]) async -> [DailyPortfolioValue] {
        guard let firstDate = transactions.first?.date,
              let lastDate = transactions.last?.date else {
            return []
        }
        
        var dailyValues: [DailyPortfolioValue] = []
        var currentDate = firstDate
        let calendar = Calendar.current
        
        // Упрощённый расчёт - только по датам транзакций
        var runningValue: Double = 0
        var runningCost: Double = 0
        
        for tx in transactions {
            switch tx.type {
            case .buy:
                runningCost += tx.amount
                runningValue += tx.amount
            case .sell:
                runningValue += tx.amount - tx.commission
            case .deposit:
                runningValue += tx.amount
            case .withdrawal:
                runningValue -= abs(tx.amount)
            case .dividend, .coupon:
                runningValue += tx.amount
            case .commission, .tax:
                runningValue -= abs(tx.amount)
            default:
                break
            }
            
            dailyValues.append(DailyPortfolioValue(
                date: tx.date,
                value: runningValue,
                cost: runningCost
            ))
        }
        
        return dailyValues
    }
    
    /// Расчёт максимальной просадки
    private func calculateMaxDrawdown(dailyValues: [DailyPortfolioValue]) -> Double {
        guard !dailyValues.isEmpty else { return 0 }
        
        var maxPeak = dailyValues.first!.value
        var maxDrawdown: Double = 0
        
        for dv in dailyValues {
            if dv.value > maxPeak {
                maxPeak = dv.value
            }
            
            let drawdown = (maxPeak - dv.value) / maxPeak * 100
            if drawdown > maxDrawdown {
                maxDrawdown = drawdown
            }
        }
        
        return maxDrawdown
    }
    
    /// Расчёт волатильности
    private func calculateVolatility(dailyValues: [DailyPortfolioValue]) -> Double {
        guard dailyValues.count > 1 else { return 0 }
        
        var returns: [Double] = []
        
        for i in 1..<dailyValues.count {
            let prevValue = dailyValues[i - 1].value
            let currentValue = dailyValues[i].value
            
            if prevValue > 0 {
                let dailyReturn = (currentValue - prevValue) / prevValue
                returns.append(dailyReturn)
            }
        }
        
        guard !returns.isEmpty else { return 0 }
        
        // Стандартное отклонение
        let mean = returns.reduce(0, +) / Double(returns.count)
        let variance = returns.reduce(0) { $0 + pow($1 - mean, 2) } / Double(returns.count)
        let stdDev = sqrt(variance)
        
        // Годовая волатильность (252 торговых дня)
        return stdDev * sqrt(252) * 100
    }
    
    /// Группировка по месяцам
    private func groupByMonth(transactions: [Transaction]) -> [(month: String, amount: Double)] {
        var grouped: [String: Double] = [:]
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM"
        
        for tx in transactions {
            let monthKey = formatter.string(from: tx.date)
            grouped[monthKey, default: 0] += tx.amount
        }
        
        return grouped.map { ($0.key, $0.value) }.sorted { $0.0 < $1.0 }
    }
    
    /// Waterfall денежного потока
    private func calculateCashFlowWaterfall(transactions: [Transaction]) -> [(date: Date, deposit: Double, withdrawal: Double, net: Double)] {
        var waterfall: [(date: Date, deposit: Double, withdrawal: Double, net: Double)] = []
        
        let deposits = transactions.filter { $0.type == .deposit }
        let withdrawals = transactions.filter { $0.type == .withdrawal }
        
        var cumulativeDeposit: Double = 0
        var cumulativeWithdrawal: Double = 0
        
        let allDates = Set(deposits.map { $0.date } + withdrawals.map { $0.date }).sorted()
        
        for date in allDates {
            let dayDeposits = deposits.filter { Calendar.current.isDate($0.date, inSameDayAs: date) }
                .reduce(0) { $0 + $1.amount }
            let dayWithdrawals = withdrawals.filter { Calendar.current.isDate($0.date, inSameDayAs: date) }
                .reduce(0) { $0 + abs($1.amount) }
            
            cumulativeDeposit += dayDeposits
            cumulativeWithdrawal += dayWithdrawals
            
            waterfall.append((
                date: date,
                deposit: cumulativeDeposit,
                withdrawal: cumulativeWithdrawal,
                net: cumulativeDeposit - cumulativeWithdrawal
            ))
        }
        
        return waterfall
    }
}

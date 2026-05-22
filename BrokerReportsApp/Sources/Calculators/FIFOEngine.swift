//
//  FIFOEngine.swift
//  BrokerReportsApp
//
//  Движок расчёта позиций по методу FIFO (First In, First Out)
//

import Foundation

/// Лот для FIFO расчёта
private struct FIFOLot {
    var date: Date
    var quantity: Double
    var price: Double
    let originalQuantity: Double
    
    init(date: Date, quantity: Double, price: Double) {
        self.date = date
        self.quantity = quantity
        self.price = price
        self.originalQuantity = quantity
    }
    
    var remainingValue: Double {
        return quantity * price
    }
}

/// Позиция с лотами
private struct PositionWithLots {
    var ticker: String
    var name: String
    var lots: [FIFOLot]
    var realizedPnL: Double = 0
    var currency: String = "RUB"
    
    var totalQuantity: Double {
        return lots.reduce(0) { $0 + $1.quantity }
    }
    
    var averagePrice: Double {
        guard totalQuantity > 0 else { return 0 }
        let totalValue = lots.reduce(0) { $0 + $1.remainingValue }
        return totalValue / totalQuantity
    }
    
    var costBasis: Double {
        return lots.reduce(0) { $0 + $1.remainingValue }
    }
}

/// Движок FIFO расчётов
public actor FIFOEngine {
    
    /// Результат расчёта FIFO
    public struct FIFOResult {
        public let positions: [PortfolioPosition]
        public let realizedPnLByTicker: [String: Double]
        public let totalRealizedPnL: Double
        public let transactionsProcessed: Int
        public let warnings: [String]
        
        public init(
            positions: [PortfolioPosition],
            realizedPnLByTicker: [String: Double] = [:],
            totalRealizedPnL: Double = 0,
            transactionsProcessed: Int = 0,
            warnings: [String] = []
        ) {
            self.positions = positions
            self.realizedPnLByTicker = realizedPnLByTicker
            self.totalRealizedPnL = totalRealizedPnL
            self.transactionsProcessed = transactionsProcessed
            self.warnings = warnings
        }
    }
    
    /// Расчёт позиций по FIFO
    public func calculatePositions(transactions: [Transaction]) async -> FIFOResult {
        print("🧮 Начало FIFO расчёта для \(transactions.count) транзакций")
        
        // Сортировка по дате
        let sortedTransactions = transactions.sorted { $0.date < $1.date }
        
        // Хранилище позиций с лотами
        var positions: [String: PositionWithLots] = [:]
        var realizedPnLByTicker: [String: Double] = [:]
        var warnings: [String] = []
        
        for transaction in sortedTransactions {
            switch transaction.type {
            case .buy:
                await handleBuy(transaction, positions: &positions)
            case .sell:
                await handleSell(transaction, positions: &positions, realizedPnL: &realizedPnLByTicker, warnings: &warnings)
            case .dividend, .coupon:
                // Дивиденды и купоны не влияют на количество акций
                break
            case .deposit, .withdrawal, .commission, .tax, .marginCall, .unknown:
                // Денежные операции не влияют на позиции
                break
            }
        }
        
        // Конвертация в PortfolioPosition
        var portfolioPositions: [PortfolioPosition] = []
        
        for (ticker, position) in positions {
            guard position.totalQuantity > 0 else { continue }
            
            let portfolioPosition = PortfolioPosition(
                ticker: ticker,
                name: position.name,
                quantity: position.totalQuantity,
                averagePrice: position.averagePrice,
                currentPrice: position.averagePrice, // Будет обновлено позже из внешних данных
                assetType: determineAssetType(ticker: ticker),
                currency: position.currency
            )
            
            // Добавляем реализованный P&L
            if let realizedPnL = realizedPnLByTicker[ticker] {
                portfolioPosition.realizedPnL = realizedPnL
            }
            
            portfolioPositions.append(portfolioPosition)
        }
        
        let totalRealizedPnL = realizedPnLByTicker.values.reduce(0, +)
        
        print("✅ Завершён FIFO расчёт: \(portfolioPositions.count) позиций")
        
        return FIFOResult(
            positions: portfolioPositions,
            realizedPnLByTicker: realizedPnLByTicker,
            totalRealizedPnL: totalRealizedPnL,
            transactionsProcessed: sortedTransactions.count,
            warnings: warnings
        )
    }
    
    /// Обработка покупки
    private func handleBuy(_ tx: Transaction, positions: inout [String: PositionWithLots]) {
        if positions[tx.ticker] == nil {
            positions[tx.ticker] = PositionWithLots(
                ticker: tx.ticker,
                name: tx.name,
                lots: [],
                currency: tx.currency
            )
        }
        
        // Добавляем новый лот
        let lot = FIFOLot(date: tx.date, quantity: tx.quantity, price: tx.price)
        positions[tx.ticker]?.lots.append(lot)
    }
    
    /// Обработка продажи
    private func handleSell(
        _ tx: Transaction,
        positions: inout [String: PositionWithLots],
        realizedPnL: inout [String: Double],
        warnings: inout [String]
    ) {
        guard var position = positions[tx.ticker] else {
            warnings.append("Продажа без позиции: \(tx.ticker) на \(tx.date)")
            return
        }
        
        var quantityToSell = tx.quantity
        var sellProceeds = tx.amount - tx.commission // Выручка от продажи
        
        // Проходим по лотам в порядке FIFO
        for i in 0..<position.lots.count {
            guard quantityToSell > 0.001 else { break } // Учитываем погрешность
            
            var lot = position.lots[i]
            
            if lot.quantity <= quantityToSell {
                // Продаём весь лот
                let lotCost = lot.quantity * lot.price
                let lotPnL = (sellProceeds * (lot.quantity / tx.quantity)) - lotCost
                
                realizedPnL[tx.ticker, default: 0] += lotPnL
                
                quantityToSell -= lot.quantity
                sellProceeds -= sellProceeds * (lot.quantity / tx.quantity)
                
                position.lots[i].quantity = 0 // Лот полностью продан
            } else {
                // Продаём часть лота
                let partialCost = quantityToSell * lot.price
                let partialPnL = sellProceeds - partialCost
                
                realizedPnL[tx.ticker, default: 0] += partialPnL
                
                position.lots[i].quantity -= quantityToSell
                quantityToSell = 0
            }
        }
        
        // Удаляем полностью проданные лоты
        position.lots.removeAll { $0.quantity < 0.001 }
        
        if position.lots.isEmpty && quantityToSell > 0.001 {
            warnings.append("Частичная продажа: не хватило лотов для \(tx.ticker)")
        }
        
        positions[tx.ticker] = position
    }
    
    /// Определение типа актива по тику
    private func determineAssetType(ticker: String) -> AssetType {
        let upper = ticker.uppercased()
        
        // Облигации обычно имеют SU, RU или содержат "OB"
        if upper.contains("SU") || upper.contains("RU") || upper.contains("OB") {
            return .bond
        }
        
        // Фонды часто имеют суффиксы .ME или содержат "EQ"
        if upper.contains("EQ") || upper.hasSuffix(".ME") {
            return .fund
        }
        
        // Фьючерсы имеют спецификации
        if upper.contains("BR") || upper.contains("SR") || upper.contains("MR") {
            return .futures
        }
        
        return .stock
    }
}

// MARK: - Unit Test Support

extension FIFOEngine {
    /// Тестовый расчёт для юнит-тестов
    public func calculateForTest(transactions: [Transaction]) async -> FIFOResult {
        return await calculatePositions(transactions: transactions)
    }
}

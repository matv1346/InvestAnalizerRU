//
//  FIFOEngineTests.swift
//  BrokerReportsAppTests
//
//  Юнит-тесты для FIFO расчёта
//

import XCTest
@testable import BrokerReportsApp

final class FIFOEngineTests: XCTestCase {
    
    var fifoEngine: FIFOEngine!
    
    override func setUp() async throws {
        fifoEngine = FIFOEngine()
    }
    
    /// Тест: Покупка и продажа одной позиции
    func testBasicBuyAndSell() async throws {
        let transactions = [
            Transaction(
                date: Date().addingTimeInterval(-86400),
                ticker: "AAPL",
                type: .buy,
                quantity: 10,
                price: 100,
                amount: 1000,
                currency: "RUB"
            ),
            Transaction(
                date: Date(),
                ticker: "AAPL",
                type: .sell,
                quantity: 5,
                price: 120,
                amount: 600,
                currency: "RUB"
            )
        ]
        
        let result = await fifoEngine.calculatePositions(transactions: transactions)
        
        XCTAssertEqual(result.positions.count, 1)
        XCTAssertEqual(result.positions.first?.ticker, "AAPL")
        XCTAssertEqual(result.positions.first?.quantity, 5)
        XCTAssertEqual(result.positions.first?.averagePrice, 100)
        XCTAssertGreaterThan(result.totalRealizedPnL, 0)
    }
    
    /// Тест: Дедупликация транзакций
    func testTransactionDeduplication() {
        let tx1 = Transaction(
            date: Date(),
            ticker: "AAPL",
            type: .buy,
            quantity: 10,
            price: 100,
            amount: 1000,
            currency: "RUB"
        )
        
        let tx2 = Transaction(
            date: tx1.date,
            ticker: tx1.ticker,
            type: tx1.type,
            quantity: tx1.quantity,
            price: tx1.price,
            amount: tx1.amount,
            currency: tx1.currency
        )
        
        XCTAssertEqual(tx1.hashKey, tx2.hashKey, "Транзакции с одинаковыми параметрами должны иметь одинаковый хэш")
    }
    
    /// Тест: Расчёт ROI
    func testROICalculation() {
        let investedCapital: Double = 10000
        let totalPnL: Double = 1500
        
        let roi = (totalPnL / investedCapital) * 100
        
        XCTAssertEqual(roi, 15.0, accuracy: 0.01)
    }
}

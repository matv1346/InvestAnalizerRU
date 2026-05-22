//
//  Transaction.swift
//  BrokerReportsApp
//
//  Модель транзакции - единое представление данных из всех источников
//

import Foundation
import SwiftData

@Model
public final class Transaction {
    public var id: String
    public var date: Date
    public var ticker: String
    public var name: String
    public var type: TransactionType
    public var quantity: Double
    public var price: Double
    public var amount: Double
    public var currency: String
    public var commission: Double
    public var accruedInterest: Double
    public var status: TransactionStatus
    public var sourceFile: String
    public var createdAt: Date
    
    public init(
        id: String = UUID().uuidString,
        date: Date,
        ticker: String,
        name: String = "",
        type: TransactionType,
        quantity: Double,
        price: Double,
        amount: Double,
        currency: String = "RUB",
        commission: Double = 0,
        accruedInterest: Double = 0,
        status: TransactionStatus = .executed,
        sourceFile: String = ""
    ) {
        self.id = id
        self.date = date
        self.ticker = ticker
        self.name = name
        self.type = type
        self.quantity = quantity
        self.price = price
        self.amount = amount
        self.currency = currency
        self.commission = commission
        self.accruedInterest = accruedInterest
        self.status = status
        self.sourceFile = sourceFile
        self.createdAt = Date()
    }
    
    /// Хэш для дедупликации
    public var hashKey: String {
        let dateFormatter = DateFormatter()
        dateFormatter.dateFormat = "yyyy-MM-dd"
        let dateStr = dateFormatter.string(from: date)
        return "\(dateStr)|\(ticker)|\(type.rawValue)|\(quantity)|\(price)"
    }
}

// MARK: - Enums

@Model
public enum TransactionType: String, Codable, CaseIterable {
    case buy = "Покупка"
    case sell = "Продажа"
    case dividend = "Дивиденд"
    case coupon = "Купон"
    case deposit = "Пополнение"
    case withdrawal = "Вывод"
    case commission = "Комиссия"
    case tax = "Налог"
    case marginCall = "Вариационная маржа"
    case unknown = "Неизвестно"
    
    public var displayValue: String { rawValue }
}

@Model
public enum TransactionStatus: String, Codable, CaseIterable {
    case executed = "Исполнена"
    case partiallyExecuted = "Частично исполнена"
    case cancelled = "Отменена"
    case declined = "Отклонена"
    case pending = "Ожидает"
    
    public var displayValue: String { rawValue }
    
    /// Статусы, которые учитываются в расчётах
    public static var validForCalculation: [TransactionStatus] {
        [.executed, .partiallyExecuted]
    }
}

// MARK: - Hashable Extension

extension Transaction: Hashable {
    public func hash(into hasher: inout Hasher) {
        hasher.combine(id)
    }
    
    public static func == (lhs: Transaction, rhs: Transaction) -> Bool {
        lhs.id == rhs.id
    }
}

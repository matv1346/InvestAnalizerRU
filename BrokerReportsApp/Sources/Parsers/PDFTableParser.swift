//
//  PDFTableParser.swift
//  BrokerReportsApp
//
//  Парсер таблиц из PDF файлов с использованием PDFKit
//

import Foundation
import PDFKit

/// Парсер таблиц из PDF файлов
public actor PDFTableParser {
    
    /// Маппинг колонок
    private let dateColumns = ["Дата", "Date", "Время"]
    private let typeColumns = ["Операция", "Тип", "Описание", "Operation"]
    private let tickerColumns = ["Тикер", "Инструмент", "Код", "Ticker", "Symbol"]
    private let quantityColumns = ["Количество", "Кол-во", "Qty", "Quantity"]
    private let priceColumns = ["Цена", "Price"]
    private let amountColumns = ["Сумма", "Amount", "Total"]
    private let commissionColumns = ["Комиссия", "Commission", "Fee"]
    
    /// Парсинг файла
    public func parse(fileURL: URL) async throws -> [Transaction] {
        guard fileURL.isFileURL else {
            throw ParserError.invalidURL
        }
        
        let ext = fileURL.pathExtension.lowercased()
        guard ext == "pdf" else {
            throw ParserError.unsupportedFormat(ext)
        }
        
        print("📊 Начало парсинга PDF: \(fileURL.lastPathComponent)")
        
        guard let document = PDFDocument(url: fileURL) else {
            throw ParserError.invalidFile("Не удалось открыть PDF документ")
        }
        
        var transactions: [Transaction] = []
        
        // Проход по всем страницам
        for pageIndex in 0..<document.pageCount {
            guard let page = document.page(at: pageIndex) else { continue }
            
            // Извлечение текста с позиции
            let pageTransactions = extractTransactionsFromPage(page: page, pageNumber: pageIndex + 1, fileName: fileURL.lastPathComponent)
            transactions.append(contentsOf: pageTransactions)
        }
        
        print("✅ Распарсено транзакций из PDF: \(transactions.count)")
        return transactions
    }
    
    /// Извлечение транзакций со страницы
    private func extractTransactionsFromPage(page: PDFPage, pageNumber: Int, fileName: String) -> [Transaction] {
        var transactions: [Transaction] = []
        
        // Получаем текст с информацией о позициях
        guard let text = page.string else { return [] }
        
        // Разбиваем на строки
        let lines = text.components(separatedBy: .newlines)
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }
        
        // Поиск табличных данных
        var headers: [String]?
        var columnIndexMapping: [String: Int]?
        
        for (lineIndex, line) in lines.enumerated() {
            // Попытка определить заголовки
            if headers == nil && isHeaderLine(line) {
                headers = parseHeaderLine(line)
                columnIndexMapping = createColumnMapping(headers: headers!)
                continue
            }
            
            // Если заголовки найдены, пробуем распарсить как данные
            if let mapping = columnIndexMapping {
                if let transaction = parseDataLine(
                    line: line,
                    columnMapping: mapping,
                    pageNumber: pageNumber,
                    fileName: fileName
                ) {
                    transactions.append(transaction)
                }
            }
        }
        
        return transactions
    }
    
    /// Проверка, является ли строка заголовком
    private func isHeaderLine(_ line: String) -> Bool {
        let lower = line.lowercased()
        
        // Ищем ключевые слова заголовков
        let headerKeywords = ["дата", "тикер", "количество", "цена", "сумма", "operation", "quantity", "price"]
        let matches = headerKeywords.filter { lower.contains($0) }
        
        return matches.count >= 3
    }
    
    /// Парсинг строки заголовков
    private func parseHeaderLine(_ line: String) -> [String] {
        // Разбиваем по нескольким пробелам или табуляции
        let components = line.components(separatedBy: .whitespaces)
            .filter { !$0.isEmpty }
        return components
    }
    
    /// Создание маппинга колонок
    private func createColumnMapping(headers: [String]) -> [String: Int] {
        var mapping: [String: Int] = [:]
        
        for (index, header) in headers.enumerated() {
            let normalized = header.lowercased()
            
            if dateColumns.contains(where: { normalized.contains($0.lowercased()) }) {
                mapping["date"] = index
            }
            if typeColumns.contains(where: { normalized.contains($0.lowercased()) }) {
                mapping["type"] = index
            }
            if tickerColumns.contains(where: { normalized.contains($0.lowercased()) }) {
                mapping["ticker"] = index
            }
            if quantityColumns.contains(where: { normalized.contains($0.lowercased()) }) {
                mapping["quantity"] = index
            }
            if priceColumns.contains(where: { normalized.contains($0.lowercased()) }) {
                mapping["price"] = index
            }
            if amountColumns.contains(where: { normalized.contains($0.lowercased()) }) {
                mapping["amount"] = index
            }
            if commissionColumns.contains(where: { normalized.contains($0.lowercased()) }) {
                mapping["commission"] = index
            }
        }
        
        return mapping
    }
    
    /// Парсинг строки данных
    private func parseDataLine(
        line: String,
        columnMapping: [String: Int],
        pageNumber: Int,
        fileName: String
    ) -> Transaction? {
        let components = line.components(separatedBy: .whitespaces)
            .filter { !$0.isEmpty }
        
        guard !components.isEmpty else { return nil }
        
        // Получаем значения по индексу
        let getValue: (String) -> String? = { key in
            guard let index = columnMapping[key], index < components.count else {
                return nil
            }
            return components[index]
        }
        
        // Парсинг даты
        guard let dateString = getValue("date"),
              let date = parseDate(dateString) else {
            return nil
        }
        
        // Парсинг типа
        let typeString = getValue("type") ?? ""
        let type = parseTransactionType(typeString)
        
        // Парсинг тикера
        let ticker = getValue("ticker") ?? "UNKNOWN"
        
        // Парсинг числовых значений
        let quantityStr = getValue("quantity") ?? "0"
        let quantity = parseNumber(quantityStr) ?? 0
        
        let priceStr = getValue("price") ?? "0"
        let price = parseNumber(priceStr) ?? 0
        
        let amountStr = getValue("amount") ?? "0"
        let amount = parseNumber(amountStr) ?? 0
        
        let commissionStr = getValue("commission") ?? "0"
        let commission = parseNumber(commissionStr) ?? 0
        
        return Transaction(
            id: UUID().uuidString,
            date: date,
            ticker: ticker,
            name: "",
            type: type,
            quantity: quantity,
            price: price,
            amount: amount,
            currency: "RUB",
            commission: commission,
            accruedInterest: 0,
            status: .executed,
            sourceFile: fileName
        )
    }
    
    /// Парсинг даты
    private func parseDate(_ string: String) -> Date? {
        let formatters: [DateFormatter] = [
            createFormatter("dd.MM.yyyy"),
            createFormatter("yyyy-MM-dd"),
            createFormatter("dd/MM/yyyy"),
            createFormatter("dd.MM.yy")
        ]
        
        for formatter in formatters {
            if let date = formatter.date(from: string) {
                return date
            }
        }
        return nil
    }
    
    private func createFormatter(_ format: String) -> DateFormatter {
        let formatter = DateFormatter()
        formatter.dateFormat = format
        formatter.locale = Locale(identifier: "ru_RU")
        return formatter
    }
    
    /// Парсинг числа
    private func parseNumber(_ string: String) -> Double? {
        let cleaned = string
            .replacingOccurrences(of: " ", with: "")
            .replacingOccurrences(of: ",", with: ".")
            .trimmingCharacters(in: .whitespaces)
        return Double(cleaned)
    }
    
    /// Определение типа транзакции
    private func parseTransactionType(_ string: String) -> TransactionType {
        let lower = string.lowercased()
        
        if lower.contains("покупк") || lower.contains("buy") { return .buy }
        if lower.contains("продаж") || lower.contains("sell") { return .sell }
        if lower.contains("дивиденд") || lower.contains("dividend") { return .dividend }
        if lower.contains("купон") || lower.contains("coupon") { return .coupon }
        if lower.contains("комисс") || lower.contains("commission") { return .commission }
        
        return .unknown
    }
}

// MARK: - Alternative Text Extraction

extension PDFTableParser {
    
    /// Альтернативный метод извлечения текста с координатами
    func extractTextWithPositions(from page: PDFPage) -> [(text: String, box: PDFRect)] {
        var result: [(text: String, box: PDFRect)] = []
        
        guard let data = page.dataRepresentation(
            of: .text,
            attributes: nil
        ) else { return result }
        
        // PDFKit не предоставляет прямого доступа к позициям слов
        // Для продвинутого парсинга потребуется использовать Core Graphics
        
        return result
    }
}

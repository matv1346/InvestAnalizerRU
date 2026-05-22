//
//  CSVParser.swift
//  BrokerReportsApp
//
//  Парсер CSV файлов
//

import Foundation

/// Парсер CSV файлов
public actor CSVParser {
    
    /// Разделители для определения формата CSV
    private let possibleDelimiters: [Character] = [",", ";", "\t", "|"]
    
    /// Кодировки для попытки чтения
    private let encodings: [String.Encoding] = [.utf8, .windowsCP1251, .isoLatin1, .macOSRoman]
    
    /// Маппинг колонок (аналогично ExcelParser)
    private let dateColumns = ["Дата создания", "Дата исполнения", "Дата сделки", "Дата", "Date", "Trade Date"]
    private let typeColumns = ["Операция", "Тип операции", "Вид операции", "Operation", "Type"]
    private let tickerColumns = ["Код инструмента", "Тикер", "Инструмент", "Ticker", "Symbol", "Instrument"]
    private let nameColumns = ["Название инструмента", "Наименование", "Name", "Description"]
    private let quantityColumns = ["Количество", "Кол-во", "Qty", "Quantity", "Shares"]
    private let priceColumns = ["Цена", "Цена сделки", "Price", "Trade Price"]
    private let amountColumns = ["Сумма", "Сумма сделки", "Amount", "Total", "Value"]
    private let commissionColumns = ["Комиссия", "Commission", "Fee"]
    private let currencyColumns = ["Валюта", "Currency", "CCY"]
    private let statusColumns = ["Статус", "Status", "Состояние"]
    
    /// Парсинг файла
    public func parse(fileURL: URL) async throws -> [Transaction] {
        guard fileURL.isFileURL else {
            throw ParserError.invalidURL
        }
        
        let ext = fileURL.pathExtension.lowercased()
        guard ext == "csv" else {
            throw ParserError.unsupportedFormat(ext)
        }
        
        print("📊 Начало парсинга CSV: \(fileURL.lastPathComponent)")
        
        var transactions: [Transaction] = []
        
        // Попытка чтения с разными кодировками
        var content: String?
        var usedEncoding: String.Encoding = .utf8
        
        for encoding in encodings {
            do {
                content = try String(contentsOf: fileURL, encoding: encoding)
                usedEncoding = encoding
                break
            } catch {
                continue
            }
        }
        
        guard let csvContent = content else {
            throw ParserError.readError("Не удалось прочитать файл в поддерживаемых кодировках")
        }
        
        print("📝 Кодировка файла: \(usedEncoding)")
        
        // Определение разделителя
        let delimiter = detectDelimiter(content: csvContent)
        print("🔸 Разделитель: '\(delimiter)'")
        
        // Парсинг строк
        let lines = csvContent.components(separatedBy: .newlines)
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }
        
        guard lines.count > 1 else {
            throw ParserError.emptyFile
        }
        
        // Парсинг заголовков
        let headers = parseLine(lines[0], delimiter: delimiter)
        print("📋 Заголовки: \(headers)")
        
        // Поиск индексов колонок
        let dateIndex = findColumnIndex(headers: headers, possibleNames: dateColumns)
        let typeIndex = findColumnIndex(headers: headers, possibleNames: typeColumns)
        let tickerIndex = findColumnIndex(headers: headers, possibleNames: tickerColumns)
        let nameIndex = findColumnIndex(headers: headers, possibleNames: nameColumns)
        let quantityIndex = findColumnIndex(headers: headers, possibleNames: quantityColumns)
        let priceIndex = findColumnIndex(headers: headers, possibleNames: priceColumns)
        let amountIndex = findColumnIndex(headers: headers, possibleNames: amountColumns)
        let commissionIndex = findColumnIndex(headers: headers, possibleNames: commissionColumns)
        let currencyIndex = findColumnIndex(headers: headers, possibleNames: currencyColumns)
        let statusIndex = findColumnIndex(headers: headers, possibleNames: statusColumns)
        
        // Проверка обязательных колонок
        guard dateIndex != nil && typeIndex != nil else {
            throw ParserError.parseError("Не найдены обязательные колонки: Дата, Операция")
        }
        
        // Парсинг данных
        for (lineNum, line) in lines.enumerated().dropFirst() {
            let columns = parseLine(line, delimiter: delimiter)
            
            guard columns.count >= headers.count else {
                print("⚠️ Пропущена строка \(lineNum): недостаточно колонок")
                continue
            }
            
            do {
                if let transaction = try parseTransaction(
                    columns: columns,
                    dateIndex: dateIndex!,
                    typeIndex: typeIndex!,
                    tickerIndex: tickerIndex,
                    nameIndex: nameIndex,
                    quantityIndex: quantityIndex,
                    priceIndex: priceIndex,
                    amountIndex: amountIndex,
                    commissionIndex: commissionIndex,
                    currencyIndex: currencyIndex,
                    statusIndex: statusIndex,
                    sourceFile: fileURL.lastPathComponent
                ) {
                    transactions.append(transaction)
                }
            } catch {
                print("⚠️ Ошибка парсинга строки \(lineNum): \(error)")
                continue
            }
        }
        
        print("✅ Распарсено транзакций: \(transactions.count)")
        return transactions
    }
    
    /// Определение разделителя
    private func detectDelimiter(content: String) -> Character {
        let firstLines = content.components(separatedBy: .newlines).prefix(5)
        
        var bestDelimiter: Character = ","
        var maxCount = 0
        
        for delimiter in possibleDelimiters {
            let counts = firstLines.map { line in
                line.filter { $0 == delimiter }.count
            }
            
            // Ищем разделитель с наиболее стабильным количеством
            if counts.count > 1, counts.allSatisfy({ $0 > 0 }) {
                let avg = counts.reduce(0, +) / counts.count
                let variance = counts.map { abs($0 - avg) }.reduce(0, +)
                
                if variance < maxCount || maxCount == 0 {
                    bestDelimiter = delimiter
                    maxCount = variance
                }
            }
        }
        
        return bestDelimiter
    }
    
    /// Парсинг строки CSV с учётом кавычек
    private func parseLine(_ line: String, delimiter: Character) -> [String] {
        var columns: [String] = []
        var currentColumn = ""
        var insideQuotes = false
        
        for character in line {
            switch character {
            case "\"" where insideQuotes:
                insideQuotes = false
            case "\"":
                insideQuotes = true
            case delimiter where !insideQuotes:
                columns.append(currentColumn.trimmingCharacters(in: .whitespaces))
                currentColumn = ""
            default:
                currentColumn.append(character)
            }
        }
        
        columns.append(currentColumn.trimmingCharacters(in: .whitespaces))
        return columns
    }
    
    /// Поиск индекса колонки
    private func findColumnIndex(headers: [String], possibleNames: [String]) -> Int? {
        for (index, header) in headers.enumerated() {
            let normalized = header.trimmingCharacters(in: .whitespacesAndQuotes).lowercased()
            for name in possibleNames {
                if normalized.contains(name.lowercased()) {
                    return index
                }
            }
        }
        return nil
    }
    
    /// Парсинг транзакции из строки
    private func parseTransaction(
        columns: [String],
        dateIndex: Int,
        typeIndex: Int,
        tickerIndex: Int?,
        nameIndex: Int?,
        quantityIndex: Int?,
        priceIndex: Int?,
        amountIndex: Int?,
        commissionIndex: Int?,
        currencyIndex: Int?,
        statusIndex: Int?,
        sourceFile: String
    ) throws -> Transaction? {
        
        // Парсинг даты
        let dateString = columns[safe: dateIndex]?.trimmingCharacters(in: .whitespacesAndQuotes) ?? ""
        guard let date = parseDate(dateString) else {
            return nil // Пропускаем строки с некорректной датой
        }
        
        // Парсинг типа операции
        let typeString = columns[safe: typeIndex]?.trimmingCharacters(in: .whitespacesAndQuotes) ?? ""
        let type = parseTransactionType(typeString)
        
        // Проверка статуса
        if let statusIndex = statusIndex {
            let statusString = columns[safe: statusIndex]?.trimmingCharacters(in: .whitespacesAndQuotes) ?? ""
            let status = parseTransactionStatus(statusString)
            
            // Игнорируем отменённые операции
            if !TransactionStatus.validForCalculation.contains(status) {
                return nil
            }
        }
        
        // Парсинг тикера
        let ticker = columns[safe: tickerIndex]?.trimmingCharacters(in: .whitespacesAndQuotes) ?? "UNKNOWN"
        
        // Парсинг названия
        let name = columns[safe: nameIndex]?.trimmingCharacters(in: .whitespacesAndQuotes) ?? ""
        
        // Парсинг количества
        let quantityStr = columns[safe: quantityIndex]?.trimmingCharacters(in: .whitespacesAndQuotes) ?? "0"
        let quantity = parseNumber(quantityStr) ?? 0
        
        // Парсинг цены
        let priceStr = columns[safe: priceIndex]?.trimmingCharacters(in: .whitespacesAndQuotes) ?? "0"
        let price = parseNumber(priceStr) ?? 0
        
        // Парсинг суммы
        let amountStr = columns[safe: amountIndex]?.trimmingCharacters(in: .whitespacesAndQuotes) ?? "0"
        let amount = parseNumber(amountStr) ?? 0
        
        // Парсинг комиссии
        let commissionStr = columns[safe: commissionIndex]?.trimmingCharacters(in: .whitespacesAndQuotes) ?? "0"
        let commission = parseNumber(commissionStr) ?? 0
        
        // Парсинг валюты
        let currency = columns[safe: currencyIndex]?.trimmingCharacters(in: .whitespacesAndQuotes) ?? "RUB"
        
        return Transaction(
            id: UUID().uuidString,
            date: date,
            ticker: ticker,
            name: name,
            type: type,
            quantity: quantity,
            price: price,
            amount: amount,
            currency: currency.uppercased(),
            commission: commission,
            accruedInterest: 0,
            status: .executed,
            sourceFile: sourceFile
        )
    }
    
    /// Определение типа транзакции по строке
    private func parseTransactionType(_ string: String) -> TransactionType {
        let lower = string.lowercased()
        
        if lower.contains("покупк") || lower.contains("buy") { return .buy }
        if lower.contains("продаж") || lower.contains("sell") { return .sell }
        if lower.contains("дивиденд") || lower.contains("dividend") { return .dividend }
        if lower.contains("купон") || lower.contains("coupon") { return .coupon }
        if lower.contains("пополнен") || lower.contains("deposit") { return .deposit }
        if lower.contains("вывод") || lower.contains("withdraw") { return .withdrawal }
        if lower.contains("комисс") || lower.contains("commission") || lower.contains("fee") { return .commission }
        if lower.contains("налог") || lower.contains("tax") { return .tax }
        if lower.contains("марж") || lower.contains("margin") { return .marginCall }
        
        return .unknown
    }
    
    /// Определение статуса транзакции
    private func parseTransactionStatus(_ string: String) -> TransactionStatus {
        let lower = string.lowercased()
        
        if lower.contains("исполнен") || lower.contains("executed") || lower.contains("done") { return .executed }
        if lower.contains("частичн") || lower.contains("partial") { return .partiallyExecuted }
        if lower.contains("отмен") || lower.contains("cancel") { return .cancelled }
        if lower.contains("отклон") || lower.contains("declin") { return .declined }
        if lower.contains("ожид") || lower.contains("pending") { return .pending }
        
        return .executed // По умолчанию считаем исполненной
    }
    
    /// Парсинг даты
    private func parseDate(_ string: String) -> Date? {
        let formatters: [DateFormatter] = [
            createFormatter("dd.MM.yyyy"),
            createFormatter("yyyy-MM-dd"),
            createFormatter("dd/MM/yyyy"),
            createFormatter("MM/dd/yyyy"),
            createFormatter("dd.MM.yyyy HH:mm:ss"),
            createFormatter("yyyy-MM-dd'T'HH:mm:ss"),
            createFormatter("dd.MM.yy"),
            createFormatter("MM.dd.yyyy")
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
        formatter.timeZone = TimeZone(identifier: "Europe/Moscow")
        return formatter
    }
    
    /// Парсинг числа
    private func parseNumber(_ string: String) -> Double? {
        let cleaned = string
            .replacingOccurrences(of: " ", with: "")
            .replacingOccurrences(of: ",", with: ".")
            .trimmingCharacters(in: .whitespaces)
        
        // Убираем возможные символы валют
        let pattern = "[^0-9.\\-]"
        let filtered = cleaned.components(separatedBy: CharacterSet(charactersIn: pattern)).joined()
        
        return Double(filtered)
    }
}

// MARK: - Array Extension

extension Array {
    subscript(safe index: Index) -> Element? {
        indices.contains(index) ? self[index] : nil
    }
}

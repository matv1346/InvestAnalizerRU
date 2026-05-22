//
//  OFXParser.swift
//  BrokerReportsApp
//
//  Парсер файлов формата OFX (Open Financial Exchange)
//

import Foundation

/// Парсер OFX файлов
public actor OFXParser {
    
    /// Парсинг файла
    public func parse(fileURL: URL) async throws -> [Transaction] {
        guard fileURL.isFileURL else {
            throw ParserError.invalidURL
        }
        
        let ext = fileURL.pathExtension.lowercased()
        guard ext == "ofx" || ext == "qfx" else {
            throw ParserError.unsupportedFormat(ext)
        }
        
        print("📊 Начало парсинга OFX: \(fileURL.lastPathComponent)")
        
        var transactions: [Transaction] = []
        
        do {
            let content = try String(contentsOf: fileURL, encoding: .utf8)
            transactions = parseOFXContent(content, fileName: fileURL.lastPathComponent)
        } catch {
            // Пробуем другие кодировки
            let encodings: [String.Encoding] = [.windowsCP1251, .isoLatin1]
            for encoding in encodings {
                if let content = try? String(contentsOf: fileURL, encoding: encoding) {
                    transactions = parseOFXContent(content, fileName: fileURL.lastPathComponent)
                    break
                }
            }
            
            if transactions.isEmpty {
                throw ParserError.readError("Не удалось прочитать файл OFX")
            }
        }
        
        print("✅ Распарсено транзакций OFX: \(transactions.count)")
        return transactions
    }
    
    /// Парсинг содержимого OFX
    private func parseOFXContent(_ content: String, fileName: String) -> [Transaction] {
        var transactions: [Transaction] = []
        
        // OFX может быть в SGML или XML формате
        let isXML = content.contains("<?xml")
        
        if isXML {
            transactions = parseXMLBasedOFX(content, fileName: fileName)
        } else {
            transactions = parseSGMLBasedOFX(content, fileName: fileName)
        }
        
        return transactions
    }
    
    /// Парсинг XML-based OFX
    private func parseXMLBasedOFX(_ content: String, fileName: String) -> [Transaction] {
        var transactions: [Transaction] = []
        
        // Простой парсинг тегов OFX
        let lines = content.components(separatedBy: .newlines)
        
        var currentTransaction: [String: String]?
        
        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            
            // Начало транзакции
            if trimmed == "<STMTTRN>" {
                currentTransaction = [:]
                continue
            }
            
            // Конец транзакции
            if trimmed == "</STMTTRN>", let tx = currentTransaction {
                if let transaction = buildTransaction(from: tx, fileName: fileName) {
                    transactions.append(transaction)
                }
                currentTransaction = nil
                continue
            }
            
            // Парсинг полей
            if currentTransaction != nil {
                parseOFXTag(trimmed, into: &currentTransaction!)
            }
        }
        
        return transactions
    }
    
    /// Парсинг SGML-based OFX
    private func parseSGMLBasedOFX(_ content: String, fileName: String) -> [Transaction] {
        var transactions: [Transaction] = []
        
        let lines = content.components(separatedBy: .newlines)
        var currentTransaction: [String: String]?
        
        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            
            // OFX теги начинаются с < и не имеют закрывающего тега в SGML
            if trimmed.hasPrefix("<DTPOSTED>") || trimmed.hasPrefix("<TRNTYPE>") {
                if currentTransaction == nil {
                    currentTransaction = [:]
                }
                parseOFXTag(trimmed, into: &currentTransaction!)
            }
            
            // Конец транзакции определяется по следующему DTPOSTED или STMTTRN
            if trimmed.hasPrefix("<STMTTRN>") {
                if let tx = currentTransaction {
                    if let transaction = buildTransaction(from: tx, fileName: fileName) {
                        transactions.append(transaction)
                    }
                }
                currentTransaction = [:]
            }
        }
        
        // Последняя транзакция
        if let tx = currentTransaction {
            if let transaction = buildTransaction(from: tx, fileName: fileName) {
                transactions.append(transaction)
            }
        }
        
        return transactions
    }
    
    /// Парсинг OFX тега
    private func parseOFXTag(_ tag: String, into dictionary: inout [String: String]) {
        guard tag.hasPrefix("<") else { return }
        
        // Извлекаем имя тега и значение
        let tagNameEndIndex = tag.firstIndex(of: ">") ?? tag.endIndex
        let tagName = String(tag[tag.index(after: tag.startIndex)..<tagNameEndIndex])
        
        // Значение может быть после тега или в следующем тексте
        let valueStartIndex = tag.index(after: tagNameEndIndex)
        if valueStartIndex < tag.endIndex {
            let value = String(tag[valueStartIndex...]).trimmingCharacters(in: .whitespaces)
            dictionary[tagName] = value
        }
    }
    
    /// Построение транзакции из OFX данных
    private func buildTransaction(from data: [String: String], fileName: String) -> Transaction? {
        // OFX поля
        guard let dateStr = data["DTPOSTED"] ?? data["DTTRADE"] else {
            return nil
        }
        
        let typeStr = data["TRNTYPE"] ?? ""
        let amountStr = data["TRNAMT"] ?? "0"
        let name = data["NAME"] ?? data["MEMO"] ?? ""
        let fitID = data["FITID"] ?? UUID().uuidString
        
        // Парсинг даты OFX формата (YYYYMMDDHHMMSS)
        guard let date = parseOFXDate(dateStr) else {
            return nil
        }
        
        // Определение типа
        let type = mapOFXType(typeStr)
        
        // Парсинг суммы
        let amount = Double(amountStr.replacingOccurrences(of: ",", with: ".")) ?? 0
        
        // Тикер (если есть)
        let ticker = data["SYMBOL"] ?? data["SECNAME"]?.prefix(10).description ?? "UNKNOWN"
        
        return Transaction(
            id: fitID,
            date: date,
            ticker: ticker,
            name: name,
            type: type,
            quantity: 1, // OFX обычно не указывает количество для денежных операций
            price: abs(amount),
            amount: amount,
            currency: data["CURRENCY"] ?? "RUB",
            commission: 0,
            accruedInterest: 0,
            status: .executed,
            sourceFile: fileName
        )
    }
    
    /// Парсинг даты OFX
    private func parseOFXDate(_ string: String) -> Date? {
        // Формат: YYYYMMDDHHMMSS или YYYYMMDD
        let formatters: [DateFormatter] = [
            createFormatter("yyyyMMddHHmmss"),
            createFormatter("yyyyMMdd"),
            createFormatter("yyyyMMddHHmmss[-z]"), // С таймзоной
            createFormatter("yyyyMMddHHmmss.XXX")
        ]
        
        // Очищаем строку от таймзоны если есть
        let cleanString = string.components(separatedBy: "[")[0]
            .components(separatedBy: ".")[0]
        
        for formatter in formatters {
            if let date = formatter.date(from: cleanString) {
                return date
            }
        }
        
        return nil
    }
    
    private func createFormatter(_ format: String) -> DateFormatter {
        let formatter = DateFormatter()
        formatter.dateFormat = format
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        return formatter
    }
    
    /// Маппинг типов OFX
    private func mapOFXType(_ type: String) -> TransactionType {
        switch type.uppercased() {
        case "BUY", "BUYOPT":
            return .buy
        case "SELL", "SELLOPT":
            return .sell
        case "DIV":
            return .dividend
        case "INTR":
            return .coupon
        case "DEP":
            return .deposit
        case "REF":
            return .withdrawal
        case "FEE", "SRVCHG":
            return .commission
        case "TAX":
            return .tax
        default:
            return .unknown
        }
    }
}

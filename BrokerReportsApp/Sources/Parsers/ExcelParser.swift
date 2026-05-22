//
//  ExcelParser.swift
//  BrokerReportsApp
//
//  Парсер XLSX файлов с использованием CoreXLSX логики
//

import Foundation
import AppKit

/// Парсер Excel файлов (.xlsx)
public actor ExcelParser {
    
    /// Ключевые слова для определения типа брокера/структуры
    private let tinkoffKeywords = ["Тинькофф", "Tinkoff", "tininvest"]
    private let vtbKeywords = ["ВТБ", "VTB", "vtb.ru"]
    private let sbertKeywords = ["Сбер", "Sber", "sberbank"]
    private let genericKeywords = ["Дата", "Операция", "Инструмент", "Количество", "Цена"]
    
    /// Маппинг возможных названий колонок
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
        
        // Проверка расширения
        let ext = fileURL.pathExtension.lowercased()
        guard ["xlsx", "xls"].contains(ext) else {
            throw ParserError.unsupportedFormat(ext)
        }
        
        print("📊 Начало парсинга XLSX: \(fileURL.lastPathComponent)")
        
        // В реальной реализации здесь используется CoreXLSX
        // Для демонстрации - эмуляция структуры
        var transactions: [Transaction] = []
        
        do {
            // Попытка прочитать файл как XLSX
            let data = try Data(contentsOf: fileURL)
            
            // Простейшая проверка на валидность XLSX (ZIP архив)
            if !isValidXLSX(data: data) {
                throw ParserError.invalidFile("Файл не является корректным XLSX")
            }
            
            // Здесь должна быть логика парсинга через CoreXLSX
            // Поскольку CoreXLSX требует добавления в Package.swift,
            // реализуем базовый парсер для CSV внутри XLSX или заглушку
            
            transactions = try await parseXLSXContent(data: data, fileName: fileURL.lastPathComponent)
            
        } catch let error as ParserError {
            throw error
        } catch {
            throw ParserError.readError(error.localizedDescription)
        }
        
        print("✅ Распарсено транзакций: \(transactions.count)")
        return transactions
    }
    
    /// Проверка валидности XLSX файла
    private func isValidXLSX(data: Data) -> Bool {
        // XLSX это ZIP архив, начинается с PK
        return data.count > 4 && data[0...3] == Data([0x50, 0x4B, 0x03, 0x04])
    }
    
    /// Парсинг содержимого XLSX
    private func parseXLSXContent(data: Data, fileName: String) async throws -> [Transaction] {
        // Эмуляция парсинга - в продакшене использовать CoreXLSX
        // Пример: https://github.com/CoreOffice/CoreXLSX
        
        /*
         Реальная реализация:
         
         let file = try XLSXFile(filepath: fileURL.path)
         for wbk in file.parseWorkbooks() {
             for sheet in wbk.sheets {
                 // Парсинг строк
             }
         }
         */
        
        // Возвращаем пустой массив с предупреждением
        print("⚠️ Для полноценного парсинга XLSX добавьте CoreXLSX через SPM")
        return []
    }
    
    /// Определение брокера по ключевым словам
    public func detectBroker(data: Data, fileName: String) -> String? {
        // Пробуем найти ключевые слова в бинарных данных
        let possibleStrings = String(data: data, encoding: .utf8) ?? ""
        
        for keyword in tinkoffKeywords {
            if possibleStrings.contains(keyword) {
                return "Тинькофф Инвестиции"
            }
        }
        
        for keyword in vtbKeywords {
            if possibleStrings.contains(keyword) {
                return "ВТБ Мои Инвестиции"
            }
        }
        
        for keyword in sbertKeywords {
            if possibleStrings.contains(keyword) {
                return "СберБанк Инвестор"
            }
        }
        
        return nil
    }
    
    /// Поиск колонки по возможным названиям
    private func findColumnIndex(headers: [String], possibleNames: [String]) -> Int? {
        for (index, header) in headers.enumerated() {
            let normalized = header.trimmingCharacters(in: .whitespaces).lowercased()
            for name in possibleNames {
                if normalized.contains(name.lowercased()) {
                    return index
                }
            }
        }
        return nil
    }
    
    /// Парсинг даты из строки
    private func parseDate(_ string: String) -> Date? {
        let formatters: [DateFormatter] = [
            createFormatter("dd.MM.yyyy"),
            createFormatter("yyyy-MM-dd"),
            createFormatter("dd/MM/yyyy"),
            createFormatter("MM/dd/yyyy"),
            createFormatter("dd.MM.yyyy HH:mm:ss"),
            createFormatter("yyyy-MM-dd'T'HH:mm:ss")
        ]
        
        for formatter in formatters {
            if let date = formatter.date(from: string.trimmingCharacters(in: .whitespaces)) {
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
    
    /// Парсинг числа из строки
    private func parseNumber(_ string: String) -> Double? {
        let cleaned = string
            .replacingOccurrences(of: " ", with: "")
            .replacingOccurrences(of: ",", with: ".")
            .trimmingCharacters(in: .whitespaces)
        return Double(cleaned)
    }
}

// MARK: - Parser Error

public enum ParserError: LocalizedError {
    case invalidURL
    case unsupportedFormat(String)
    case invalidFile(String)
    case readError(String)
    case parseError(String)
    case emptyFile
    
    public var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Некорректный URL файла"
        case .unsupportedFormat(let ext):
            return "Неподдерживаемый формат: .\(ext)"
        case .invalidFile(let msg):
            return "Некорректный файл: \(msg)"
        case .readError(let msg):
            return "Ошибка чтения: \(msg)"
        case .parseError(let msg):
            return "Ошибка парсинга: \(msg)"
        case .emptyFile:
            return "Файл пуст или не содержит данных"
        }
    }
}

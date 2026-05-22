//
//  PDFReportGenerator.swift
//  BrokerReportsApp
//
//  Генератор PDF отчётов с использованием PDFKit и CoreGraphics
//

import Foundation
import PDFKit
import CoreGraphics
import AppKit

/// Генератор PDF отчётов
public actor PDFReportGenerator {
    
    /// Настройки генерации
    public struct GenerationSettings {
        public var pageSize: CGSize = CGSize(width: 595, height: 842) // A4
        public var margins: CGFloat = 40
        public var fontName: String = "Helvetica"
        public var titleFontSize: CGFloat = 18
        public var headerFontSize: CGFloat = 14
        public var bodyFontSize: CGFloat = 10
        public var captionFontSize: CGFloat = 8
        
        public init() {}
    }
    
    private let settings: GenerationSettings
    
    public init(settings: GenerationSettings = GenerationSettings()) {
        self.settings = settings
    }
    
    /// Генерация отчёта
    public func generate(
        metrics: PortfolioMetrics,
        positions: [PortfolioPosition],
        transactions: [Transaction],
        dividendsByMonth: [(month: String, amount: Double)],
        couponsByMonth: [(month: String, amount: Double)],
        outputFileURL: URL
    ) async throws -> URL {
        print("📄 Начало генерации PDF отчёта...")
        
        guard let pdfData = createPDFData(
            metrics: metrics,
            positions: positions,
            transactions: transactions,
            dividendsByMonth: dividendsByMonth,
            couponsByMonth: couponsByMonth
        ) else {
            throw GeneratorError.generationFailed("Не удалось создать PDF данные")
        }
        
        try pdfData.write(to: outputFileURL)
        
        print("✅ PDF отчёт сохранён: \(outputFileURL.path)")
        return outputFileURL
    }
    
    private func createPDFData(
        metrics: PortfolioMetrics,
        positions: [PortfolioPosition],
        transactions: [Transaction],
        dividendsByMonth: [(month: String, amount: Double)],
        couponsByMonth: [(month: String, amount: Double)]
    ) -> Data? {
        let pdfData = NSMutableData()
        guard let consumer = CGDataConsumer(data: pdfData as CFMutableData) else {
            return nil
        }
        
        var mediaBox = CGRect(origin: .zero, size: settings.pageSize)
        
        guard let context = CGContext(consumer: consumer, idInfo: nil) else {
            return nil
        }
        
        context.beginPDFPage(mediaBox as CFDictionary)
        generateTitlePage(context: context, metrics: metrics)
        context.endPDFPage()
        
        context.beginPDFPage(mediaBox as CFDictionary)
        generateSummaryPage(context: context, metrics: metrics)
        context.endPDFPage()
        
        context.beginPDFPage(mediaBox as CFDictionary)
        generatePositionsPage(context: context, positions: positions)
        context.endPDFPage()
        
        context.beginPDFPage(mediaBox as CFDictionary)
        generateTransactionsPage(context: context, transactions: transactions)
        context.endPDFPage()
        
        context.beginPDFPage(mediaBox as CFDictionary)
        generateDividendsPage(context: context, dividends: dividendsByMonth, coupons: couponsByMonth)
        context.endPDFPage()
        
        context.closePDF()
        
        return pdfData as Data
    }
    
    private func generateTitlePage(context: CGContext, metrics: PortfolioMetrics) {
        let dateFormatter = DateFormatter()
        dateFormatter.dateStyle = .long
        
        drawCenteredText(context: context, text: "ИНВЕСТИЦИОННЫЙ ОТЧЁТ", y: 100, fontSize: settings.titleFontSize, bold: true)
        
        let periodText = "Период: \(dateFormatter.string(from: metrics.periodStart)) — \(dateFormatter.string(from: metrics.periodEnd))"
        drawCenteredText(context: context, text: periodText, y: 140, fontSize: settings.bodyFontSize)
        
        var yPos: CGFloat = 200
        drawKeyValueRow(context: context, key: "Общая стоимость:", value: formatCurrency(metrics.totalValue), y: &yPos)
        drawKeyValueRow(context: context, key: "P&L:", value: formatCurrency(metrics.totalPnL), y: &yPos, color: metrics.totalPnL >= 0 ? .green : .red)
        drawKeyValueRow(context: context, key: "ROI:", value: String(format: "%.2f%%", metrics.roi), y: &yPos)
    }
    
    private func generateSummaryPage(context: CGContext, metrics: PortfolioMetrics) {
        drawHeader(context: context, text: "СВОДКА ПО ПОРТФЕЛЮ")
        
        var yPos: CGFloat = 120
        drawSectionHeader(context: context, text: "Основные показатели", y: &yPos)
        
        let metricsData: [(String, String)] = [
            ("Оценка портфеля", formatCurrency(metrics.totalValue)),
            ("Себестоимость", formatCurrency(metrics.totalCost)),
            ("ROI", String(format: "%.2f%%", metrics.roi)),
            ("CAGR", String(format: "%.2f%%", metrics.cagr)),
            ("Макс. просадка", String(format: "%.2f%%", metrics.maxDrawdown)),
            ("Дивиденды", formatCurrency(metrics.totalDividends)),
            ("Купоны", formatCurrency(metrics.totalCoupons)),
            ("Комиссии", formatCurrency(metrics.totalCommissions))
        ]
        
        for (key, value) in metricsData {
            drawTableRow(context: context, columns: [key, value], y: &yPos)
        }
    }
    
    private func generatePositionsPage(context: CGContext, positions: [PortfolioPosition]) {
        drawHeader(context: context, text: "ПОЗИЦИИ ПОРТФЕЛЯ")
        
        var yPos: CGFloat = 100
        let headers = ["Тикер", "Кол-во", "Ср. цена", "Стоимость", "P&L"]
        drawTableHeader(context: context, columns: headers, y: &yPos)
        
        for position in positions.sorted(by: { $0.marketValue > $1.marketValue }).prefix(20) {
            let totalPnL = position.unrealizedPnL + position.realizedPnL
            let row = [
                position.ticker,
                String(format: "%.2f", position.quantity),
                formatCurrency(position.averagePrice),
                formatCurrency(position.marketValue),
                formatCurrency(totalPnL)
            ]
            drawTableRow(context: context, columns: row, y: &yPos, textColor: totalPnL >= 0 ? .black : .red)
        }
    }
    
    private func generateTransactionsPage(context: CGContext, transactions: [Transaction]) {
        drawHeader(context: context, text: "ИСТОРИЯ ТРАНЗАКЦИЙ")
        
        var yPos: CGFloat = 100
        let headers = ["Дата", "Тикер", "Тип", "Кол-во", "Сумма"]
        drawTableHeader(context: context, columns: headers, y: &yPos)
        
        let dateFormatter = DateFormatter()
        dateFormatter.dateFormat = "dd.MM.yyyy"
        
        for tx in transactions.sorted(by: { $0.date > $1.date }).prefix(30) {
            let row = [
                dateFormatter.string(from: tx.date),
                tx.ticker,
                tx.type.displayValue,
                String(format: "%.2f", tx.quantity),
                formatCurrency(tx.amount)
            ]
            drawTableRow(context: context, columns: row, y: &yPos)
        }
    }
    
    private func generateDividendsPage(context: CGContext, dividends: [(month: String, amount: Double)], coupons: [(month: String, amount: Double)]) {
        drawHeader(context: context, text: "ДИВИДЕНДЫ И КУПОНЫ")
        
        var yPos: CGFloat = 100
        drawSectionHeader(context: context, text: "Дивиденды по месяцам", y: &yPos)
        
        if dividends.isEmpty {
            drawText(context: context, text: "Нет данных", x: settings.margins, y: yPos, fontSize: settings.bodyFontSize)
            yPos += 20
        } else {
            for (month, amount) in dividends {
                drawTableRow(context: context, columns: [month, formatCurrency(amount)], y: &yPos)
            }
        }
        
        yPos += 20
        drawSectionHeader(context: context, text: "Купоны по месяцам", y: &yPos)
        
        if coupons.isEmpty {
            drawText(context: context, text: "Нет данных", x: settings.margins, y: yPos, fontSize: settings.bodyFontSize)
        } else {
            for (month, amount) in coupons {
                drawTableRow(context: context, columns: [month, formatCurrency(amount)], y: &yPos)
            }
        }
    }
    
    // MARK: - Drawing Helpers
    
    private func drawHeader(context: CGContext, text: String) {
        drawCenteredText(context: context, text: text, y: 50, fontSize: settings.headerFontSize, bold: true)
        context.setStrokeColor(CGColor(red: 0.2, green: 0.2, blue: 0.2, alpha: 1))
        context.setLineWidth(1)
        context.move(to: CGPoint(x: settings.margins, y: 75))
        context.addLine(to: CGPoint(x: settings.pageSize.width - settings.margins, y: 75))
        context.strokePath()
    }
    
    private func drawText(context: CGContext, text: String, x: CGFloat, y: CGFloat, fontSize: CGFloat, bold: Bool = false, color: NSColor = .black) {
        let attributes: [NSAttributedString.Key: Any] = [
            .font: bold ? NSFont.boldSystemFont(ofSize: fontSize) : NSFont.systemFont(ofSize: fontSize),
            .foregroundColor: color
        ]
        
        let attributedString = NSAttributedString(string: text, attributes: attributes)
        
        context.saveGState()
        context.translateBy(x: 0, y: settings.pageSize.height)
        context.scaleBy(x: 1, y: -1)
        attributedString.draw(at: CGPoint(x: x, y: settings.pageSize.height - y - fontSize))
        context.restoreGState()
    }
    
    private func drawCenteredText(context: CGContext, text: String, y: CGFloat, fontSize: CGFloat, bold: Bool = false) {
        let attributes: [NSAttributedString.Key: Any] = [
            .font: bold ? NSFont.boldSystemFont(ofSize: fontSize) : NSFont.systemFont(ofSize: fontSize)
        ]
        let attributedString = NSAttributedString(string: text, attributes: attributes)
        let textSize = attributedString.size()
        let x = (settings.pageSize.width - textSize.width) / 2
        drawText(context: context, text: text, x: x, y: y, fontSize: fontSize, bold: bold)
    }
    
    private func drawKeyValueRow(context: CGContext, key: String, value: String, y: inout CGFloat, color: NSColor = .black, bold: Bool = false) {
        drawText(context: context, text: key, x: settings.margins, y: y, fontSize: settings.bodyFontSize, bold: bold)
        drawText(context: context, text: value, x: settings.pageSize.width - settings.margins - 100, y: y, fontSize: settings.bodyFontSize, bold: bold, color: color)
        y += 25
    }
    
    private func drawTableRow(context: CGContext, columns: [String], y: inout CGFloat, textColor: NSColor = .black) {
        let columnWidth = (settings.pageSize.width - 2 * settings.margins) / CGFloat(columns.count)
        for (index, column) in columns.enumerated() {
            let x = settings.margins + CGFloat(index) * columnWidth + 5
            drawText(context: context, text: column, x: x, y: y, fontSize: settings.bodyFontSize, color: textColor)
        }
        y += 20
    }
    
    private func drawTableHeader(context: CGContext, columns: [String], y: inout CGFloat) {
        let headerRect = CGRect(x: settings.margins, y: settings.pageSize.height - y - 20, width: settings.pageSize.width - 2 * settings.margins, height: 20)
        context.setFillColor(CGColor(red: 0.9, green: 0.9, blue: 0.9, alpha: 1))
        context.fill(headerRect)
        drawTableRow(context: context, columns: columns, y: &y, textColor: .black)
        y += 5
    }
    
    private func drawSectionHeader(context: CGContext, text: String, y: inout CGFloat) {
        drawText(context: context, text: text, x: settings.margins, y: y, fontSize: settings.bodyFontSize, bold: true)
        y += 25
    }
    
    private func formatCurrency(_ value: Double) -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .currency
        formatter.currencyCode = "RUB"
        formatter.locale = Locale(identifier: "ru_RU")
        return formatter.string(from: NSNumber(value: value)) ?? String(format: "%.2f ₽", value)
    }
}

public enum GeneratorError: LocalizedError {
    case generationFailed(String)
    
    public var errorDescription: String? {
        switch self {
        case .generationFailed(let msg):
            return "Ошибка генерации PDF: \(msg)"
        }
    }
}

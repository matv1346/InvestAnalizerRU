//
//  ReportsViewModel.swift
//  BrokerReportsApp
//
//  ViewModel для управления отчётами
//

import Foundation
import SwiftUI
import SwiftData
import UniformTypeIdentifiers

@MainActor
class ReportsViewModel: ObservableObject {
    @Published var files: [ParsedFile] = []
    @Published var transactions: [Transaction] = []
    @Published var positions: [PortfolioPosition] = []
    @Published var metrics: PortfolioMetrics?
    
    @Published var selectedFileID: String?
    @Published var isDraggingOver = false
    @Published var isProcessing = false
    @Published var progress: Double = 0
    @Published var statusMessage = ""
    
    // Настройки
    @AppStorage("maxFileSize") var maxFileSizeMB: Int = 50
    @AppStorage("defaultCurrency") var defaultCurrency: String = "RUB"
    @AppStorage("savePath") var savePath: String = "~/Downloads"
    
    // Парсеры
    private let csvParser = CSVParser()
    private let excelParser = ExcelParser()
    private let pdfParser = PDFTableParser()
    private let ofxParser = OFXParser()
    private let fifoEngine = FIFOEngine()
    private let metricsCalculator = MetricsCalculator()
    private let pdfGenerator = PDFReportGenerator()
    
    // MARK: - File Operations
    
    func showFilePicker() {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = true
        panel.canChooseDirectories = false
        panel.allowedContentTypes = [.xlsx, .csv, .pdf, .ofx]
        
        panel.begin { [weak self] response in
            guard response == .OK else { return }
            
            Task {
                await self?.processSelectedFiles(urls: panel.urls)
            }
        }
    }
    
    func handleDrop(providers: [NSItemProvider]) async {
        var urls: [URL] = []
        
        for provider in providers {
            if provider.hasItemConformingToTypeIdentifier(UTType.fileURL.identifier) {
                do {
                    let item = try await provider.loadItem(forTypeIdentifier: UTType.fileURL.identifier, options: nil)
                    if let data = item as? Data, let url = URL(dataRepresentation: data, relativeTo: nil) {
                        urls.append(url)
                    }
                } catch {
                    print("Ошибка загрузки файла: \(error)")
                }
            }
        }
        
        await processSelectedFiles(urls: urls)
    }
    
    private func processSelectedFiles(urls: [URL]) async {
        guard !urls.isEmpty else { return }
        
        isProcessing = true
        progress = 0
        
        for (index, url) in urls.enumerated() {
            let currentProgress = Double(index) / Double(urls.count) * 100
            progress = currentProgress
            statusMessage = "Обработка: \(url.lastPathComponent)"
            
            await processFile(url: url)
        }
        
        progress = 100
        statusMessage = "Готово"
        
        // После загрузки всех файлов - консолидация
        await consolidateData()
        
        isProcessing = false
    }
    
    private func processFile(url: URL) async {
        // Проверка размера
        do {
            let resources = try url.resourceValues(forKeys: [.fileSizeKey])
            if let fileSize = resources.fileSize, fileSize > maxFileSizeMB * 1024 * 1024 {
                let parsedFile = ParsedFile(
                    fileName: url.lastPathComponent,
                    filePath: url.path,
                    fileType: url.pathExtension,
                    fileSize: Int64(fileSize),
                    status: .error,
                    errorMessage: "Файл превышает лимит \(maxFileSizeMB) МБ"
                )
                files.append(parsedFile)
                return
            }
        } catch {
            print("Ошибка получения размера файла: \(error)")
        }
        
        // Создание записи о файле
        let parsedFile = ParsedFile(
            fileName: url.lastPathComponent,
            filePath: url.path,
            fileType: url.pathExtension,
            fileSize: getFileSize(url: url),
            status: .parsing
        )
        files.append(parsedFile)
        
        // Парсинг в зависимости от типа
        var fileTransactions: [Transaction] = []
        var brokerName: String?
        
        do {
            switch url.pathExtension.lowercased() {
            case "csv":
                fileTransactions = try await csvParser.parse(fileURL: url)
            case "xlsx", "xls":
                fileTransactions = try await excelParser.parse(fileURL: url)
            case "pdf":
                fileTransactions = try await pdfParser.parse(fileURL: url)
            case "ofx", "qfx":
                fileTransactions = try await ofxParser.parse(fileURL: url)
            default:
                throw ParserError.unsupportedFormat(url.pathExtension)
            }
            
            // Обновление статуса файла
            if let index = files.firstIndex(where: { $0.id == parsedFile.id }) {
                files[index].status = .success
                files[index].transactionCount = fileTransactions.count
                files[index].brokerName = brokerName
            }
            
        } catch {
            if let index = files.firstIndex(where: { $0.id == parsedFile.id }) {
                files[index].status = .error
                files[index].errorMessage = error.localizedDescription
            }
            print("Ошибка парсинга файла \(url.lastPathComponent): \(error)")
        }
    }
    
    private func getFileSize(url: URL) -> Int64 {
        do {
            let resources = try url.resourceValues(forKeys: [.fileSizeKey])
            return Int64(resources.fileSize ?? 0)
        } catch {
            return 0
        }
    }
    
    // MARK: - Data Consolidation
    
    private func consolidateData() async {
        statusMessage = "Консолидация данных..."
        
        // Сбор всех транзакций
        var allTransactions: [Transaction] = []
        for file in files where file.status == .success {
            // В реальной реализации здесь была бы загрузка из БД
        }
        
        // Дедупликация по хэшу
        var uniqueTransactions: [String: Transaction] = [:]
        for tx in allTransactions {
            uniqueTransactions[tx.hashKey] = tx
        }
        
        transactions = Array(uniqueTransactions.values).sorted { $0.date < $1.date }
        
        // FIFO расчёт
        statusMessage = "Расчёт позиций (FIFO)..."
        let fifoResult = await fifoEngine.calculatePositions(transactions: transactions)
        positions = fifoResult.positions
        
        // Расчёт метрик
        statusMessage = "Расчёт метрик..."
        let metricsResult = await metricsCalculator.calculate(
            transactions: transactions,
            positions: positions
        )
        metrics = metricsResult.metrics
        
        statusMessage = "Готово к генерации отчёта"
    }
    
    // MARK: - Report Generation
    
    func generateReport() async {
        guard let metrics = metrics else {
            showAlert(title: "Ошибка", message: "Сначала загрузите файлы отчётов")
            return
        }
        
        isProcessing = true
        progress = 0
        statusMessage = "Генерация PDF отчёта..."
        
        do {
            // Диалог сохранения
            let savePanel = NSSavePanel()
            savePanel.allowedContentTypes = [.pdf]
            savePanel.nameFieldStringValue = "Инвестиционный_отчёт_\(Date().formatted(.dateTime.year().month().day()))"
            savePanel.directoryURL = FileManager.default.urls(for: .downloadsDirectory, in: .userDomainMask).first
            
            guard savePanel.runModal() == .OK, let outputURL = savePanel.url else {
                isProcessing = false
                return
            }
            
            progress = 20
            statusMessage = "Создание PDF..."
            
            // Получение данных для отчёта
            let metricsResult = await metricsCalculator.calculate(
                transactions: transactions,
                positions: positions
            )
            
            progress = 50
            statusMessage = "Формирование страниц..."
            
            // Генерация PDF
            try await pdfGenerator.generate(
                metrics: metrics,
                positions: positions,
                transactions: transactions,
                dividendsByMonth: metricsResult.dividendsByMonth,
                couponsByMonth: metricsResult.couponsByMonth,
                outputFileURL: outputURL
            )
            
            progress = 100
            statusMessage = "Отчёт сохранён"
            
            // Открытие папки с файлом
            NSWorkspace.shared.selectFile(outputURL.path, inFileViewerRootedAtPath: outputURL.deletingLastPathComponent().path)
            
        } catch {
            showAlert(title: "Ошибка генерации", message: error.localizedDescription)
            statusMessage = "Ошибка: \(error.localizedDescription)"
        }
        
        isProcessing = false
    }
    
    // MARK: - Utility Methods
    
    func loadSavedFiles() async {
        // Загрузка сохранённых файлов из SwiftData
        // В полной реализации здесь был бы FetchDescriptor
    }
    
    func removeFile(_ file: ParsedFile) {
        files.removeAll { $0.id == file.id }
        // Также удалить транзакции этого файла
    }
    
    func clearAll() {
        files.removeAll()
        transactions.removeAll()
        positions.removeAll()
        metrics = nil
        progress = 0
        statusMessage = ""
    }
    
    private func showAlert(title: String, message: String) {
        let alert = NSAlert()
        alert.messageText = title
        alert.informativeText = message
        alert.alertStyle = .warning
        alert.runModal()
    }
}

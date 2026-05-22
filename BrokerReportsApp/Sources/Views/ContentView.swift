//
//  ContentView.swift
//  BrokerReportsApp
//
//  Главное окно приложения
//

import SwiftUI
import SwiftData
import UniformTypeIdentifiers

struct ContentView: View {
    @Environment(\.modelContext) private var modelContext
    @StateObject private var viewModel = ReportsViewModel()
    @State private var showingSettings = false
    @State private var showingAbout = false
    
    var body: some View {
        NavigationSplitView {
            // Sidebar - список файлов
            FileListView(viewModel: viewModel)
                .navigationTitle("Файлы отчётов")
                .toolbar {
                    ToolbarItem(placement: .primaryAction) {
                        Button(action: { viewModel.showFilePicker() }) {
                            Image(systemName: "plus")
                        }
                        .help("Добавить файлы")
                    }
                    
                    ToolbarItem(placement: .secondaryAction) {
                        Button(action: { viewModel.clearAll() }) {
                            Image(systemName: "trash")
                        }
                        .help("Очистить все")
                        .disabled(viewModel.files.isEmpty)
                    }
                }
        } detail: {
            // Main area - превью и настройки
            if viewModel.files.isEmpty {
                EmptyStateView(viewModel: viewModel)
            } else {
                MainDetailView(viewModel: viewModel)
            }
        }
        .frame(minWidth: 900, minHeight: 600)
        .sheet(isPresented: $showingSettings) {
            SettingsView()
        }
        .sheet(isPresented: $showingAbout) {
            AboutView()
        }
        .task {
            await viewModel.loadSavedFiles()
        }
    }
}

// MARK: - File List View

struct FileListView: View {
    @ObservedObject var viewModel: ReportsViewModel
    
    var body: some View {
        List(viewModel.files, id: \.id, selection: $viewModel.selectedFileID) { file in
            FileRowView(file: file)
                .contextMenu {
                    Button("Удалить", role: .destructive) {
                        viewModel.removeFile(file)
                    }
                }
        }
        .listStyle(.sidebar)
        .onDrop(of: [.fileURL], isTargeted: $viewModel.isDraggingOver) { providers in
            Task {
                await viewModel.handleDrop(providers: providers)
            }
            return true
        }
    }
}

struct FileRowView: View {
    let file: ParsedFile
    
    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: file.fileIcon)
                .foregroundColor(.accentColor)
                .font(.title3)
            
            VStack(alignment: .leading, spacing: 4) {
                Text(file.fileName)
                    .font(.system(.body, design: .default))
                    .lineLimit(1)
                
                HStack {
                    Text(file.formattedFileSize)
                        .font(.caption)
                        .foregroundColor(.secondary)
                    
                    Text("•")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    
                    statusBadge
                }
            }
            
            Spacer()
            
            if file.status == .error {
                Image(systemName: "exclamationmark.triangle.fill")
                    .foregroundColor(.red)
                    .font(.caption)
            }
        }
        .padding(.vertical, 4)
    }
    
    private var statusBadge: some View {
        Group {
            switch file.status {
            case .pending:
                Label("Ожидает", systemImage: "clock.fill")
            case .parsing:
                Label("Обработка", systemImage: "arrow.triangle.2.circlepath")
            case .success:
                Label("Готов", systemImage: "checkmark.circle.fill")
            case .error:
                Label("Ошибка", systemImage: "xmark.circle.fill")
            }
        }
        .font(.caption2)
        .foregroundColor(statusColor)
    }
    
    private var statusColor: Color {
        switch file.status {
        case .pending: return .orange
        case .parsing: return .blue
        case .success: return .green
        case .error: return .red
        }
    }
}

// MARK: - Empty State View

struct EmptyStateView: View {
    @ObservedObject var viewModel: ReportsViewModel
    
    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "doc.badge.plus")
                .font(.system(size: 80))
                .foregroundColor(.secondary)
            
            Text("Перетащите файлы отчётов сюда")
                .font(.title2)
                .fontWeight(.medium)
            
            Text("Поддерживаются форматы: XLSX, CSV, PDF, OFX")
                .font(.body)
                .foregroundColor(.secondary)
            
            Button("Выбрать файлы") {
                viewModel.showFilePicker()
            }
            .buttonStyle(.borderedProminent)
            .padding(.top, 10)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .onDrop(of: [.fileURL], isTargeted: $viewModel.isDraggingOver) { providers in
            Task {
                await viewModel.handleDrop(providers: providers)
            }
            return true
        }
    }
}

// MARK: - Main Detail View

struct MainDetailView: View {
    @ObservedObject var viewModel: ReportsViewModel
    @State private var showingProgress = false
    
    var body: some View {
        VStack(spacing: 0) {
            // Прогресс бар
            if viewModel.isProcessing {
                ProgressView(value: viewModel.progress, total: 100)
                    .progressViewStyle(.linear)
                    .padding(.horizontal)
                
                Text(viewModel.statusMessage)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .padding(.bottom, 8)
            }
            
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    // Статистика файлов
                    FilesSummaryView(files: viewModel.files)
                    
                    Divider()
                    
                    // Предварительный просмотр данных
                    if !viewModel.transactions.isEmpty {
                        PreviewPane(transactions: viewModel.transactions, positions: viewModel.positions)
                    }
                }
                .padding()
            }
            
            Divider()
            
            // Панель действий
            HStack {
                Text("Всего транзакций: \(viewModel.transactions.count)")
                    .font(.caption)
                    .foregroundColor(.secondary)
                
                Spacer()
                
                Button("Сгенерировать отчёт") {
                    Task {
                        await viewModel.generateReport()
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(viewModel.isProcessing || viewModel.transactions.isEmpty)
            }
            .padding()
        }
    }
}

// MARK: - Files Summary View

struct FilesSummaryView: View {
    let files: [ParsedFile]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Загруженные файлы")
                .font(.headline)
            
            HStack(spacing: 20) {
                SummaryCard(title: "Файлов", value: "\(files.count)", icon: "doc.fill")
                SummaryCard(title: "Успешно", value: "\(files.filter { $0.status == .success }.count)", icon: "checkmark.circle.fill")
                SummaryCard(title: "Транзакций", value: "\(files.reduce(0) { $0 + $1.transactionCount })", icon: "arrow.left.arrow.right")
            }
        }
    }
}

struct SummaryCard: View {
    let title: String
    let value: String
    let icon: String
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: icon)
                    .foregroundColor(.accentColor)
                Text(title)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Text(value)
                .font(.title2)
                .fontWeight(.bold)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(Color.secondary.opacity(0.1))
        .cornerRadius(10)
    }
}

// MARK: - Preview Pane

struct PreviewPane: View {
    let transactions: [Transaction]
    let positions: [PortfolioPosition]
    @State private var selectedTab = 0
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Предварительный просмотр")
                .font(.headline)
            
            Picker("Тип", selection: $selectedTab) {
                Text("Позиции").tag(0)
                Text("Транзакции").tag(1)
            }
            .pickerStyle(.segmented)
            
            if selectedTab == 0 {
                PositionsPreview(positions: positions)
            } else {
                TransactionsPreview(transactions: transactions)
            }
        }
    }
}

struct PositionsPreview: View {
    let positions: [PortfolioPosition]
    
    var body: some View {
        Table(positions.prefix(10)) {
            TableColumn("Тикер") { pos in
                Text(pos.ticker)
            }
            TableColumn("Кол-во") { pos in
                Text(String(format: "%.2f", pos.quantity))
            }
            TableColumn("Ср. цена") { pos in
                Text(String(format: "%.2f", pos.averagePrice))
            }
            TableColumn("Стоимость") { pos in
                Text(String(format: "%.2f", pos.marketValue))
            }
        }
        .tableStyle(.inset)
    }
}

struct TransactionsPreview: View {
    let transactions: [Transaction]
    
    var body: some View {
        Table(transactions.prefix(10)) {
            TableColumn("Дата") { tx in
                Text(tx.date, style: .date)
            }
            TableColumn("Тикер") { tx in
                Text(tx.ticker)
            }
            TableColumn("Тип") { tx in
                Text(tx.type.displayValue)
            }
            TableColumn("Сумма") { tx in
                Text(String(format: "%.2f", tx.amount))
            }
        }
        .tableStyle(.inset)
    }
}

#Preview {
    ContentView()
        .modelContainer(for: Transaction.self, inMemory: true)
}

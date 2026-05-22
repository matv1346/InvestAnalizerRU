//
//  ParsedFile.swift
//  BrokerReportsApp
//
//  Модель загруженного файла отчёта
//

import Foundation
import SwiftData
import UniformTypeIdentifiers

/// Статус обработки файла
public enum FileProcessingStatus: String, Codable {
    case pending = "Ожидает"
    case parsing = "Обработка"
    case success = "Успешно"
    case error = "Ошибка"
    
    public var displayValue: String { rawValue }
}

/// Информация о загруженном файле
@Model
public final class ParsedFile {
    public var id: String
    public var fileName: String
    public var filePath: String?
    public var fileType: String
    public var fileSize: Int64
    public var uploadedAt: Date
    public var status: FileProcessingStatus
    public var errorMessage: String?
    public var transactionCount: Int
    public var brokerName: String?
    
    public init(
        id: String = UUID().uuidString,
        fileName: String,
        filePath: String? = nil,
        fileType: String,
        fileSize: Int64,
        status: FileProcessingStatus = .pending,
        errorMessage: String? = nil,
        transactionCount: Int = 0,
        brokerName: String? = nil
    ) {
        self.id = id
        self.fileName = fileName
        self.filePath = filePath
        self.fileType = fileType
        self.fileSize = fileSize
        self.uploadedAt = Date()
        self.status = status
        self.errorMessage = errorMessage
        self.transactionCount = transactionCount
        self.brokerName = brokerName
    }
    
    /// Форматированный размер файла
    public var formattedFileSize: String {
        let formatter = ByteCountFormatter()
        formatter.countStyle = .file
        return formatter.string(fromByteCount: fileSize)
    }
    
    /// Иконка в зависимости от типа файла
    public var fileIcon: String {
        switch fileType.lowercased() {
        case "xlsx", "xls":
            return "doc.fill"
        case "csv":
            return "text.alignleft"
        case "pdf":
            return "doc.richtext"
        case "ofx":
            return "arrow.triangle.2.circlepath"
        default:
            return "doc"
        }
    }
}

extension ParsedFile: Hashable {
    public func hash(into hasher: inout Hasher) {
        hasher.combine(id)
    }
    
    public static func == (lhs: ParsedFile, rhs: ParsedFile) -> Bool {
        lhs.id == rhs.id
    }
}

// MARK: - UTType Extension

public extension UTType {
    static var ofx: UTType {
        UTType(filenameExtension: "ofx") ?? .data
    }
    
    static var xlsx: UTType {
        UTType(filenameExtension: "xlsx") ?? .data
    }
}

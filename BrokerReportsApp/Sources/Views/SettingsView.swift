//
//  SettingsView.swift
//  BrokerReportsApp
//
//  Настройки приложения
//

import SwiftUI

struct SettingsView: View {
    @AppStorage("maxFileSize") private var maxFileSizeMB: Int = 50
    @AppStorage("defaultCurrency") private var defaultCurrency: String = "RUB"
    @AppStorage("savePath") private var savePath: String = "~/Downloads"
    
    var body: some View {
        Form {
            Section("Парсинг файлов") {
                HStack {
                    Text("Макс. размер файла (МБ)")
                    Spacer()
                    TextField("", value: $maxFileSizeMB, formatter: NumberFormatter())
                        .textFieldStyle(.roundedBorder)
                        .frame(width: 80)
                }
                
                Picker("Валюта по умолчанию", selection: $defaultCurrency) {
                    Text("RUB").tag("RUB")
                    Text("USD").tag("USD")
                    Text("EUR").tag("EUR")
                }
            }
            
            Section("Сохранение отчётов") {
                HStack {
                    Text("Папка сохранения")
                    Spacer()
                    Text(savePath)
                        .foregroundColor(.secondary)
                        .lineLimit(1)
                    
                    Button("Изменить") {
                        selectSavePath()
                    }
                }
            }
            
            Section("О приложении") {
                HStack {
                    Text("Версия")
                    Spacer()
                    Text("1.0.0")
                        .foregroundColor(.secondary)
                }
                
                HStack {
                    Text("Сборка")
                    Spacer()
                    Text("1")
                        .foregroundColor(.secondary)
                }
            }
        }
        .formStyle(.grouped)
        .frame(width: 400, height: 300)
        .padding()
    }
    
    private func selectSavePath() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        
        if panel.runModal() == .OK, let url = panel.url {
            savePath = url.path
        }
    }
}

#Preview {
    SettingsView()
}

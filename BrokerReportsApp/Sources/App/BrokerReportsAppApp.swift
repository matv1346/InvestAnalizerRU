//
//  BrokerReportsAppApp.swift
//  BrokerReportsApp
//
//  Главный файл приложения
//

import SwiftUI
import SwiftData

@main
struct BrokerReportsAppApp: App {
    var sharedModelContainer: ModelContainer = {
        let schema = Schema([
            Transaction.self,
            ParsedFile.self,
            PortfolioPosition.self,
            PortfolioMetrics.self,
            DailyPortfolioValue.self
        ])
        
        let modelConfiguration = ModelConfiguration(
            schema: schema,
            isStoredInMemoryOnly: false,
            cloudKitDatabase: .none
        )
        
        do {
            return try ModelContainer(for: schema, configurations: [modelConfiguration])
        } catch {
            fatalError("Could not create ModelContainer: \(error)")
        }
    }()
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(\.modelContext, sharedModelContainer.mainContext)
        }
        .windowStyle(.titleBar)
        .commands {
            CommandGroup(replacing: .appSettings) {
                Button("Настройки...") {
                    NSApp.sendAction(Selector(("showSettingsWindow:")), to: nil, from: nil)
                }
                .keyboardShortcut(",", modifiers: .command)
            }
            
            CommandGroup(after: .appInfo) {
                Button("О приложении") {
                    NSApp.orderFrontStandardAboutPanel(nil)
                }
            }
        }
        
        #if os(macOS)
        Settings {
            SettingsView()
        }
        #endif
    }
}

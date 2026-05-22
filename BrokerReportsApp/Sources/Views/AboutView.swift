//
//  AboutView.swift
//  BrokerReportsApp
//
//  Окно "О приложении"
//

import SwiftUI

struct AboutView: View {
    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "chart.line.uptrend.xyaxis")
                .font(.system(size: 60))
                .foregroundColor(.accentColor)
            
            Text("Broker Reports App")
                .font(.title)
                .fontWeight(.bold)
            
            Text("Версия 1.0.0")
                .font(.body)
                .foregroundColor(.secondary)
            
            Text("Приложение для консолидации отчётов брокеров\nи генерации инвестиционных отчётов в PDF")
                .font(.caption)
                .multilineTextAlignment(.center)
                .foregroundColor(.secondary)
            
            Divider()
            
            Text("© 2024 Все права защищены")
                .font(.caption2)
                .foregroundColor(.secondary)
        }
        .padding(40)
        .frame(width: 350, height: 300)
    }
}

#Preview {
    AboutView()
}

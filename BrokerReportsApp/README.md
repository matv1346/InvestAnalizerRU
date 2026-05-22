# Broker Reports App

Нативное macOS-приложение для консолидации отчётов брокеров и генерации инвестиционных отчётов в PDF.

## 📋 Требования

- **macOS**: 13.0 (Ventura) или новее
- **Xcode**: 15.0 или новее
- **Swift**: 5.9+

## 🏗️ Структура проекта

```
BrokerReportsApp/
├── Sources/
│   ├── App/                    # Главный файл приложения
│   │   └── BrokerReportsAppApp.swift
│   ├── Models/                 # Модели данных
│   │   ├── Transaction.swift
│   │   ├── PortfolioPosition.swift
│   │   └── ParsedFile.swift
│   ├── Parsers/                # Парсеры файлов
│   │   ├── ExcelParser.swift
│   │   ├── CSVParser.swift
│   │   ├── PDFTableParser.swift
│   │   └── OFXParser.swift
│   ├── Calculators/            # Калькуляторы
│   │   ├── FIFOEngine.swift
│   │   └── MetricsCalculator.swift
│   ├── Generators/             # Генераторы отчётов
│   │   └── PDFReportGenerator.swift
│   ├── ViewModels/             # ViewModel
│   │   └── ReportsViewModel.swift
│   └── Views/                  # SwiftUI представления
│       ├── ContentView.swift
│       ├── SettingsView.swift
│       └── AboutView.swift
├── Resources/                  # Ресурсы
├── Tests/                      # Юнит-тесты
├── build-dmg.sh               # Скрипт сборки DMG
└── README.md
```

## 🚀 Быстрый старт

### 1. Открытие проекта

```bash
cd BrokerReportsApp
open Package.swift  # Или откройте через Xcode
```

### 2. Сборка в Xcode

1. Откройте проект в Xcode 15+
2. Выберите схему `BrokerReportsApp`
3. Для отладки: нажмите `Cmd+R`
4. Для релиза: `Product → Archive`

### 3. Создание DMG

```bash
# После сборки Release конфигурации
./build-dmg.sh --version 1.0.0
```

## 📁 Поддерживаемые форматы

| Формат | Расширения | Описание |
|--------|------------|----------|
| Excel  | `.xlsx`, `.xls` | Отчёты в формате XLSX |
| CSV    | `.csv`     | Текстовые файлы с разделителями |
| PDF    | `.pdf`     | Таблицы из PDF документов |
| OFX    | `.ofx`, `.qfx` | Open Financial Exchange |

## 🔧 Настройки

Приложение поддерживает следующие настройки (через `UserDefaults`):

- `maxFileSize` — максимальный размер файла (МБ), по умолчанию 50
- `defaultCurrency` — валюта по умолчанию (RUB/USD/EUR)
- `savePath` — путь сохранения отчётов

## 📊 Расчёт метрик

Приложение рассчитывает следующие инвестиционные метрики:

- **P&L** — общая прибыль/убыток
- **ROI** — возврат на инвестиции (%)
- **CAGR** — среднегодовая доходность
- **Max Drawdown** — максимальная просадка
- **Volatility** — волатильность портфеля
- **Dividend Yield** — дивидендная доходность

## 🔐 Безопасность

- App Sandbox с минимальными разрешениями
- Все данные хранятся локально (SwiftData)
- Нет сетевого взаимодействия
- Privacy Manifest включён

## 📦 Code Signing & Notarization

### Подпись приложения

```bash
codesign --deep --force --sign "Developer ID Application: Your Name" \
  build/Release/BrokerReportsApp.app
```

### Нотаризация

```bash
xcrun notarytool submit build/Release/BrokerReportsApp-1.0.0.dmg \
  --apple-id "your@apple.id" \
  --team-id "TEAMID" \
  --password "app-specific-password"
```

### Stapling

```bash
xcrun stapler staple build/Release/BrokerReportsApp.app
```

## 🧪 Тестирование

Запуск тестов:

```bash
swift test
# или в Xcode: Product → Test (Cmd+U)
```

## 🛠️ Расширение функциональности

### Добавление поддержки CoreXLSX

Для полноценного парсинга XLSX добавьте зависимость в `Package.swift`:

```swift
dependencies: [
    .package(url: "https://github.com/CoreOffice/CoreXLSX.git", from: "0.17.0")
]
```

### Добавление новых типов активов

Отредактируйте `AssetType` в `PortfolioPosition.swift`:

```swift
public enum AssetType: String, Codable, CaseIterable {
    case stock = "Акции"
    case bond = "Облигации"
    // Добавьте новые типы здесь
}
```

## 📝 Лицензия

© 2024 Все права защищены.

## 🤝 Вклад в проект

1. Fork репозиторий
2. Создайте ветку (`git checkout -b feature/amazing-feature`)
3. Commit изменения (`git commit -m 'Add amazing feature'`)
4. Push (`git push origin feature/amazing-feature`)
5. Откройте Pull Request

## 📞 Поддержка

Вопросы и предложения направляйте через Issues на GitHub.

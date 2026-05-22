#!/bin/bash
#
#  build-dmg.sh
#  BrokerReportsApp
#
#  Скрипт для создания .dmg образа приложения
#

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Параметры по умолчанию
APP_NAME="BrokerReportsApp"
VERSION="1.0.0"
BUILD_DIR="build"
RELEASE_DIR="${BUILD_DIR}/Release"
DMG_NAME="${APP_NAME}-${VERSION}.dmg"
VOLUME_NAME="${APP_NAME}"

# Пути
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_PATH="${RELEASE_DIR}/${APP_NAME}.app"
DMG_PATH="${RELEASE_DIR}/${DMG_NAME}"

# Парсинг аргументов
while [[ $# -gt 0 ]]; do
    case $1 in
        --app-name)
            APP_NAME="$2"
            shift 2
            ;;
        --version)
            VERSION="$2"
            shift 2
            ;;
        --output)
            DMG_NAME="$2"
            shift 2
            ;;
        --help)
            echo "Использование: $0 [опции]"
            echo ""
            echo "Опции:"
            echo "  --app-name NAME    Имя приложения (по умолчанию: BrokerReportsApp)"
            echo "  --version VERSION  Версия приложения (по умолчанию: 1.0.0)"
            echo "  --output NAME      Имя выходного .dmg файла"
            echo "  --help             Показать эту справку"
            exit 0
            ;;
        *)
            echo -e "${RED}Неизвестная опция: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Создание DMG образа для ${APP_NAME}${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Проверка наличия приложения
if [ ! -d "$APP_PATH" ]; then
    echo -e "${RED}Ошибка: Приложение не найдено по пути:${NC}"
    echo -e "${RED}  $APP_PATH${NC}"
    echo ""
    echo -e "${YELLOW}Убедитесь, что приложение собрано в конфигурации Release.${NC}"
    echo -e "${YELLOW}В Xcode: Product → Archive или выберите схему Release и нажмите Build.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Приложение найдено: $APP_PATH${NC}"

# Проверка кодовой подписи
echo ""
echo -e "${BLUE}Проверка кодовой подписи...${NC}"

if codesign -dv "$APP_PATH" 2>/dev/null; then
    echo -e "${GREEN}✓ Приложение подписано${NC}"
else
    echo -e "${YELLOW}⚠ Приложение не подписано!${NC}"
    echo ""
    echo -e "${YELLOW}Для подписи используйте команду:${NC}"
    echo -e "${BLUE}  codesign --deep --force --sign \"Developer ID Application: Your Name\" \"$APP_PATH\"${NC}"
    echo ""
    read -p "Продолжить без подписи? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Создание временной директории для DMG
TEMP_DIR=$(mktemp -d)
DMG_CONTENTS_DIR="${TEMP_DIR}/${VOLUME_NAME}"
mkdir -p "$DMG_CONTENTS_DIR"

echo ""
echo -e "${BLUE}Копирование приложения...${NC}"
cp -R "$APP_PATH" "$DMG_CONTENTS_DIR/"
echo -e "${GREEN}✓ Приложение скопировано${NC}"

# Создание символической ссылки на Applications
echo ""
echo -e "${BLUE}Создание ссылки на Applications...${NC}"
ln -s /Applications "$DMG_CONTENTS_DIR/Applications"
echo -e "${GREEN}✓ Ссылка создана${NC}"

# Создание фона (если есть ресурсы)
BACKGROUND_DIR="${SCRIPT_DIR}/Resources/DMGBackground"
if [ -d "$BACKGROUND_DIR" ] && [ -f "${BACKGROUND_DIR}/background.png" ]; then
    echo ""
    echo -e "${BLUE}Настройка фона DMG...${NC}"
    mkdir -p "${TEMP_DIR}/.background"
    cp "${BACKGROUND_DIR}/background.png" "${TEMP_DIR}/.background/icon.png"
fi

# Создание DMG с помощью hdiutil
echo ""
echo -e "${BLUE}Создание DMG образа...${NC}"

# Временный raw образ
RAW_DMG="${TEMP_DIR}/${VOLUME_NAME}.cdr"

hdiutil create -volname "${VOLUME_NAME}" \
    -srcfolder "$DMG_CONTENTS_DIR" \
    -ov -format UDRW \
    "$RAW_DMG"

echo -e "${GREEN}✓ Raw образ создан${NC}"

# Конвертация в финальный DMG
hdiutil convert "$RAW_DMG" \
    -format UDZO \
    -imagekey zlib-level=9 \
    -o "$DMG_PATH"

echo -e "${GREEN}✓ DMG образ создан: $DMG_PATH${NC}"

# Очистка
rm -rf "$TEMP_DIR"

# Вывод информации о файле
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Готово!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

DMG_SIZE=$(du -h "$DMG_PATH" | cut -f1)
echo -e "${GREEN}Файл: ${DMG_NAME}${NC}"
echo -e "${GREEN}Размер: ${DMG_SIZE}${NC}"
echo -e "${GREEN}Путь: ${DMG_PATH}${NC}"
echo ""

# Предложение открыть папку
read -p "Открыть папку с DMG файлом? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    open -R "$DMG_PATH"
fi

echo ""
echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}  Следующие шаги:${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""
echo -e "1. ${BLUE}Тестирование:${NC} Установите приложение из DMG"
echo -e "2. ${BLUE}Notarization (для дистрибуции):${NC}"
echo -e "   xcrun notarytool submit \"$DMG_PATH\" --apple-id \"your@apple.id\" --team-id \"TEAMID\" --password \"app-password\""
echo -e "3. ${BLUE}Stapling:${NC}"
echo -e "   xcrun stapler staple \"$APP_PATH\""
echo ""

"""
ui/main_navigation.py - Основной навигационный компонент (QTabWidget)
"""

from PySide6.QtWidgets import QTabWidget, QWidget, QVBoxLayout
from PySide6.QtCore import Signal


class MainNavigation(QTabWidget):
    """Основной навигатор приложения с вкладками"""
    
    current_tab_changed = Signal(int)
    
    def __init__(self):
        super().__init__()
        
        # Настройка стиля табов
        self.setMovable(True)
        self.setTabsClosable(False)
        self.setIconSize((20, 20))
        
        # Подключение сигнала переключения таба
        self.currentChanged.connect(self._on_tab_changed)
    
    def add_tab(self, widget: QWidget, title: str, icon=None) -> int:
        """Добавление вкладки"""
        if icon:
            index = self.addTab(widget, icon, title)
        else:
            index = self.addTab(widget, title)
        
        return index
    
    def _on_tab_changed(self, index: int):
        """Обработчик переключения вкладки"""
        self.current_tab_changed.emit(index)

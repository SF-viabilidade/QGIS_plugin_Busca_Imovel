# ARQUIVO: busca_imovel.py
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import Qt
from qgis.utils import iface

# Importa a interface principal
from .interface_imovel import BuscaImovelDock

class BuscaImovelPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.dock_widget = None
        self.action = None

    def initGui(self):
        # 1. Cria a Ação (Botão)
        # Se não tiver o icon.png, usaremos um ícone padrão do QGIS ou texto
        icon_path = ':/plugins/busca_imovel/icon.png'
        self.action = QAction(QIcon(icon_path), "Busca Imóveis", self.iface.mainWindow())
        self.action.setObjectName("BuscaImovelAction")
        self.action.setCheckable(True)
        
        # 2. Conecta o clique à função run
        self.action.triggered.connect(self.run)

        # 3. Adiciona na Barra de Ferramentas e no Menu
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("&Busca Imóveis", self.action)

    def unload(self):
        # Limpeza quando o plugin é desinstalado/desativado
        self.iface.removeToolBarIcon(self.action)
        self.iface.removePluginMenu("&Busca Imóveis", self.action)
        
        if self.dock_widget:
            self.iface.removeDockWidget(self.dock_widget)
            self.dock_widget = None

    def run(self):
        # Lógica de Abrir/Fechar a janela
        if not self.dock_widget:
            # Se a janela ainda não existe, cria-a
            self.dock_widget = BuscaImovelDock(self.iface.mainWindow())
            
            # Sincroniza o estado do botão com a visibilidade da janela
            self.dock_widget.visibilityChanged.connect(self.action.setChecked)
            
            # Adiciona o dock na lateral direita
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock_widget)
            self.dock_widget.show()
        else:
            # Se já existe, alterna a visibilidade
            if self.dock_widget.isVisible():
                self.dock_widget.hide()
            else:
                self.dock_widget.show()
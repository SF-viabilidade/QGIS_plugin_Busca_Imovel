# ARQUIVO: interface_imovel.py
import os
import re
import glob
import shutil
import unicodedata
from PyQt5.QtWidgets import (QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QAbstractItemView, QDialog, 
                             QGroupBox, QTabWidget, QComboBox, QCheckBox, 
                             QFileDialog, QSizePolicy, QListWidget, QListWidgetItem, 
                             QMessageBox, QGraphicsView, QGraphicsScene,
                             QGraphicsPixmapItem)
from PyQt5.QtCore import Qt, pyqtSignal, QUrl, QThread
from PyQt5.QtGui import QPixmap, QDesktopServices

from qgis.core import (QgsProject, QgsFeatureRequest, QgsLayoutExporter, 
                       QgsGeometry, QgsReadWriteContext, QgsPrintLayout,
                       QgsCoordinateReferenceSystem, QgsCoordinateTransform)
from qgis.gui import QgsMapTool
from qgis.utils import iface

# ============================================================================
# TEMA VISUAL (QSS) - ESTILO MODERNO
# ============================================================================
MODERN_STYLE = """
QWidget {
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
    color: #333333;
}
QPushButton {
    background-color: #005A9E;
    color: white;
    border-radius: 4px;
    padding: 6px 12px;
    font-weight: bold;
    border: none;
}
QPushButton:hover { background-color: #106EBE; }
QPushButton:pressed { background-color: #004578; }
QPushButton:disabled { background-color: #cccccc; color: #888888; }
QPushButton#btnAcaoSecundaria { background-color: #E1DFDD; color: #333333; }
QPushButton#btnAcaoSecundaria:hover { background-color: #D2D0CE; }

QLineEdit, QComboBox {
    padding: 6px;
    border: 1px solid #8A8886;
    border-radius: 4px;
    background-color: #FFFFFF;
}
QLineEdit:focus, QComboBox:focus { border: 1px solid #005A9E; }

QTableWidget {
    gridline-color: #E1DFDD;
    border: 1px solid #C8C6C4;
    border-radius: 4px;
    selection-background-color: #CCE3F5;
    selection-color: #333333;
    background-color: #FFFFFF;
    alternate-background-color: #F8F8F8;
}
QHeaderView::section {
    background-color: #F3F2F1;
    padding: 6px;
    border: none;
    border-right: 1px solid #E1DFDD;
    border-bottom: 1px solid #E1DFDD;
    font-weight: bold;
}
QTabWidget::pane {
    border: 1px solid #C8C6C4;
    border-radius: 4px;
    top: -1px;
    background-color: #FFFFFF;
}
QTabBar::tab {
    background: #F3F2F1;
    border: 1px solid #C8C6C4;
    padding: 8px 20px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background: #FFFFFF;
    border-bottom-color: #FFFFFF;
    font-weight: bold;
    color: #005A9E;
}
QGroupBox {
    font-weight: bold;
    border: 1px solid #C8C6C4;
    border-radius: 5px;
    margin-top: 15px;
    padding-top: 15px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 5px;
    left: 10px;
    color: #005A9E;
}
"""

# ============================================================================
# FUNÇÕES UTILITÁRIAS
# ============================================================================
def normalize_str(s):
    """Remove acentos e coloca em minúsculas."""
    if not s: return ""
    return ''.join(c for c in unicodedata.normalize('NFD', str(s)) 
                   if unicodedata.category(c) != 'Mn').lower()

# ============================================================================
# THREAD DE BUSCA DE FOTOS (Evita congelamento da interface)
# ============================================================================
class FotoBuscaThread(QThread):
    resultado_pronto = pyqtSignal(list)
    
    def __init__(self, inscricao_limpa, base_path):
        super().__init__()
        self.inscricao_limpa = inscricao_limpa
        self.base_path = base_path
        
    def run(self):
        lista_fotos = []
        if os.path.exists(self.base_path) and self.inscricao_limpa:
            padroes = [
                os.path.join(self.base_path, f"{self.inscricao_limpa}.*"),
                os.path.join(self.base_path, f"{self.inscricao_limpa}_*.*")
            ]
            encontrados = []
            for p in padroes: encontrados.extend(glob.glob(p))
            exts = ['.jpg', '.jpeg', '.png', '.bmp']
            lista_fotos = sorted(list(set([f for f in encontrados if os.path.splitext(f)[1].lower() in exts])))
        self.resultado_pronto.emit(lista_fotos)

# ============================================================================
# COMPONENTE DE VISUALIZAÇÃO DE FOTOS COM ZOOM
# ============================================================================
class FotoViewer(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        # Desativa as scrollbars nativas para usar pan (arrastar) fluido manual
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.setStyleSheet("background-color: #F3F2F1; border: 1px solid #C8C6C4; border-radius: 5px;")
        self.setMinimumHeight(450)
        
        self.pixmap_item = None
        
        # Variáveis para controlo manual do arrastamento (Pan)
        self._is_panning = False
        self._pan_start = None

    def show_text(self, text):
        self.scene.clear()
        self.pixmap_item = None
        text_item = self.scene.addText(text)
        text_item.setDefaultTextColor(Qt.darkGray)
        self.setSceneRect(0, 0, 400, 300)
        text_item.setPos((400 - text_item.boundingRect().width()) / 2, (300 - text_item.boundingRect().height()) / 2)
        self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    def set_image(self, pixmap):
        self.scene.clear()
        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        self.pixmap_item.setTransformationMode(Qt.SmoothTransformation)
        self.scene.addItem(self.pixmap_item)
        
        # Define os limites exatos da cena de acordo com a imagem real
        self.setSceneRect(0, 0, pixmap.width(), pixmap.height())
        self.fit_in_view()

    def fit_in_view(self):
        if self.pixmap_item:
            self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)

    def wheelEvent(self, event):
        if not self.pixmap_item:
            return
        
        # Define a âncora para fazer zoom focado na posição atual do cursor
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        
        if event.angleDelta().y() > 0:
            self.scale(1.25, 1.25)
        else:
            self.scale(0.8, 0.8)

    def zoom_in(self):
        if not self.pixmap_item: return
        # Quando usa os botões, o zoom foca no centro da visualização
        self.setTransformationAnchor(QGraphicsView.AnchorViewCenter)
        self.scale(1.25, 1.25)

    def zoom_out(self):
        if not self.pixmap_item: return
        # Quando usa os botões, o zoom foca no centro da visualização
        self.setTransformationAnchor(QGraphicsView.AnchorViewCenter)
        self.scale(0.8, 0.8)

    # --- EVENTOS DE RATO PARA ARRASTAR (PAN MANUAL) ---
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor) # Muda o cursor para a "mão fechada"
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_panning = False
            self.setCursor(Qt.ArrowCursor)
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_panning and self._pan_start is not None:
            delta = event.pos() - self._pan_start
            
            # Desloca a visualização subtraindo a diferença ao valor interno das barras (mesmo ocultas)
            h_bar = self.horizontalScrollBar()
            v_bar = self.verticalScrollBar()
            
            h_bar.setValue(h_bar.value() - delta.x())
            v_bar.setValue(v_bar.value() - delta.y())
            
            self._pan_start = event.pos()
        super().mouseMoveEvent(event)


# ============================================================================
# 1. CLASSE DA FICHA CADASTRAL
# ============================================================================
class FichaImovelDialog(QDialog):
    def __init__(self, feature, layer, parent=None):
        super().__init__(parent)
        self.feature = feature
        self.layer = layer 
        self.setStyleSheet(MODERN_STYLE)
        
        self.inscricao = "N/A"
        for field in layer.fields():
            name_norm = normalize_str(field.name())
            if 'inscricao' in name_norm or name_norm == 'im':
                val = feature[field.name()]
                if val: self.inscricao = str(val)
                break
        
        self.inscricao_limpa = re.sub(r'[^0-9]', '', self.inscricao)

        self.setWindowTitle(f"Ficha do Imóvel: {self.inscricao}")
        self.setMinimumWidth(1000)
        self.setMinimumHeight(750)

        layout_principal = QVBoxLayout(self)
        
        # Cabeçalho da Ficha com Botão do Street View
        header_layout = QHBoxLayout()
        lbl_titulo = QLabel(f"🏢 Inscrição: <b>{self.inscricao}</b>")
        lbl_titulo.setStyleSheet("font-size: 18px; color: #005A9E;")
        header_layout.addWidget(lbl_titulo)
        header_layout.addStretch()
        
        btn_street_view = QPushButton("🗺️ Abrir Street View")
        btn_street_view.clicked.connect(self.abrir_street_view)
        header_layout.addWidget(btn_street_view)
        layout_principal.addLayout(header_layout)

        self.tabs = QTabWidget()
        layout_principal.addWidget(self.tabs)

        self.tab_dados = QWidget()
        self.setup_aba_dados(self.tab_dados)
        self.tabs.addTab(self.tab_dados, "📄 Dados Gerais")

        self.tab_fotos = QWidget()
        self.setup_aba_fotos(self.tab_fotos)
        self.tabs.addTab(self.tab_fotos, "🖼️ Fachada")

        self.tab_anexos = QWidget()
        self.setup_aba_anexos(self.tab_anexos)
        self.tabs.addTab(self.tab_anexos, "📎 Anexos")

        self.tab_historico = QWidget()
        self.setup_aba_historico(self.tab_historico)
        self.tabs.addTab(self.tab_historico, "🕒 Histórico")

        # Rodapé
        hbox_btns = QHBoxLayout()
        self.btn_croqui = QPushButton("🖨️ Gerar Croqui (PDF)")
        self.btn_croqui.clicked.connect(self.gerar_croqui_local)
        hbox_btns.addWidget(self.btn_croqui)
        
        hbox_btns.addStretch()
        
        btn_fechar = QPushButton("❌ Fechar")
        btn_fechar.setObjectName("btnAcaoSecundaria")
        btn_fechar.clicked.connect(self.accept)
        hbox_btns.addWidget(btn_fechar)

        layout_principal.addLayout(hbox_btns)

    def abrir_street_view(self):
        geom = self.feature.geometry()
        if geom.isNull():
            QMessageBox.warning(self, "Aviso", "Imóvel sem geometria válida.")
            return

        centroid = geom.centroid().asPoint()
        
        # Transformar coordenadas para WGS 84 (EPSG:4326) necessário para o Google Maps
        crs_src = self.layer.crs()
        crs_dest = QgsCoordinateReferenceSystem("EPSG:4326")
        transform = QgsCoordinateTransform(crs_src, crs_dest, QgsProject.instance())
        
        try:
            pt_wgs = transform.transform(centroid)
            url = f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={pt_wgs.y()},{pt_wgs.x()}"
            QDesktopServices.openUrl(QUrl(url))
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao calcular coordenadas:\n{str(e)}")

    # --- ABA DADOS ---
    def setup_aba_dados(self, parent_widget):
        layout = QVBoxLayout(parent_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Atributo", "Informação Cadastral"])
        table.setAlternatingRowColors(True)
        
        header = table.horizontalHeader()
        # Permite redimensionar colunas interativamente
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        table.setColumnWidth(0, 250) # Largura inicial da coluna 'Atributo'
        
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)

        fields = self.layer.fields()
        table.setRowCount(len(fields))
        
        for i, field in enumerate(fields):
            nome_campo = field.name()
            try: val = self.feature[nome_campo]
            except KeyError: val = ""
            
            valor_str = str(val) if val is not None else ""
            
            item_key = QTableWidgetItem(nome_campo)
            item_key.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            font = item_key.font()
            font.setBold(True)
            item_key.setFont(font)
            
            item_val = QTableWidgetItem(valor_str)
            item_val.setToolTip(valor_str) 
            
            table.setItem(i, 0, item_key)
            table.setItem(i, 1, item_val)

        layout.addWidget(table)

    # --- ABA FOTOS (ASSÍNCRONA COM ZOOM) ---
    def setup_aba_fotos(self, parent_widget):
        layout = QVBoxLayout(parent_widget)
        
        self.viewer = FotoViewer()
        self.viewer.show_text("A procurar fotos na rede...")
        layout.addWidget(self.viewer)

        hbox_nav = QHBoxLayout()
        
        # Botões de Zoom
        self.btn_zoom_out = QPushButton("➖")
        self.btn_zoom_out.setObjectName("btnAcaoSecundaria")
        self.btn_zoom_out.setToolTip("Reduzir Zoom")
        self.btn_zoom_out.clicked.connect(self.viewer.zoom_out)
        
        self.btn_fit = QPushButton("🔳")
        self.btn_fit.setObjectName("btnAcaoSecundaria")
        self.btn_fit.setToolTip("Ajustar ao Ecrã")
        self.btn_fit.clicked.connect(self.viewer.fit_in_view)

        self.btn_zoom_in = QPushButton("➕")
        self.btn_zoom_in.setObjectName("btnAcaoSecundaria")
        self.btn_zoom_in.setToolTip("Aumentar Zoom")
        self.btn_zoom_in.clicked.connect(self.viewer.zoom_in)

        # Botões de Navegação
        self.btn_prev = QPushButton("◀ Anterior")
        self.btn_prev.setObjectName("btnAcaoSecundaria")
        self.btn_prev.clicked.connect(self.foto_anterior)
        
        self.btn_next = QPushButton("Próxima ▶")
        self.btn_next.setObjectName("btnAcaoSecundaria")
        self.btn_next.clicked.connect(self.foto_proxima)
        
        self.lbl_contador = QLabel("0 / 0")
        self.lbl_contador.setAlignment(Qt.AlignCenter)
        self.lbl_contador.setStyleSheet("font-weight: bold; min-width: 60px;")

        hbox_nav.addWidget(self.btn_zoom_out)
        hbox_nav.addWidget(self.btn_fit)
        hbox_nav.addWidget(self.btn_zoom_in)
        hbox_nav.addStretch()
        hbox_nav.addWidget(self.btn_prev)
        hbox_nav.addWidget(self.lbl_contador)
        hbox_nav.addWidget(self.btn_next)
        hbox_nav.addStretch()
        layout.addLayout(hbox_nav)

        self.lista_fotos = []
        self.indice_atual = 0
        self.btn_prev.setEnabled(False)
        self.btn_next.setEnabled(False)
        
        # Inicia a thread para não congelar o QGIS
        base_path = r"P:\Ortofotos 2023\05. Foto-Fachada para Entrega"
        self.thread_fotos = FotoBuscaThread(self.inscricao_limpa, base_path)
        self.thread_fotos.resultado_pronto.connect(self.ao_terminar_busca_fotos)
        self.thread_fotos.start()

    def ao_terminar_busca_fotos(self, lista):
        self.lista_fotos = lista
        if self.lista_fotos:
            self.carregar_imagem(0)
        else:
            self.viewer.show_text("Nenhuma foto encontrada para esta inscrição.")
            self.lbl_contador.setText("0 / 0")

    def carregar_imagem(self, indice):
        if not self.lista_fotos: return
        self.indice_atual = indice % len(self.lista_fotos)
        caminho = self.lista_fotos[self.indice_atual]
        
        pixmap = QPixmap(caminho)
        if not pixmap.isNull():
            self.viewer.set_image(pixmap)
        else:
            self.viewer.show_text("Erro ao renderizar ficheiro da imagem.")

        self.lbl_contador.setText(f"Foto {self.indice_atual + 1} de {len(self.lista_fotos)}")
        tem_nav = len(self.lista_fotos) > 1
        self.btn_prev.setEnabled(tem_nav)
        self.btn_next.setEnabled(tem_nav)

    def foto_anterior(self): self.carregar_imagem(self.indice_atual - 1)
    def foto_proxima(self): self.carregar_imagem(self.indice_atual + 1)

    # --- ABA ANEXOS ---
    def setup_aba_anexos(self, parent_widget):
        layout = QVBoxLayout(parent_widget)
        layout.addWidget(QLabel("Arquivos digitais vinculados (Duplo clique para abrir):"))

        self.list_anexos = QListWidget()
        self.list_anexos.setAlternatingRowColors(True)
        self.list_anexos.itemDoubleClicked.connect(self.abrir_anexo)
        layout.addWidget(self.list_anexos)

        hbox_files = QHBoxLayout()
        btn_add = QPushButton("➕ Incluir Documento")
        btn_add.clicked.connect(self.adicionar_anexo)
        
        btn_open_dir = QPushButton("📂 Abrir Pasta Original")
        btn_open_dir.setObjectName("btnAcaoSecundaria")
        btn_open_dir.clicked.connect(self.abrir_pasta_anexos)
        
        btn_refresh = QPushButton("🔄 Atualizar")
        btn_refresh.setObjectName("btnAcaoSecundaria")
        btn_refresh.clicked.connect(self.carregar_lista_anexos)

        hbox_files.addWidget(btn_add)
        hbox_files.addWidget(btn_open_dir)
        hbox_files.addWidget(btn_refresh)
        layout.addLayout(hbox_files)

        self.base_anexos_path = r"S:\geomap\geomap_imob\imobiliario_geomap"
        self.carregar_lista_anexos()

    def get_path_imovel(self):
        if not self.inscricao_limpa: return None
        return os.path.join(self.base_anexos_path, self.inscricao_limpa)

    def carregar_lista_anexos(self):
        self.list_anexos.clear()
        path_imovel = self.get_path_imovel()
        
        if not os.path.exists(self.base_anexos_path):
            self.list_anexos.addItem("ERRO: Unidade de rede S:\\ não encontrada ou indisponível.")
            return

        if not path_imovel or not os.path.exists(path_imovel):
            self.list_anexos.addItem("Nenhuma pasta de anexos criada para este imóvel.")
            return

        try:
            arquivos = os.listdir(path_imovel)
            arquivos_filtrados = [f for f in arquivos if os.path.isfile(os.path.join(path_imovel, f))]
            if not arquivos_filtrados:
                self.list_anexos.addItem("Pasta existente, mas encontra-se vazia.")
            else:
                for arq in arquivos_filtrados:
                    item = QListWidgetItem(f"📄 {arq}")
                    self.list_anexos.addItem(item)
        except Exception as e:
            self.list_anexos.addItem(f"Erro ao ler pasta: {str(e)}")

    def adicionar_anexo(self):
        if not self.inscricao_limpa:
            QMessageBox.warning(self, "Aviso", "Imóvel sem inscrição válida.")
            return

        filename, _ = QFileDialog.getOpenFileName(self, "Selecione o documento a vincular")
        if not filename: return

        path_imovel = self.get_path_imovel()
        try:
            if not os.path.exists(path_imovel):
                os.makedirs(path_imovel)
            
            nome_arquivo = os.path.basename(filename)
            destino = os.path.join(path_imovel, nome_arquivo)
            if os.path.exists(destino):
                res = QMessageBox.question(self, "Substituir?", f"O arquivo '{nome_arquivo}' já existe.\nDeseja substituí-lo?", QMessageBox.Yes|QMessageBox.No)
                if res == QMessageBox.No: return

            shutil.copy2(filename, destino)
            QMessageBox.information(self, "Sucesso", "Documento adicionado com sucesso!")
            self.carregar_lista_anexos()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao adicionar documento:\n{str(e)}")

    def abrir_anexo(self, item):
        texto = item.text().replace("📄 ", "")
        if "ERRO" in texto or "Nenhuma" in texto or "Pasta" in texto: return
        path = os.path.join(self.get_path_imovel(), texto)
        if os.path.exists(path): QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def abrir_pasta_anexos(self):
        path = self.get_path_imovel()
        if path and os.path.exists(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        else:
            if os.path.exists(self.base_anexos_path):
                QMessageBox.information(self, "Info", "A pasta deste imóvel ainda não existe. Abrindo pasta raiz.")
                QDesktopServices.openUrl(QUrl.fromLocalFile(self.base_anexos_path))

    # --- ABA HISTÓRICO ---
    def setup_aba_historico(self, parent_widget):
        layout = QVBoxLayout(parent_widget)
        
        tabela = QTableWidget()
        tabela.setColumnCount(4)
        tabela.setHorizontalHeaderLabels(["Inscrição", "Data", "Histórico", "Assunto"])
        tabela.setWordWrap(True)
        
        header = tabela.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive) # Permite ajustar manual
        header.setStretchLastSection(True)
        
        # Conecta o redimensionamento das colunas com o ajuste dinâmico da altura das linhas
        header.sectionResized.connect(tabela.resizeRowsToContents)
        
        # Define larguras iniciais
        tabela.setColumnWidth(0, 100)
        tabela.setColumnWidth(1, 100)
        tabela.setColumnWidth(2, 400)
        
        tabela.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        tabela.setSelectionBehavior(QAbstractItemView.SelectRows)
        tabela.setAlternatingRowColors(True)
        tabela.verticalHeader().setVisible(False)
        tabela.setSortingEnabled(False)
        
        layout.addWidget(tabela)

        if self.inscricao == "N/A":
            layout.addWidget(QLabel("Imóvel sem inscrição identificada."))
            return

        nome_historico = "historico_imob_SMAR" 
        layers = QgsProject.instance().mapLayersByName(nome_historico)
        if not layers:
            layout.addWidget(QLabel(f"Camada de histórico '{nome_historico}' não encontrada no projeto."))
            return
        
        layer_hist = layers[0]

        try:
            im_busca = self.inscricao_limpa
            features = []
            
            if im_busca.isdigit():
                expr = f"\"IdOrigem\" = {im_busca}"
                req = QgsFeatureRequest().setFilterExpression(expr)
                features = list(layer_hist.getFeatures(req))
            
            if not features:
                expr = f"\"IdOrigem\" = '{self.inscricao}'"
                req = QgsFeatureRequest().setFilterExpression(expr)
                features = list(layer_hist.getFeatures(req))

            tabela.setRowCount(len(features))
            if not features:
                layout.addWidget(QLabel(f"Nenhum registo de histórico encontrado."))
                return

            for row_idx, feat in enumerate(features):
                def get_val(campo):
                    try:
                        v = feat[campo]
                        return str(v) if v is not None else ""
                    except KeyError: return ""

                tabela.setItem(row_idx, 0, QTableWidgetItem(get_val('IdOrigem')))
                tabela.setItem(row_idx, 1, QTableWidgetItem(get_val('DtHistorico')))
                
                item_hist = QTableWidgetItem(get_val('Historico'))
                item_hist.setToolTip(get_val('Historico'))
                tabela.setItem(row_idx, 2, item_hist)
                tabela.setItem(row_idx, 3, QTableWidgetItem(get_val('Assunto')))
            
            tabela.resizeRowsToContents()
            tabela.setSortingEnabled(True)
            tabela.sortItems(1, Qt.DescendingOrder) # Recentes primeiro

            layout.addWidget(QLabel(f"<b>Total de registos:</b> {len(features)}"))

        except Exception as e:
            layout.addWidget(QLabel(f"Erro ao processar histórico: {str(e)}"))

    def gerar_croqui_local(self):
        fid = self.feature.id()
        self.layer.selectByIds([fid])
        box = self.layer.getFeature(fid).geometry().boundingBox()
        box.scale(1.5)
        iface.mapCanvas().setExtent(box)
        iface.mapCanvas().refresh()

        project = QgsProject.instance()
        layout_manager = project.layoutManager()
        nome_layout = "A4 - Croqui de Imovel (IMOBILIARIO)"
        layout = layout_manager.layoutByName(nome_layout)

        if not layout:
            path_qpt = os.path.join(os.path.dirname(__file__), f"{nome_layout}.qpt")
            if os.path.exists(path_qpt):
                layout = QgsPrintLayout(project)
                layout.initializeDefaults()
                layout.setName(nome_layout)
                with open(path_qpt) as f:
                    template_content = f.read()
                from PyQt5.QtXml import QDomDocument
                doc = QDomDocument()
                doc.setContent(template_content)
                layout.loadFromTemplate(doc, QgsReadWriteContext())
                layout_manager.addLayout(layout)
            else:
                iface.messageBar().pushMessage("Erro", f"Template '{nome_layout}' não encontrado.", level=2)
                return

        atlas = layout.atlas()
        atlas.setCoverageLayer(self.layer)
        atlas.setEnabled(True)
        atlas.setFilterFeatures(True)
        atlas.setFilterExpression(f"$id = {fid}")

        nome_sugestao = f"CROQUI_{self.inscricao_limpa}.pdf"
        path_inicial = os.path.join(os.path.expanduser("~"), "Documents", nome_sugestao)
        
        filename, _ = QFileDialog.getSaveFileName(self, "Exportar Croqui PDF", path_inicial, "PDF (*.pdf)")
        if not filename: return

        if atlas.updateFeatures(): 
            atlas.beginRender()
            atlas.seekTo(0)
            exporter = QgsLayoutExporter(layout)
            result = exporter.exportToPdf(filename, QgsLayoutExporter.PdfExportSettings())
            atlas.endRender()
            if result == QgsLayoutExporter.Success:
                iface.messageBar().pushMessage("Sucesso", f"Croqui gerado: {filename}", level=0)
                try: os.startfile(filename)
                except: pass
            else:
                iface.messageBar().pushMessage("Erro", "Falha na exportação do PDF.", level=2)
        else:
             iface.messageBar().pushMessage("Erro", "Erro ao preparar imóvel no Atlas.", level=2)


# ============================================================================
# 2. FERRAMENTA DE MAPA
# ============================================================================
class ToolSelecionarFicha(QgsMapTool):
    imovel_encontrado = pyqtSignal(object)

    def __init__(self, canvas, layer):
        super().__init__(canvas)
        self.canvas = canvas
        self.layer = layer
        self.setCursor(Qt.CrossCursor)

    def canvasReleaseEvent(self, event):
        point_xy = self.toMapCoordinates(event.pos())
        point_geo = QgsGeometry.fromPointXY(point_xy)
        
        radius = self.canvas.mapUnitsPerPixel() * 2 
        rect = point_geo.buffer(radius, 5).boundingBox()
        request = QgsFeatureRequest().setFilterRect(rect)
        
        found = None
        for feat in self.layer.getFeatures(request):
            if feat.geometry().contains(point_geo):
                found = feat
                break 
        
        if not found:
            iterator = self.layer.getFeatures(request)
            try: found = next(iterator)
            except StopIteration: pass

        if found:
            self.imovel_encontrado.emit(found)
        else:
            iface.messageBar().pushMessage("Seleção", "Clique no interior de um lote válido.", level=1, duration=2)

# ============================================================================
# 3. INTERFACE PRINCIPAL (DOCK WIDGET)
# ============================================================================
class BuscaImovelDock(QDockWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔍 Busca de Imóveis")
        self.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        self.main_widget = QWidget()
        self.setWidget(self.main_widget)
        self.setStyleSheet(MODERN_STYLE)
        
        self.layout = QVBoxLayout(self.main_widget)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)
        
        self.setup_ui()
        self.tool_selecao = None

    def setup_ui(self):
        # --- Painel de Pesquisa ---
        gb = QGroupBox("Parâmetros de Pesquisa")
        lb = QVBoxLayout(gb)
        
        self.combo = QComboBox()
        self.combo.addItems(["Inscrição", "Endereço", "CPF/CNPJ", "Proprietário"])
        
        self.input_busca = QLineEdit()
        self.input_busca.setPlaceholderText("Introduza o termo a procurar...")
        self.input_busca.returnPressed.connect(self.buscar)
        
        self.check_exata = QCheckBox("Busca Exata (Ignorar partes de palavras)")
        
        btn_buscar = QPushButton("🔎 Realizar Busca")
        btn_buscar.clicked.connect(self.buscar)

        lb.addWidget(QLabel("Filtrar por:"))
        lb.addWidget(self.combo)
        lb.addWidget(self.input_busca)
        lb.addWidget(self.check_exata)
        lb.addWidget(btn_buscar)
        self.layout.addWidget(gb)

        # --- Tabela de Resultados ---
        self.tabela = QTableWidget()
        self.tabela.setColumnCount(3)
        self.tabela.setHorizontalHeaderLabels(["Inscrição", "Proprietário", "Endereço"])
        self.tabela.setSortingEnabled(True) 
        
        # Ajusta a largura das colunas interativamente
        self.tabela.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive) 
        self.tabela.horizontalHeader().setStretchLastSection(True) 
        self.tabela.setColumnWidth(0, 100)
        self.tabela.setColumnWidth(1, 250)
        
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabela.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabela.doubleClicked.connect(self.abrir_ficha_por_item)
        self.layout.addWidget(self.tabela)

        # --- Ações Rápidas ---
        gb_acoes = QGroupBox("Ações")
        layout_acoes = QVBoxLayout(gb_acoes)

        hbox_top = QHBoxLayout()
        btn_zoom = QPushButton("🎯 Zoom")
        btn_zoom.setObjectName("btnAcaoSecundaria")
        btn_zoom.clicked.connect(lambda: self.acao_tabela(self.zoom_para_imovel))
        
        btn_ficha = QPushButton("📄 Ver Ficha")
        btn_ficha.clicked.connect(lambda: self.acao_tabela(self.abrir_ficha_por_item))
        
        hbox_top.addWidget(btn_zoom)
        hbox_top.addWidget(btn_ficha)
        layout_acoes.addLayout(hbox_top)
        
        btn_mapa = QPushButton("🖱️ Selecionar Clicando no Mapa")
        btn_mapa.setObjectName("btnAcaoSecundaria")
        btn_mapa.clicked.connect(self.ativar_ferramenta_mapa)
        layout_acoes.addWidget(btn_mapa)

        btn_croqui = QPushButton("🖨️ Gerar Croqui Rápido")
        btn_croqui.clicked.connect(lambda: self.acao_tabela(self.exportar_croqui))
        layout_acoes.addWidget(btn_croqui)

        self.layout.addWidget(gb_acoes)

    def get_layer(self):
        nome_alvo = "IMOBILIARIO"
        layers = QgsProject.instance().mapLayersByName(nome_alvo)
        if layers: return layers[0]
        iface.messageBar().pushMessage("Erro", f"Camada base '{nome_alvo}' não encontrada.", level=2)
        return None

    def find_col(self, layer, keywords, exclude_keywords=[]):
        for f in layer.fields():
            fn_norm = normalize_str(f.name())
            is_excluded = False
            for exc in exclude_keywords:
                if exc in fn_norm:
                    is_excluded = True
                    break
            if is_excluded: continue
            for k in keywords:
                if k in fn_norm: return f.name()
        return None

    def buscar(self):
        texto = self.input_busca.text().strip()
        layer = self.get_layer()
        if not layer or not texto: return

        tipo = self.combo.currentText()
        exata = self.check_exata.isChecked()
        
        self.tabela.setSortingEnabled(False)
        self.tabela.setRowCount(0)
        
        expr = ""
        if tipo == "Inscrição":
            col = self.find_col(layer, ['inscricao', 'im'])
            if not col: return self.aviso_coluna("Inscrição")
            op = "=" if exata else "ILIKE"
            val = f"'{texto}'" if exata else f"'%{texto}%'"
            expr = f"\"{col}\" {op} {val}"

        elif tipo == "Endereço":
            col = self.find_col(layer, ['bd_smar_imovel_endereco', 'endereco'])
            if not col: col = self.find_col(layer, ['logradouro', 'rua']) 
            if not col: return self.aviso_coluna("Endereço")
            expr = f"\"{col}\" ILIKE '%{texto}%'"

        elif tipo == "Proprietário":
            col = self.find_col(layer, ['proprietario', 'prop', 'nome'], exclude_keywords=['cpf', 'cnpj', 'doc'])
            if not col: return self.aviso_coluna("Proprietário")
            op = "=" if exata else "ILIKE"
            val = f"'{texto}'" if exata else f"'%{texto}%'"
            expr = f"\"{col}\" {op} {val}"

        elif tipo == "CPF/CNPJ":
            col = self.find_col(layer, ['cpf', 'cnpj', 'doc'])
            if not col: return self.aviso_coluna("CPF/CNPJ")
            nums = re.sub(r'[^0-9]', '', texto)
            if not nums: return
            op = "=" if exata else "LIKE"
            val = f"'{nums}'" if exata else f"'%{nums}%'"
            expr = f"regexp_replace(\"{col}\", '[^0-9]', '') {op} {val}"

        try:
            req = QgsFeatureRequest().setFilterExpression(expr)
            feats = list(layer.getFeatures(req))
            self.tabela.setRowCount(len(feats))
            
            c_insc = self.find_col(layer, ['inscricao', 'im'])
            c_prop = self.find_col(layer, ['proprietario', 'prop'], exclude_keywords=['cpf', 'cnpj', 'doc'])
            c_end  = self.find_col(layer, ['bd_smar_imovel_endereco', 'endereco'])
            if not c_end: c_end = self.find_col(layer, ['logradouro'])

            for r, f in enumerate(feats):
                v_insc = str(f[c_insc]) if c_insc else ""
                v_prop = str(f[c_prop]) if c_prop else ""
                v_end = str(f[c_end]) if c_end else ""

                self.tabela.setItem(r, 0, QTableWidgetItem(v_insc))
                self.tabela.setItem(r, 1, QTableWidgetItem(v_prop))
                self.tabela.setItem(r, 2, QTableWidgetItem(v_end))
                self.tabela.item(r, 0).setData(Qt.UserRole, f.id())

            self.tabela.setSortingEnabled(True)
            if not feats:
                iface.messageBar().pushMessage("Busca", "Nenhum resultado encontrado.", level=1)
        except Exception as e:
            iface.messageBar().pushMessage("Erro", f"Falha na consulta: {e}", level=2)

    def aviso_coluna(self, nome):
        iface.messageBar().pushMessage("Erro", f"Coluna correspondente a '{nome}' não identificada.", level=2)

    def acao_tabela(self, func):
        sel = self.tabela.selectedItems()
        if not sel: 
            iface.messageBar().pushMessage("Atenção", "Selecione primeiro um imóvel na tabela.", level=1, duration=2)
            return
        func(sel[0])

    def zoom_para_imovel(self, item):
        layer = self.get_layer()
        if not layer: return
        fid = self.tabela.item(item.row(), 0).data(Qt.UserRole)
        layer.selectByIds([fid])
        box = layer.boundingBoxOfSelected()
        box.scale(1.5)
        iface.mapCanvas().setExtent(box)
        iface.mapCanvas().refresh()

    def abrir_ficha_por_item(self, item):
        layer = self.get_layer()
        if not layer: return
        fid = self.tabela.item(item.row(), 0).data(Qt.UserRole)
        self.abrir_dialogo_ficha(layer.getFeature(fid))

    def abrir_dialogo_ficha(self, feature):
        layer = self.get_layer()
        if not layer: return
        dialog = FichaImovelDialog(feature, layer, self)
        dialog.exec_()

    def ativar_ferramenta_mapa(self):
        layer = self.get_layer()
        if not layer: return
        self.tool_selecao = ToolSelecionarFicha(iface.mapCanvas(), layer)
        self.tool_selecao.imovel_encontrado.connect(self.abrir_dialogo_ficha)
        iface.mapCanvas().setMapTool(self.tool_selecao)
        iface.messageBar().pushMessage("Ferramenta Ativa", "Clique sobre o polígono do imóvel no mapa.", level=0, duration=3)

    def exportar_croqui(self, item):
        layer = self.get_layer()
        if not layer: return
        fid = self.tabela.item(item.row(), 0).data(Qt.UserRole)
        
        layer.selectByIds([fid])
        box = layer.getFeature(fid).geometry().boundingBox()
        box.scale(1.2)
        iface.mapCanvas().setExtent(box)
        iface.mapCanvas().refresh()

        project = QgsProject.instance()
        layout_manager = project.layoutManager()
        nome_layout = "A4 - Croqui de Imovel (IMOBILIARIO)"
        layout = layout_manager.layoutByName(nome_layout)

        if not layout:
            iface.messageBar().pushMessage("Erro", f"Layout base '{nome_layout}' em falta.", level=2)
            return

        atlas = layout.atlas()
        atlas.setCoverageLayer(layer)
        atlas.setEnabled(True)
        atlas.setFilterFeatures(True)
        atlas.setFilterExpression(f"$id = {fid}")

        row = item.row()
        inscricao_raw = self.tabela.item(row, 0).text()
        inscricao_limpa = re.sub(r'[\\/*?:"<>|]', "", inscricao_raw)
        
        nome_sugestao = f"CROQUI_{inscricao_limpa}.pdf"
        path_inicial = os.path.join(os.path.expanduser("~"), "Documents", nome_sugestao)
        
        filename, _ = QFileDialog.getSaveFileName(self, "Exportar Croqui", path_inicial, "PDF (*.pdf)")
        if not filename: return

        if atlas.updateFeatures(): 
            atlas.beginRender()
            atlas.seekTo(0)
            exporter = QgsLayoutExporter(layout)
            result = exporter.exportToPdf(filename, QgsLayoutExporter.PdfExportSettings())
            atlas.endRender()
            if result == QgsLayoutExporter.Success:
                iface.messageBar().pushMessage("Sucesso", "Exportado com sucesso.", level=0)
                try: os.startfile(filename)
                except: pass
            else:
                iface.messageBar().pushMessage("Erro", "Erro ao guardar ficheiro.", level=2)
        else:
             iface.messageBar().pushMessage("Erro", "Falha de renderização.", level=2)